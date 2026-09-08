#!/usr/bin/env python3
"""Install Web UI Quality into a local Codex marketplace safely."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


PLUGIN_NAME = "web-ui-quality"
EXCLUDED_NAMES = {
    ".git", ".pytest_cache", ".test-workspace", "__pycache__", "build", "dist",
    "external-proof", "reports", "tests", "PKG-INFO", "run_tests.py",
}
EXCLUDED_PREFIXES = ("release-evidence-", "RELEASE_REPORT_")


def _ignore(_: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDED_NAMES
        or name.startswith(EXCLUDED_PREFIXES)
        or name.endswith((".pyc", ".pyo", ".egg-info"))
        or name == ".DS_Store"
    }


def _load_marketplace(path: Path, name: str) -> dict:
    if not path.exists():
        return {"name": name, "interface": {"displayName": name.replace("-", " ").title()}, "plugins": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("plugins"), list):
        raise ValueError(f"invalid marketplace file: {path}")
    if value.get("name") != name:
        raise ValueError(f"marketplace name is {value.get('name')!r}, expected {name!r}")
    interface = value.get("interface")
    if interface is None:
        value["interface"] = {"displayName": name.replace("-", " ").title()}
    elif not isinstance(interface, dict):
        raise ValueError(f"marketplace interface must be an object: {path}")
    return value


def _updated_marketplace(marketplace: dict) -> dict:
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    updated = dict(marketplace)
    plugins = list(marketplace["plugins"])
    positions = [index for index, item in enumerate(plugins) if isinstance(item, dict) and item.get("name") == PLUGIN_NAME]
    if positions:
        plugins[positions[0]] = entry
        for index in reversed(positions[1:]):
            del plugins[index]
    else:
        plugins.append(entry)
    updated["plugins"] = plugins
    return updated


def _validate_source(source: Path) -> dict:
    manifest = source / ".codex-plugin" / "plugin.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("name") != PLUGIN_NAME or source.name != PLUGIN_NAME:
        raise ValueError("source folder and plugin manifest must both be named web-ui-quality")
    if not isinstance(payload.get("version"), str) or not payload["version"]:
        raise ValueError("plugin manifest version is missing")
    if not (source / "skills" / "audit-and-fix-web-ui" / "SKILL.md").is_file():
        raise ValueError("primary plugin skill is missing")
    return payload


def install(
    source: Path,
    plugins_dir: Path | None,
    marketplace_path: Path,
    marketplace_name: str,
    *,
    replace: bool,
) -> dict:
    source = source.expanduser().resolve()
    payload = _validate_source(source)
    marketplace_path = marketplace_path.expanduser().resolve()
    expected_plugins_dir = marketplace_path.parent / "plugins"
    plugins_dir = expected_plugins_dir if plugins_dir is None else plugins_dir.expanduser().resolve()
    if plugins_dir != expected_plugins_dir:
        raise ValueError(
            f"plugins directory must be {expected_plugins_dir} so marketplace source ./plugins/{PLUGIN_NAME} resolves correctly"
        )
    target = plugins_dir / PLUGIN_NAME
    if source == target:
        raise ValueError("source is already the marketplace installation target")
    if target.exists() and not replace:
        raise FileExistsError(f"{target} already exists; rerun with --replace to keep a backup and update it")

    # Validate and render the marketplace before mutating either destination.
    marketplace = _updated_marketplace(_load_marketplace(marketplace_path, marketplace_name))
    marketplace_text = json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_target: Path | None = None
    backup_marketplace: Path | None = None

    with tempfile.TemporaryDirectory(prefix="wuq-install-", dir=plugins_dir) as temp:
        staged = Path(temp) / PLUGIN_NAME
        shutil.copytree(source, staged, ignore=_ignore)
        _validate_source(staged)
        pending_marketplace = Path(temp) / "marketplace.json"
        pending_marketplace.write_text(marketplace_text, encoding="utf-8")
        json.loads(pending_marketplace.read_text(encoding="utf-8"))

        if target.exists():
            backup_target = plugins_dir / f"{PLUGIN_NAME}.backup-{stamp}"
            if backup_target.exists():
                raise FileExistsError(f"backup destination already exists: {backup_target}")
        if marketplace_path.exists():
            backup_marketplace = marketplace_path.with_name(marketplace_path.name + f".backup-{stamp}")
            if backup_marketplace.exists():
                raise FileExistsError(f"backup destination already exists: {backup_marketplace}")

        if target.exists() and backup_target is not None:
            target.replace(backup_target)
        if marketplace_path.exists() and backup_marketplace is not None:
            shutil.copy2(marketplace_path, backup_marketplace)

        replacement: Path | None = None
        try:
            staged.replace(target)
            replacement = marketplace_path.with_name(marketplace_path.name + f".pending-{os.getpid()}")
            replacement.write_text(marketplace_text, encoding="utf-8")
            replacement.replace(marketplace_path)
        except OSError:
            if replacement is not None and replacement.exists():
                replacement.unlink()
            if target.exists():
                shutil.rmtree(target)
            if backup_target is not None and backup_target.exists():
                backup_target.replace(target)
            raise

    return {
        "status": "INSTALLED",
        "version": payload["version"],
        "plugin": str(target),
        "marketplace": str(marketplace_path),
        "backup": str(backup_target) if backup_target else None,
        "pluginBackup": str(backup_target) if backup_target else None,
        "marketplaceBackup": str(backup_marketplace) if backup_marketplace else None,
        "nextCommand": f"codex plugin add {PLUGIN_NAME}@{marketplace_name}",
        "newThreadRequiredForUpdatedSkill": True,
    }


def main() -> int:
    runtime = Path(__file__).resolve().parents[1] / "runtime" / "python"
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    parser = argparse.ArgumentParser(description="Install Web UI Quality into a local Codex marketplace")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--plugins-dir", type=Path, help="must be the marketplace's ./plugins directory; derived by default")
    parser.add_argument("--marketplace", type=Path, default=Path.home() / ".agents" / "plugins" / "marketplace.json")
    parser.add_argument("--marketplace-name", default="personal")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        result = install(args.source, args.plugins_dir, args.marketplace, args.marketplace_name, replace=args.replace)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAILED", "error": str(error)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
