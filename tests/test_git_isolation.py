"""P0: Source Assurance must never execute repository-controlled programs.

A repository can point `core.fsmonitor`, `diff.external`, `core.pager` or
`core.hooksPath` at an arbitrary executable. Any git subcommand run inside such
a repository hands control to the audited project, which breaks the core promise
that inspecting source code never runs source code.

The attack is platform sensitive: git dispatches these hooks through its bundled
`sh`, so whether a marker file appears depends on the local git build. The tests
below therefore verify the *mechanism* (hardened argv and environment) rather
than relying on a marker that some platforms silently fail to produce, plus an
end-to-end check with a baseline that proves the harness itself is capable of
reproducing the attack.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from web_ui_quality.source_assurance import (
    _git_config_args,
    _git_env,
    _run_git,
    resolve_change_scope,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

_HOSTILE_KEYS = ("core.fsmonitor", "diff.external", "core.pager", "core.hooksPath")


def _make_hostile_repo(base: Path) -> tuple[Path, Path]:
    """Create a repo whose local config runs a marker-dropping script."""
    repo = base / "hostile"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True, capture_output=True)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")

    script = repo / "hook.sh"
    script.write_text("#!/bin/sh\ntouch PWNED\nexit 1\n", encoding="utf-8", newline="\n")
    script.chmod(0o755)

    for key in _HOSTILE_KEYS:
        subprocess.run(
            ["git", "-C", str(repo), "config", key, script.as_posix()],
            check=True, capture_output=True,
        )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "init"],
        check=True, capture_output=True,
    )
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    return repo, repo / "PWNED"


def _unhardened_git_reproduces_attack(repo: Path, marker: Path) -> bool:
    """Baseline: can a plain git call in this environment trigger the hook?"""
    marker.unlink(missing_ok=True)
    subprocess.run(["git", "status", "--porcelain=v1"], cwd=repo, capture_output=True)
    subprocess.run(["git", "diff"], cwd=repo, capture_output=True)
    triggered = marker.exists()
    marker.unlink(missing_ok=True)
    return triggered


def test_hardened_git_env_blocks_config_injection() -> None:
    env = _git_env()
    assert env.get("GIT_CONFIG_NOSYSTEM") == "1"
    assert env.get("GIT_CONFIG_GLOBAL") in {os.devnull, "/dev/null", "NUL"}
    assert env.get("GIT_EXTERNAL_DIFF") == ""
    assert env.get("GIT_OPTIONAL_LOCKS") == "0"
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
    # PATH must be inherited, otherwise git silently breaks on some platforms
    # and the isolation would only appear to work by accident.
    assert env.get("PATH")


def test_hardened_git_command_pins_safety_flags() -> None:
    joined = " ".join(_git_config_args())
    assert "core.fsmonitor=false" in joined
    assert "core.hooksPath=" in joined
    assert "diff.external=" in joined
    assert "core.pager=cat" in joined
    assert "protocol.ext.allow=never" in joined
    assert "uploadpack.packObjectsHook=" in joined


def test_explicit_scope_skips_git_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit file scope must need no git process at all."""
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")

    def _fail(project, args):  # type: ignore[no-untyped-def]
        raise AssertionError(f"git must not run for explicit scope: {list(args)}")

    monkeypatch.setattr("web_ui_quality.source_assurance._run_git", _fail)
    result = resolve_change_scope(repo, files=["a.py"])

    assert result["files"] == ["a.py"]
    assert result["scopeState"] == "SOURCE_SCOPE_READY"
    assert result["workspaceStateSource"] == "NOT_CONSULTED"
    assert result["dirtyWorkspace"] == []


def test_hardened_run_git_does_not_execute_hooks(tmp_path: Path) -> None:
    repo, marker = _make_hostile_repo(tmp_path)
    if not _unhardened_git_reproduces_attack(repo, marker):
        pytest.skip("local git build does not dispatch these hooks; baseline absent")

    _run_git(repo, ["status", "--porcelain=v1", "--untracked-files=all"])
    _run_git(repo, ["diff", "--name-only", "--diff-filter=ACMRTUXB", "--"])

    assert not marker.exists(), "hardened git invocation executed a repository program"


def test_git_diff_scope_does_not_execute_hooks(tmp_path: Path) -> None:
    repo, marker = _make_hostile_repo(tmp_path)
    if not _unhardened_git_reproduces_attack(repo, marker):
        pytest.skip("local git build does not dispatch these hooks; baseline absent")

    resolve_change_scope(repo)

    assert not marker.exists(), "scope resolution executed a repository program"
