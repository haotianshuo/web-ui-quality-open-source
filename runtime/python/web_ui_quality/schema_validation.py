"""Small dependency-free JSON Schema validator for bundled WUQ contracts.

It implements the assertion keywords used by this project.  It is not exposed
as a general replacement for the full ``jsonschema`` package; its purpose is to
keep ``doctor`` and clean-environment contract tests useful in any Codex host.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


class SchemaValidationError(ValueError):
    pass


_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _pointer(document: Any, fragment: str) -> Any:
    value = document
    if not fragment or fragment == "#":
        return value
    if not fragment.startswith("#/"):
        raise SchemaValidationError(f"unsupported schema fragment: {fragment}")
    for token in fragment[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def _resolve(ref: str, root: dict[str, Any], base_dir: Path | None) -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    if ref.startswith("#"):
        return _pointer(root, ref), root, base_dir
    filename, marker, fragment = ref.partition("#")
    if base_dir is None:
        raise SchemaValidationError(f"cannot resolve external ref without base directory: {ref}")
    path = (base_dir / filename).resolve()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SchemaValidationError(f"cannot resolve schema ref {ref}: {type(error).__name__}") from error
    target = _pointer(document, f"#{fragment}" if marker else "#")
    return target, document, path.parent


def _is_type(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    kind = _TYPES.get(expected)
    return bool(kind and isinstance(value, kind))


def _unique(items: list[Any]) -> bool:
    encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in items]
    return len(encoded) == len(set(encoded))


def _validate(
    instance: Any,
    schema: Any,
    *,
    root: dict[str, Any],
    base_dir: Path | None,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(schema, bool):
        if not schema:
            errors.append(f"{path}: schema rejects value")
        return
    if not isinstance(schema, dict):
        errors.append(f"{path}: invalid schema node")
        return
    if "$ref" in schema:
        try:
            target, target_root, target_base = _resolve(str(schema["$ref"]), root, base_dir)
        except SchemaValidationError as error:
            errors.append(f"{path}: {error}")
            return
        _validate(instance, target, root=target_root, base_dir=target_base, path=path, errors=errors)
        return

    expected = schema.get("type")
    if expected is not None:
        choices = [expected] if isinstance(expected, str) else expected
        if not isinstance(choices, list) or not any(_is_type(instance, item) for item in choices if isinstance(item, str)):
            errors.append(f"{path}: expected type {expected!r}")
            return
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")

    for subschema in schema.get("allOf", []):
        _validate(instance, subschema, root=root, base_dir=base_dir, path=path, errors=errors)
    for keyword, required_count in (("anyOf", 1), ("oneOf", 1)):
        if keyword in schema:
            matches = 0
            for subschema in schema[keyword]:
                branch_errors: list[str] = []
                _validate(instance, subschema, root=root, base_dir=base_dir, path=path, errors=branch_errors)
                matches += not branch_errors
            valid = matches >= required_count if keyword == "anyOf" else matches == required_count
            if not valid:
                errors.append(f"{path}: {keyword} matched {matches} branches")
    if "not" in schema:
        branch_errors: list[str] = []
        _validate(instance, schema["not"], root=root, base_dir=base_dir, path=path, errors=branch_errors)
        if not branch_errors:
            errors.append(f"{path}: value matches forbidden schema")
    if "if" in schema:
        branch_errors: list[str] = []
        _validate(instance, schema["if"], root=root, base_dir=base_dir, path=path, errors=branch_errors)
        branch = schema.get("then") if not branch_errors else schema.get("else")
        if branch is not None:
            _validate(instance, branch, root=root, base_dir=base_dir, path=path, errors=errors)

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], root=root, base_dir=base_dir, path=f"{path}.{key}", errors=errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(value, schema["additionalProperties"], root=root, base_dir=base_dir, path=f"{path}.{key}", errors=errors)
    elif isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            errors.append(f"{path}: expected at most {schema['maxItems']} items")
        if schema.get("uniqueItems") and not _unique(instance):
            errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, value in enumerate(instance):
                _validate(value, item_schema, root=root, base_dir=base_dir, path=f"{path}[{index}]", errors=errors)
    elif isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: string is shorter than minLength")
        if "maxLength" in schema and len(instance) > int(schema["maxLength"]):
            errors.append(f"{path}: string is longer than maxLength")
        if "pattern" in schema and re.search(str(schema["pattern"]), instance) is None:
            errors.append(f"{path}: string does not match pattern")
    elif isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: number is below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: number is above maximum")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: number is not above exclusiveMinimum")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: number is not below exclusiveMaximum")


def validation_errors(instance: Any, schema: dict[str, Any], *, base_dir: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    _validate(instance, schema, root=schema, base_dir=Path(base_dir).resolve() if base_dir else None, path="$", errors=errors)
    return errors


def validate_instance(instance: Any, schema: dict[str, Any], *, base_dir: str | Path | None = None) -> None:
    errors = validation_errors(instance, schema, base_dir=base_dir)
    if errors:
        raise SchemaValidationError("; ".join(errors[:12]))


def check_schema_bundle(schema_dir: str | Path) -> dict[str, Any]:
    directory = Path(schema_dir).resolve()
    errors: list[dict[str, str]] = []
    files = sorted(directory.glob("*.json"))
    for path in files:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(schema, dict):
                raise SchemaValidationError("root must be an object")
            if not isinstance(schema.get("$schema"), str):
                raise SchemaValidationError("$schema is required")
            refs: list[str] = []
            stack = [schema]
            while stack:
                value = stack.pop()
                if isinstance(value, dict):
                    if isinstance(value.get("$ref"), str):
                        refs.append(value["$ref"])
                    stack.extend(value.values())
                elif isinstance(value, list):
                    stack.extend(value)
            for ref in refs:
                _resolve(ref, schema, path.parent)
        except (OSError, json.JSONDecodeError, SchemaValidationError, KeyError, IndexError) as error:
            errors.append({"file": path.name, "error": str(error)})
    return {"status": "PASS" if files and not errors else "FAIL", "checked": len(files), "errors": errors, "engine": "wuq-builtin-contract-validator"}
