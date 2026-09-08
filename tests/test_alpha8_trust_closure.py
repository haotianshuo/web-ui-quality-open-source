from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.host_bridge import require_verified_host_write, verify_host_write_receipt
from web_ui_quality.mutation_firewall import BrowserMutationFirewall
from web_ui_quality.production_mapper import build_production_plan, generate_production_scaffold
from web_ui_quality.project_baseline import build_project_baseline, compare_project_baseline


def test_5001_file_baseline_is_explicitly_incomplete(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    for index in range(5001):
        (project / f"file-{index:04d}.css").write_text("a{}", encoding="utf-8")

    baseline = build_project_baseline(project)
    comparison = compare_project_baseline(baseline, project, target_files=["file-5000.css"])

    assert baseline["fileCount"] == 5000
    assert baseline["truncated"] is True
    assert baseline["completenessStatus"] == "INDETERMINATE"
    assert comparison["status"] == "INDETERMINATE"
    assert comparison["reasonCode"] == "BASELINE_INCOMPLETE"
    assert comparison["baselineComplete"] is False


def test_dangerous_get_is_a_blocked_mutation_attempt():
    firewall = BrowserMutationFirewall(["https://example.test"])

    decision = firewall.evaluate(
        url="https://example.test/account/logout?next=/", method="GET", resource_type="document"
    )

    assert decision.allow is False
    assert decision.code == "SIDE_EFFECT_ROUTE_BLOCKED"
    assert firewall.mutation_attempted is True


def test_authenticated_navigation_requires_an_approved_route():
    firewall = BrowserMutationFirewall(
        ["https://example.test"], approved_routes=["/home"], authenticated=True
    )

    allowed = firewall.evaluate(
        url="https://example.test/home", method="GET", resource_type="document"
    )
    blocked = firewall.evaluate(
        url="https://example.test/admin", method="GET", resource_type="document"
    )

    assert allowed.allow is True
    assert blocked.allow is False
    assert blocked.code == "ROUTE_NOT_APPROVED"


def _host_receipt_fixture(tmp_path: Path):
    project = tmp_path / "project"
    source = project / "src" / "App.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export const App = () => <main>before</main>;\n", encoding="utf-8")
    baseline = build_project_baseline(project)
    before_sha = hash_file(source)
    source.write_text("export const App = () => <main>after</main>;\n", encoding="utf-8")
    after_sha = hash_file(source)
    files = [{"path": "src/App.tsx", "beforeSha256": before_sha, "afterSha256": after_sha}]
    receipt = {
        "runId": "wuq-0123456789abcdef",
        "taskId": "task-1",
        "sessionId": "session-1",
        "findingIds": ["F-1"],
        "sourceScope": ["src/App.tsx"],
        "exclusions": ["dependencies"],
        "baselineDigest": baseline["baselineDigest"],
        "planDigest": "a" * 64,
        "patchCandidateDigest": digest_json({"sourceScope": ["src/App.tsx"], "files": files}),
        "toolchainDigest": "b" * 64,
        "verificationContextDigest": "c" * 64,
        "files": files,
    }
    kwargs = {
        "task_id": "task-1",
        "session_id": "session-1",
        "finding_ids": ["F-1"],
        "source_scope": ["src/App.tsx"],
        "exclusions": ["dependencies"],
        "run_id": "wuq-0123456789abcdef",
        "baseline": baseline,
        "plan_digest": "a" * 64,
        "toolchain_digest": "b" * 64,
        "verification_context_digest": "c" * 64,
    }
    return project, receipt, kwargs


def test_host_receipt_binds_identity_scope_and_before_after_hashes(tmp_path: Path):
    project, receipt, kwargs = _host_receipt_fixture(tmp_path)

    verified = verify_host_write_receipt(project, receipt, **kwargs)

    assert require_verified_host_write(verified) is verified
    assert verified.payload["files"] == receipt["files"]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.pop("verificationContextDigest"), "HOST_WRITE_RECEIPT_MISMATCH"),
        (lambda value: value.__setitem__("taskId", "other-task"), "HOST_WRITE_RECEIPT_MISMATCH"),
        (lambda value: value["files"][0].__setitem__("beforeSha256", "0" * 64), "HOST_WRITE_RECEIPT_MISMATCH"),
        (lambda value: value["files"][0].__setitem__("afterSha256", "0" * 64), "HOST_WRITE_RECEIPT_MISMATCH"),
    ],
)
def test_host_receipt_rejects_missing_or_mismatched_binding(tmp_path: Path, mutation, code: str):
    project, receipt, kwargs = _host_receipt_fixture(tmp_path)
    mutation(receipt)

    with pytest.raises(ContractViolation) as caught:
        verify_host_write_receipt(project, receipt, **kwargs)

    assert caught.value.code == code


def test_project_after_requires_host_receipt(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "index.html"
    source.write_text("<main>before</main>", encoding="utf-8")

    def fake_acceptance(*args, **kwargs):
        return {
            "status": "NOT_VERIFIED",
            "pageHealth": {"pageStatus": "NOT_VERIFIED"},
            "topFindings": [],
            "deliveryConclusion": "Browser intentionally omitted by trust-closure regression",
            "open": "index.html",
        }

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", fake_acceptance)
    first = run_experience_fix(
        project, tmp_path / "artifacts", request="修复当前页面", mode="FIX_AND_VERIFY",
        task_id="task-1", session_id="session-1", url="http://127.0.0.1:3000/", files=["index.html"],
    )
    run_dir = next((tmp_path / "artifacts").glob("wuq-*"))
    source.write_text("<main>after</main>", encoding="utf-8")

    with pytest.raises(ContractViolation) as caught:
        run_experience_fix(
            project, tmp_path / "artifacts", request="修复当前页面", mode="FIX_AND_VERIFY",
            task_id="task-1", session_id="session-1", url="http://127.0.0.1:3000/",
            existing_run=run_dir, after_url="http://127.0.0.1:3000/",
        )

    assert first["runId"]
    assert caught.value.code == "HOST_WRITE_RECEIPT_REQUIRED"


def test_unsupported_framework_has_no_html_success_fallback(tmp_path: Path):
    project = tmp_path / "angular-project"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"dependencies": {"@angular/core": "20.0.0"}}), encoding="utf-8"
    )
    (project / "app.ts").write_text("export class App {}", encoding="utf-8")
    plan = build_production_plan(project, {})
    output = tmp_path / "production"

    scaffold = generate_production_scaffold(plan, {}, output)

    assert plan["detectedFramework"] == "angular"
    assert plan["status"] == "FRAMEWORK_NOT_SUPPORTED"
    assert scaffold["status"] == "NOT_SUPPORTED"
    assert scaffold["reason"] == "FRAMEWORK_NOT_SUPPORTED"
    assert list(output.glob("*.html")) == []


def test_representative_persisted_outputs_do_not_leak_project_absolute_path(tmp_path: Path):
    from web_ui_quality.fix_workflow import prepare_fix_workflow

    project = tmp_path / "project"
    project.mkdir()
    source = project / "index.html"
    source.write_text("<nav>Home</nav><form><input></form><table></table>", encoding="utf-8")
    output = tmp_path / "artifacts"
    prepare_fix_workflow(project, output / "fix", files=["index.html"])
    baseline = build_project_baseline(project)
    (output / "baseline.json").parent.mkdir(parents=True, exist_ok=True)
    (output / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    persisted = [path for path in output.rglob("*") if path.is_file() and path.suffix in {".json", ".html", ".md"}]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in persisted)
    project_path = str(project.resolve())

    assert len(persisted) >= 4
    assert project_path not in combined
    assert project_path.replace("\\", "/") not in combined
    assert re.search(r"(?i)(?:^|[\"'\s])[a-z]:[\\/]", combined) is None
