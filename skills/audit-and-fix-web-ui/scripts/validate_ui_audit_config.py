#!/usr/bin/env python3
"""Validate .ui-audit.json without accepting credential material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORBIDDEN_FRAGMENTS = ("password", "secret", "token", "cookie", "credential", "api_key", "apikey")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a project .ui-audit.json")
    parser.add_argument("config", help="path to .ui-audit.json")
    parser.add_argument("--schema", help="override bundled schema path")
    return parser.parse_args()


def find_forbidden(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.casefold()
            if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
                errors.append(f"{path}.{key}: credentials and secrets are forbidden")
            errors.extend(find_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_forbidden(child, f"{path}[{index}]"))
    return errors


def manual_validate(config: Any) -> list[str]:
    if not isinstance(config, dict):
        return ["$: expected object"]
    errors = find_forbidden(config)
    if config.get("schemaVersion") != "1":
        errors.append("$.schemaVersion: expected string '1'")
    allowed = {
        "schemaVersion", "routes", "roles", "viewports", "cssSources", "finalizedPages",
        "safeActions", "protectedActions", "adapters", "accessibility", "journeys",
        "acceptedDifferences",
    }
    for key in config:
        if key not in allowed:
            errors.append(f"$.{key}: unknown property")
    for index, viewport in enumerate(config.get("viewports", [])):
        if not isinstance(viewport, dict):
            errors.append(f"$.viewports[{index}]: expected object")
            continue
        for key in ("name", "width", "height"):
            if key not in viewport:
                errors.append(f"$.viewports[{index}].{key}: required")
    return sorted(set(errors))


def validate(config_path: Path, schema_path: Path) -> list[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = find_forbidden(config)
    try:
        import jsonschema
    except ImportError:
        errors.extend(manual_validate(config))
    else:
        validator = jsonschema.Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(config), key=lambda item: list(item.absolute_path)):
            location = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            errors.append(f"{location}: {error.message}")
    return sorted(set(errors))


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    plugin_root = Path(__file__).resolve().parents[3]
    schema_path = (
        Path(args.schema).expanduser().resolve()
        if args.schema
        else plugin_root / "schemas" / "ui-audit.schema.json"
    )
    if not config_path.is_file():
        print(f"Config not found: {config_path}")
        return 2
    if not schema_path.is_file():
        print(f"Schema not found: {schema_path}")
        return 2
    try:
        errors = validate(config_path, schema_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"Config validation failed: {error}")
        return 2
    if errors:
        print("UI audit config is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"UI audit config is valid: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
