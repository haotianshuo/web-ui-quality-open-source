"""Narrow public facade for Web UI Quality 4.0 Product Evidence Foundation.

The historical module-level exports remain compatibility surfaces during the 4.0 transition. New integrations should start here instead of orchestrating the
internal diagnosis/governance modules directly.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .auth_profiles import load_auth_profile
from .experience_fix import run_experience_fix


def run(
    target: str | Path,
    request: str,
    *,
    url: str | None = None,
    files: Iterable[str] = (),
    artifacts_root: str | Path | None = None,
    auth_profile: str | None = None,
    storage_state: str | Path | None = None,
    allowed_origins: Iterable[str] = (),
    browser_executable: str | Path | None = None,
    host_tool_results: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Run the consolidated repair/inspection workflow without exposing runtime IDs."""
    target_path = Path(str(target)).expanduser()
    root = Path(artifacts_root).expanduser() if artifacts_root else ((target_path.resolve() / ".wuq" / "runs") if target_path.is_dir() else (Path.cwd() / ".wuq" / "runs"))
    allowed = list(allowed_origins)
    auth_state = "anonymous"
    state = storage_state
    if auth_profile:
        profile = load_auth_profile(auth_profile)
        state = Path(profile["storageStatePath"])
        allowed = sorted(set(allowed) | set(profile.get("allowedOrigins", [])))
        auth_state = f"profile:{auth_profile}"
    elif state is not None:
        auth_state = "explicit-storage-state"
    local_id = uuid.uuid4().hex[:16]
    return run_experience_fix(
        target, root, request=request,
        task_id=f"api-task-{local_id}", session_id=f"api-session-{local_id}",
        url=url, files=files, allowed_origins=allowed, auth_state=auth_state,
        browser_executable=browser_executable, storage_state=state, host_tool_results=host_tool_results,
    )


__all__ = ["run"]
