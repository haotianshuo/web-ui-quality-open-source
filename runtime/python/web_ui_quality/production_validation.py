"""Local/staging Browser acceptance for an isolated transformation workspace."""
from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from html import escape
import json
import os
from pathlib import Path
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading
from typing import Any, Iterator, Mapping, Sequence

from .release_info import release_identity
from .visual_diff import compare_images
from .browser_locator import resolve_browser_executable


VIEWPORTS = (
    {"id": "desktop", "width": 1440, "height": 900},
    {"id": "tablet", "width": 768, "height": 1024},
    {"id": "mobile", "width": 390, "height": 844},
)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _serve(directory: Path) -> Iterator[str]:
    handler = partial(_QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _entry(root: Path) -> str | None:
    direct = root / "index.html"
    if direct.is_file():
        return "index.html"
    candidates = sorted(root.rglob("index.html"))
    return candidates[0].relative_to(root).as_posix() if candidates else None


def _node_path() -> str:
    values = []
    for key in ("NODE_PATH", "CODEX_PRIMARY_RUNTIME_NODE_MODULES"):
        value = os.environ.get(key)
        if value:
            values.extend(part for part in value.split(os.pathsep) if part)
    return os.pathsep.join(dict.fromkeys(values))


def browser_runtime_capability(browser_executable: str | Path | None = None) -> dict[str, Any]:
    """Inspect the same Node Playwright path used by transformation validation."""
    node = shutil.which("node")
    runner = Path(__file__).resolve().parent / "browser_runner.cjs"
    if node is None or not runner.is_file():
        return {
            "available": False,
            "runtime": "node-playwright",
            "reasonCode": "NODE_RUNTIME_OR_BROWSER_RUNNER_MISSING",
            "reason": "Node or the bundled Browser runner is unavailable.",
            "repair": "Install Node.js and reinstall web-ui-quality.",
        }
    env = dict(os.environ)
    node_path = _node_path()
    if node_path:
        env["NODE_PATH"] = node_path
    probe = subprocess.run(
        [node, "-e", "const fs=require('fs');try{const p=require('playwright');process.stdout.write(JSON.stringify({module:true,executable:p.chromium.executablePath()}))}catch(e){process.stdout.write(JSON.stringify({module:false,error:e.name}))}"],
        env=env,
        text=True,
        capture_output=True,
    )
    try:
        payload = json.loads(probe.stdout) if probe.stdout else {}
    except json.JSONDecodeError:
        payload = {}
    module_available = bool(payload.get("module"))
    bundled = Path(str(payload.get("executable"))).expanduser() if payload.get("executable") else None
    if browser_executable:
        decision = resolve_browser_executable("chromium", explicit=browser_executable)
    else:
        # The selected executable is passed to both the Node runner and the
        # Python Playwright workflow. Prefer an installed desktop browser when
        # available because a managed binary can be present yet fail to spawn
        # under the local OS policy. Keep the managed binary as a fallback for
        # hosts without a desktop Chromium-family install.
        desktop = resolve_browser_executable("chromium")
        if desktop.get("available"):
            decision = desktop
        elif bundled and bundled.is_file():
            decision = {
                "available": True,
                "executable": str(bundled),
                "source": "playwright",
                "reason": None,
                "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
                "resolutionTrace": list(desktop.get("resolutionTrace") or []) + ["playwright"],
            }
        else:
            decision = desktop
    available = bool(module_available and decision.get("available"))
    if available:
        reason_code = "CAPABILITY_AVAILABLE"
    elif not module_available:
        reason_code = "NODE_PLAYWRIGHT_MODULE_MISSING"
    elif decision.get("reasonCode") == "EXPLICIT_BROWSER_NOT_FOUND":
        reason_code = "EXPLICIT_BROWSER_NOT_FOUND"
    else:
        reason_code = "NODE_BROWSER_EXECUTABLE_MISSING"
    return {
        "available": available,
        "runtime": "node-playwright",
        "node": node,
        "moduleAvailable": module_available,
        "browser": "chromium" if available else None,
        "executable": decision.get("executable"),
        "executableSource": decision.get("source"),
        "reasonCode": reason_code,
        "resolutionTrace": list(decision.get("resolutionTrace") or []),
        "reason": None if available else "Node Playwright is missing or no Chrome/Edge/Chromium executable is available.",
        "repair": None if available else "Run `npm install playwright`; Web UI Quality will auto-detect Chrome/Edge/Chromium, or pass --browser-executable.",
    }


def _validation_html(report: Mapping[str, Any]) -> str:
    cards = "".join(
        f"<article><span>{escape(str(key))}</span><b>{escape(str(value))}</b></article>"
        for key, value in report.get("readiness", {}).items()
    )
    records = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(str(item.get("label"))), escape(str(item.get("viewport", {}).get("id"))),
            escape(str(item.get("status"))), "YES" if item.get("horizontalOverflow") else "NO",
            escape(str(item.get("screenshotRef", ""))),
        )
        for item in report.get("records", [])
        if isinstance(item, Mapping)
    )
    diffs = "".join(
        f"<article><span>{escape(str(item.get('viewport', {}).get('id')))}</span><b>{escape(str(item.get('status')))}</b><small>{escape(str(item.get('changedPixelRatio')))}</small></article>"
        for item in report.get("visualDiff", [])
        if isinstance(item, Mapping)
    )
    status = escape(str(report.get("status")))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Production validation · {status}</title><style>
:root{{--ink:#17211d;--muted:#637068;--line:#d9e4de;--paper:#f3f7f5;--brand:#146048;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:1120px;margin:auto;padding:40px 20px 80px}}header{{background:var(--ink);color:white;padding:42px;border-radius:24px}}h1{{font-size:clamp(36px,6vw,64px);margin:8px 0}}header p{{color:#bed0c7;line-height:1.6}}.status{{background:#cff2dd;color:#0e503a;padding:7px 10px;border-radius:99px;font-weight:800;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}article{{background:white;border:1px solid var(--line);border-radius:16px;padding:16px}}article span,article small{{display:block;color:var(--muted);font-size:12px}}article b{{display:block;margin:9px 0}}section{{background:white;border:1px solid var(--line);border-radius:18px;overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:720px}}th,td{{padding:13px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}}@media(max-width:720px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main><header><span class="status">{status}</span><h1>真实 Browser 验收</h1><p>Before 与 After 在相同 Chromium 条件下分别打开，覆盖桌面、平板和手机，并执行安全关键旅程。</p></header><div class="grid">{cards}</div><section><table><thead><tr><th>页面</th><th>视口</th><th>结果</th><th>横向溢出</th><th>截图</th></tr></thead><tbody>{records}</tbody></table></section><h2>Visual diff</h2><div class="grid">{diffs}</div></main></body></html>"""


def validate_transformation(
    before_dir: str | Path,
    after_dir: str | Path,
    output_dir: str | Path,
    *,
    browser_executable: str | Path | None = None,
    journey: Sequence[Mapping[str, Any]] = (),
    single_process: bool = False,
) -> dict[str, Any]:
    before = Path(before_dir).expanduser().resolve()
    after = Path(after_dir).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    entry = _entry(before)
    if entry is None or not (after / entry).is_file():
        report = {
            "schemaVersion": "1", "generator": release_identity(), "status": "NOT_APPLICABLE",
            "reason": "Before and After do not expose the same static index.html entry.",
            "readiness": {"screenshots": "NOT_RUN", "journey": "NOT_RUN", "visualDiff": "NOT_RUN"},
        }
        (output / "production-validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    capability = browser_runtime_capability(browser_executable)
    if not capability.get("available"):
        report = {
            "schemaVersion": "1", "generator": release_identity(), "status": "NOT_AVAILABLE",
            "reason": capability.get("reason"), "repair": capability.get("repair"),
            "browserCapability": capability,
            "readiness": {"screenshots": "NOT_RUN", "journey": "NOT_RUN", "visualDiff": "NOT_RUN"},
        }
        (output / "production-validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    node = shutil.which("node")
    packaged_runner = Path(__file__).resolve().parent / "browser_runner.cjs"
    source_runner = Path(__file__).resolve().parents[3] / "scripts" / "run_browser_validation.cjs"
    runner = packaged_runner if packaged_runner.is_file() else source_runner
    if node is None or not runner.is_file():
        report = {
            "schemaVersion": "1", "generator": release_identity(), "status": "NOT_AVAILABLE",
            "reason": "Node or bundled Browser runner is unavailable.",
            "readiness": {"screenshots": "NOT_RUN", "journey": "NOT_RUN", "visualDiff": "NOT_RUN"},
        }
        (output / "production-validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    with _serve(before) as before_origin, _serve(after) as after_origin:
        config = {
            "beforeUrl": f"{before_origin}/{entry}",
            "afterUrl": f"{after_origin}/{entry}",
            "outputDir": str(output),
            "browserExecutable": capability.get("executable"),
            "singleProcess": single_process,
            "viewports": list(VIEWPORTS),
            "journey": [dict(item) for item in journey],
        }
        config_path = output / "browser-run-config.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        env = dict(os.environ)
        node_path = _node_path()
        if node_path:
            env["NODE_PATH"] = node_path
        completed = subprocess.run([node, str(runner), str(config_path)], env=env, text=True, capture_output=True)
    raw_path = output / "node-browser-report.json"
    if not raw_path.is_file():
        report = {
            "schemaVersion": "1", "generator": release_identity(), "status": "NOT_AVAILABLE" if completed.returncode == 2 else "FAIL",
            "reason": completed.stderr.strip()[:1000] or "Browser runner did not produce a report.",
            "readiness": {"screenshots": "NOT_RUN", "journey": "NOT_RUN", "visualDiff": "NOT_RUN"},
        }
        (output / "production-validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    visual_results = []
    for viewport in VIEWPORTS:
        before_image = output / "screenshots" / "before" / f"{viewport['id']}.png"
        after_image = output / "screenshots" / "after" / f"{viewport['id']}.png"
        diff_path = output / "screenshots" / "diff" / f"{viewport['id']}.png"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        result = compare_images(before_image, after_image, diff_path=diff_path)
        result["viewport"] = dict(viewport)
        if diff_path.is_file():
            result["diffRef"] = f"screenshots/diff/{viewport['id']}.png"
        visual_results.append(result)
    computed = [item for item in visual_results if item.get("status") == "COMPUTED"]
    visual_changed = bool(computed) and all(float(item.get("changedPixelRatio", 0)) > 0.001 for item in computed)
    browser_status = raw.get("status")
    if browser_status == "FAIL":
        final_status = "FAIL"
    elif not computed:
        final_status = "PASS_WITH_WARNINGS"
    elif not visual_changed:
        final_status = "FAIL"
    else:
        final_status = browser_status
    report = {
        **raw,
        "generator": release_identity(),
        "status": final_status,
        "scope": "LOCAL_OR_STAGING_TRANSFORMATION",
        "visualDiff": visual_results,
        "visualChangeObserved": visual_changed,
        "readiness": {
            "screenshots": "PASS" if all(item.get("status") != "FAIL" for item in raw.get("records", [])) else "FAIL",
            "journey": "PASS" if raw.get("journey") and all(item.get("status") == "PASS" for item in raw.get("journey", [])) else "NOT_RUN" if not raw.get("journey") else "FAIL",
            "visualDiff": "PASS" if visual_changed else "NOT_AVAILABLE" if not computed else "FAIL",
            "production": "READ_ONLY_NOT_RUN",
        },
        "claimBoundary": "Local/staging Browser evidence does not authorize production mutation or establish a business outcome.",
    }
    report_path = output / "production-validation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "production-validation-report.html").write_text(_validation_html(report), encoding="utf-8")
    return report
