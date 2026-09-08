#!/usr/bin/env python3
"""Acceptance checks retained for the 4.0.0-rc.1 product-experience surface."""
from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.__main__ import _parser, main as cli_main  # noqa: E402
from web_ui_quality.business_context import build_context_v2  # noqa: E402
from web_ui_quality.capability_registry import build_capability_registry  # noqa: E402
from web_ui_quality.error_classifier import classify_runtime_error  # noqa: E402
from web_ui_quality.fix_workflow import prepare_fix_workflow  # noqa: E402
from web_ui_quality.intent_router import route_user_intent  # noqa: E402
from web_ui_quality.quick_ui import QUICK_UI_VIEWPORTS, summarize_top_ui_issues  # noqa: E402
from web_ui_quality.release_info import KERNEL_BASE_VERSION, KERNEL_VERSION, PACKAGE_VERSION  # noqa: E402

EXPECTED_VERSION = "4.2.3"
EXPECTED_PACKAGE_VERSION = "4.3.0"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _check_identity() -> str:
    plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    if KERNEL_VERSION != EXPECTED_VERSION or KERNEL_BASE_VERSION != "4.0.0-rc.1":
        raise RuntimeError("kernel version identity differs")
    if PACKAGE_VERSION != EXPECTED_PACKAGE_VERSION or plugin.get("version") != EXPECTED_PACKAGE_VERSION:
        raise RuntimeError("package version identity differs")
    return f"{EXPECTED_PACKAGE_VERSION} / kernel {EXPECTED_VERSION}"


def _check_intent_router() -> str:
    cases = {
        "帮我看看这个页面": "inspect",
        "把刚才的问题修好": "fix",
        "把这个问题修一下": "fix",
        "优化一下页面": "fix",
        "重新设计这个后台系统": "redesign",
        "做无障碍检查": "specialized-audit",
        "修复响应式断点错位": "fix",
        "修复无障碍按钮问题": "fix",
        "修复性能问题": "fix",
        "优化这个页面的响应式布局": "fix",
        "不要改代码，只检查响应式问题": "inspect",
        "修复订单页移动端错位，不要修改登录逻辑": "fix",
        "这个页面感觉怪怪的": "inspect",
    }
    for text, expected in cases.items():
        actual = route_user_intent(text).get("intent")
        if actual != expected:
            raise RuntimeError(f"intent mismatch for {text}: {actual}")
    return "inspect/fix/redesign/specialized-audit"


def _check_help_surface() -> str:
    parser = _parser()
    help_text = parser.format_help()
    subparser_action = next(action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction")
    visible = [action.dest for action in subparser_action._choices_actions]
    if visible != ["run", "auth", "expert", "doctor"]:
        raise RuntimeError(f"normal help surface differs: {visible}")
    for command in visible:
        if command not in help_text:
            raise RuntimeError(f"public command missing from help: {command}")
    expert = io.StringIO()
    with redirect_stdout(expert):
        code = cli_main(["expert", "--compact"])
    payload = json.loads(expert.getvalue())
    if code != 0 or "commercial-upgrade" not in payload.get("commands", {}):
        raise RuntimeError("expert command catalog missing")
    return "one default entry, compatibility shortcuts, and advanced tools; internal catalog preserved"


def _check_error_recovery() -> str:
    policy = classify_runtime_error(error="net::ERR_BLOCKED_BY_ADMINISTRATOR")
    if policy.get("category") != "POLICY_BLOCKED" or policy.get("sourceCodeChangeSuggested") is not False:
        raise RuntimeError("policy block classification failed")
    text = " ".join(policy.get("recoveryActions", []))
    if "路由" in text or "源码" in text:
        raise RuntimeError("policy recovery incorrectly suggests source changes")
    http = classify_runtime_error(http_status=404)
    if http.get("category") != "HTTP_NOT_FOUND":
        raise RuntimeError("HTTP 404 classification failed")
    return "policy and HTTP root causes separated"


def _check_capability_registry() -> str:
    registry = build_capability_registry()
    required = {"pageNavigation", "pageScreenshot", "domInspection", "safeInteraction", "pythonPlaywright", "nodeCandidateValidation", "lighthouse", "axe"}
    if not required.issubset(registry):
        raise RuntimeError("capability registry incomplete")
    if registry.get("browserStatus") == "AVAILABLE" and not registry.get("pythonPlaywright", {}).get("available"):
        raise RuntimeError("browser status disagrees with Python Playwright")
    doctor = io.StringIO()
    with redirect_stdout(doctor):
        code = cli_main(["doctor", "--compact"])
    payload = json.loads(doctor.getvalue())
    if code != 0 or payload.get("browserStatus") != ("AVAILABLE" if payload.get("browser", {}).get("available") else "NOT_AVAILABLE"):
        raise RuntimeError("doctor public Browser state is contradictory")
    if "candidateBrowser" not in payload or payload.get("candidateBrowser", {}).get("runtime") != "node-playwright":
        raise RuntimeError("doctor does not separate Node candidate validation")
    return "Python/Node/providers separated without contradictory doctor state"


def _check_unknown_context() -> str:
    context = build_context_v2(None, inferred={})
    summary = context.get("summary", "")
    if "未找到足够证据" not in summary or "主要用户要围绕" in summary:
        raise RuntimeError("unknown context still produces empty pseudo-understanding")
    return "unknown stays unknown"


def _check_fix_boundary() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-fix-acceptance-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "index.html").write_text("<h1>Demo</h1>", encoding="utf-8")
        (project / "styles.css").write_text("h1{display:block}", encoding="utf-8")
        before = _tree_digest(project)
        unknown = prepare_fix_workflow(project, Path(temp) / "unknown-output")
        if unknown.get("status") != "SCOPE_NOT_CONFIRMED" or unknown.get("risk") != "UNKNOWN":
            raise RuntimeError("unproven source scope was guessed")
        result = prepare_fix_workflow(project, Path(temp) / "output", files=["index.html"])
        if result.get("status") != "PATCH_CANDIDATE_REQUIRED" or result.get("sourceProjectChanged") is not False:
            raise RuntimeError("fix preparation crossed write boundary")
        if _tree_digest(project) != before:
            raise RuntimeError("fix preparation changed source")
        for name in ("index.html", "summary.md", "fix-plan.json"):
            if not (Path(temp) / "output" / name).is_file():
                raise RuntimeError(f"fix artifact missing: {name}")
    if result.get("writeAuthorized") is not False or result.get("hostBridgeAction") != "submitPatchCandidate":
        raise RuntimeError("Runtime pretended to carry Host authority")
    return "read-only Patch Candidate handoff; unknown scope is never guessed"


def _check_viewports_and_top3() -> str:
    if QUICK_UI_VIEWPORTS != ((390, 844), (768, 1024), (1440, 900)):
        raise RuntimeError("viewport contract differs")
    records = [{
        "status": "FAIL", "viewport": {"width": 390, "height": 844},
        "errorMessage": "net::ERR_BLOCKED_BY_ADMINISTRATOR",
    }]
    top = summarize_top_ui_issues(records)
    if len(top) != 1 or top[0].get("id") != "POLICY_BLOCKED" or top[0].get("userLabel") != "暂时无法确认":
        raise RuntimeError("runtime boundary incorrectly presented as product defect")
    return "three viewports and Top 3 boundary"


def _check_redesign_defaults() -> str:
    args = _parser().parse_args(["redesign", "/tmp/project", "/tmp/output"])
    if args.directions != 3 or args.mode != "full":
        raise RuntimeError("redesign compatibility default must remain three directions")
    two = _parser().parse_args(["redesign", "/tmp/project", "/tmp/output", "--directions", "2"])
    one = _parser().parse_args(["redesign", "/tmp/project", "/tmp/output", "--directions", "1"])
    if two.directions != 2 or one.directions != 1:
        raise RuntimeError("redesign must accept one to three genuine directions")
    return "1–3 directions with compatibility default 3"


def _check_version_surfaces() -> str:
    current_files = [
        ROOT / ".codex-plugin/plugin.json",
        ROOT / "skills/audit-and-fix-web-ui/SKILL.md",
        ROOT / "runtime/python/web_ui_quality/design_gallery.py",
    ]
    for path in current_files:
        text = path.read_text(encoding="utf-8")
        if "3.7.4" in text or "3.7.5" in text:
            raise RuntimeError(f"old identity remains on current surface: {path}")
    history = ROOT / "references/history"
    if history.exists():
        raise RuntimeError("historical regression material must not ship on the current product surface")
    return "current identity isolated; historical regression payload excluded"


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks = [
        ("PX-001", _check_identity),
        ("PX-002", _check_intent_router),
        ("PX-003", _check_help_surface),
        ("PX-004", _check_error_recovery),
        ("PX-005", _check_capability_registry),
        ("PX-006", _check_unknown_context),
        ("PX-007", _check_fix_boundary),
        ("PX-008", _check_viewports_and_top3),
        ("PX-009", _check_redesign_defaults),
        ("PX-010", _check_version_surfaces),
    ]
    results = []
    failed = False
    for check_id, function in checks:
        try:
            detail = function()
            results.append({"id": check_id, "status": "PASS", "detail": detail})
        except Exception as error:
            failed = True
            results.append({"id": check_id, "status": "FAIL", "detail": f"{type(error).__name__}: {error}"})
    payload = {"status": "FAIL" if failed else "PASS", "version": EXPECTED_VERSION, "checks": results}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
