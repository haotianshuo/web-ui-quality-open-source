import json
from pathlib import Path

import pytest

from web_ui_quality import __main__ as cli
from web_ui_quality.__main__ import _COMMAND_LIFECYCLE, _INTERNAL_COMMANDS, _PUBLIC_COMMANDS, _COMPATIBILITY_COMMANDS, _parser
from web_ui_quality.browser_locator import resolve_browser_executable
from web_ui_quality.contracts import ContractViolation


def _subparsers():
    parser = _parser()
    action = next(item for item in parser._actions if item.__class__.__name__ == "_SubParsersAction")
    return parser, action


def test_cli_uses_product_prog_name():
    parser, _ = _subparsers()
    assert parser.prog == "web-ui-quality"


def test_ui_inventory_has_complete_help_and_browser_path():
    _, action = _subparsers()
    inventory = action.choices["ui-inventory"]
    flags = [item for item in inventory._actions if item.option_strings and item.dest != "help"]
    assert flags
    assert all(item.help not in {None, ""} for item in flags)
    assert any("--browser-executable" in item.option_strings for item in flags)


def test_public_browser_entries_accept_explicit_executable():
    _, action = _subparsers()
    for command in ("experience-fix", "inspect", "ui-inventory"):
        parser = action.choices[command]
        assert any("--browser-executable" in item.option_strings for item in parser._actions)


def test_run_exposes_after_and_host_receipt_options():
    _, action = _subparsers()
    options = {option for item in action.choices["run"]._actions for option in item.option_strings}
    assert {"--after-url", "--host-write-receipt"} <= options


def test_run_after_reuses_latest_fix_session_and_receipt(tmp_path: Path, monkeypatch, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run_dir = tmp_path / "run"
    receipt_path = tmp_path / "host-write-receipt.json"
    receipt = {"receiptId": "receipt-1"}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    observed = {}

    def fake_find(artifacts_root, **kwargs):
        observed["find"] = {"artifactsRoot": Path(artifacts_root), **kwargs}
        return run_dir

    def fake_run(*args, **kwargs):
        observed["runArgs"] = args
        observed["runKwargs"] = kwargs
        return {"status": "PASS"}

    monkeypatch.setattr(cli, "find_latest_compatible_run", fake_find)
    monkeypatch.setattr(cli, "load_experience_run", lambda path: {"sessionId": "persisted-session"})
    monkeypatch.setattr(cli, "run_experience_fix", fake_run)

    exit_code = cli.main([
        "run", str(project), "--request", "修复并验证当前问题",
        "--url", "http://127.0.0.1:3000/", "--after-url", "http://127.0.0.1:3000/",
        "--host-write-receipt", str(receipt_path), "--compact",
    ])

    assert exit_code == 0
    assert observed["find"]["artifactsRoot"] == project.resolve() / ".wuq" / "runs"
    assert observed["find"]["mode"] == "FIX_AND_VERIFY"
    assert observed["find"]["target_identity"]["projectRoot"] == "."
    assert observed["runKwargs"]["existing_run"] == run_dir
    assert observed["runKwargs"]["session_id"] == "persisted-session"
    assert observed["runKwargs"]["mode"] == "FIX_AND_VERIFY"
    assert observed["runKwargs"]["after_url"] == "http://127.0.0.1:3000/"
    assert observed["runKwargs"]["host_write_receipt"] == receipt
    capsys.readouterr()


def test_run_after_uses_after_url_when_url_is_omitted(tmp_path: Path, monkeypatch, capsys):
    project = tmp_path / "project"
    project.mkdir()
    observed = {}

    monkeypatch.setattr(cli, "find_latest_compatible_run", lambda artifacts_root, **kwargs: observed.setdefault("find", kwargs) and tmp_path / "run")
    monkeypatch.setattr(cli, "load_experience_run", lambda path: {"sessionId": "persisted-session"})

    def fake_run(*args, **kwargs):
        observed["runKwargs"] = kwargs
        return {"status": "PASS"}

    monkeypatch.setattr(cli, "run_experience_fix", fake_run)

    exit_code = cli.main([
        "run", str(project), "--request", "验证修复结果",
        "--after-url", "http://127.0.0.1:3000/", "--compact",
    ])

    assert exit_code == 0
    assert observed["find"]["target_identity"]["url"] == "http://127.0.0.1:3000/"
    assert observed["runKwargs"]["url"] == "http://127.0.0.1:3000/"
    capsys.readouterr()


@pytest.mark.parametrize("status", ["FAIL", "BLOCKED", "FRAMEWORK_NOT_SUPPORTED"])
def test_run_returns_nonzero_for_failure_statuses(tmp_path: Path, monkeypatch, capsys, status: str):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cli, "run_experience_fix", lambda *args, **kwargs: {"status": status})

    assert cli.main(["run", str(project), "--request", "检查界面", "--compact"]) == 1
    capsys.readouterr()


def test_every_reachable_command_has_a_lifecycle():
    _, action = _subparsers()
    assert set(action.choices) == set(_COMMAND_LIFECYCLE)
    assert len(action.choices) == len(_COMMAND_LIFECYCLE)
    assert _PUBLIC_COMMANDS == {"run", "doctor", "auth", "expert"}
    assert {"experience-fix", "inspect", "fix", "redesign", "audit", "ui-inventory"} == _COMPATIBILITY_COMMANDS
    assert len(_INTERNAL_COMMANDS) == 24


def test_contract_violation_keeps_machine_pointer_but_cleans_cli_message():
    error = ContractViolation("PLAYWRIGHT_UNAVAILABLE", ["$: install web-ui-quality[browser]"])
    assert error.as_dict()["errors"] == ["$: install web-ui-quality[browser]"]
    human = error.as_user_dict()
    assert human["errors"] == ["install web-ui-quality[browser]"]
    assert human["message"] == "install web-ui-quality[browser]"


def test_explicit_browser_path_wins(tmp_path: Path):
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"stub")
    result = resolve_browser_executable("chromium", explicit=executable)
    assert result["available"] is True
    assert result["source"] == "explicit"
    assert Path(result["executable"]) == executable.resolve()
