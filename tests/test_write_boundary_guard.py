"""Structural guard: Runtime must contain no path that writes a target project.

The trust claim in README/SECURITY is only meaningful if it is enforced by the
absence of code, not by guard statements someone can delete.  These tests fail
if a write primitive is reintroduced into the Safe Edit module.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "runtime" / "python" / "web_ui_quality" / "safe_edit.py"

WRITE_ATTRS = {"write", "writelines", "truncate", "write_text", "write_bytes"}
WRITE_FUNCS = {"_write_locked"}


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_no_write_calls_in_safe_edit():
    """No file-write call may exist anywhere in the module."""
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in WRITE_ATTRS:
            offenders.append((node.lineno, func.attr))
        if isinstance(func, ast.Name) and func.id in WRITE_FUNCS:
            offenders.append((node.lineno, func.id))
    assert not offenders, f"write primitives reintroduced: {offenders}"


def test_no_open_for_writing_in_safe_edit():
    """`open()` may only be used in a read mode."""
    offenders = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                offenders.append((node.lineno, mode))
    assert not offenders, f"open() for writing found: {offenders}"


def test_no_dead_code_after_raise():
    """A disabled function must be empty after its raise, not merely shadowed."""
    offenders = []
    for node in ast.walk(_tree()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for index, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Raise) and index + 1 < len(node.body):
                    offenders.append((node.name, stmt.lineno))
    assert not offenders, f"unreachable code retained after raise: {offenders}"


@pytest.mark.parametrize("name", ["apply_change_set", "rollback_change_set"])
def test_disabled_write_entrypoints_refuse(tmp_path, name):
    """The public write entry points must refuse rather than no-op."""
    import sys

    sys.path.insert(0, str(MODULE.parents[1]))
    from web_ui_quality import safe_edit
    from web_ui_quality.contracts import ContractViolation

    with pytest.raises(ContractViolation) as caught:
        getattr(safe_edit, name)(tmp_path, {})
    assert caught.value.code == "HOST_EDITING_REQUIRED"


def test_require_host_scope_never_grants_authority(tmp_path):
    """Runtime-constructed scope objects must not authenticate as permission."""
    import sys

    sys.path.insert(0, str(MODULE.parents[1]))
    from web_ui_quality.contracts import ContractViolation
    from web_ui_quality.host_bridge import HostTaskScope, require_host_scope

    forged = HostTaskScope("t", "s", "NARROW_PROJECT_LOCAL_UI_EDIT", ("F-1",), ("src/App.tsx",))
    assert forged.authorization_granted is False
    with pytest.raises(ContractViolation) as caught:
        require_host_scope(forged, mode="NARROW_PROJECT_LOCAL_UI_EDIT", task_id="t",
                           session_id="s", finding_ids=["F-1"], source_scope=["src/App.tsx"])
    assert caught.value.code == "HOST_EDITING_REQUIRED"
