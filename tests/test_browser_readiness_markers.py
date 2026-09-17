from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlunsplit

import pytest

from web_ui_quality.browser_locator import resolve_browser_executable
from web_ui_quality.quick_ui import run_quick_ui


class _PageHandler(BaseHTTPRequestHandler):
    page = b""

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.page)))
        self.end_headers()
        self.wfile.write(self.page)

    def log_message(self, *_args: object) -> None:
        return


def _run_local_page(html: str, output_dir: object) -> dict[str, object]:
    pytest.importorskip("playwright.sync_api")
    if not resolve_browser_executable("chromium").get("available"):
        pytest.skip("No local Chromium-compatible executable is available")
    _PageHandler.page = html.encode("utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        url = urlunsplit(("http", f"{host}:{port}", "/", "", ""))
        return run_quick_ui(url, output_dir=output_dir, viewports=[(1440, 900)])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_hidden_skeleton_marker_does_not_block_ready_page(tmp_path) -> None:
    report = _run_local_page(
        """
        <main><h1>Public dashboard</h1><p>Stable content is visible.</p>
          <div class="skeleton" style="display:none;width:300px;height:40px"></div>
        </main>
        """,
        tmp_path,
    )

    record = report["records"][0]
    assert record["readiness"]["skeletonCount"] == 0
    assert "PAGE-DATA-NOT-READY" not in {item["id"] for item in report["topIssues"]}


def test_visible_skeleton_marker_remains_a_readiness_boundary(tmp_path) -> None:
    report = _run_local_page(
        """
        <main><h1>Loading dashboard</h1><p>Loading...</p>
          <div class="skeleton" style="width:300px;height:40px">Loading</div>
        </main>
        """,
        tmp_path,
    )

    record = report["records"][0]
    assert record["readiness"]["skeletonCount"] == 1
    assert "PAGE-DATA-NOT-READY" in {item["id"] for item in report["topIssues"]}


@pytest.mark.parametrize(
    "marker",
    (
        '<div class="skeleton" hidden style="width:300px;height:40px"></div>',
        '<div class="skeleton" aria-hidden="true" style="width:300px;height:40px"></div>',
        '<div class="skeleton" style="width:0;height:40px"></div>',
        '<div class="skeleton" style="position:absolute;left:-10000px;width:300px;height:40px"></div>',
        '<div class="skeleton" style="opacity:0;width:300px;height:40px"></div>',
        '<div class="skeleton" style="clip-path:inset(100%);width:300px;height:40px"></div>',
        '<div style="display:none"><div class="skeleton" style="width:300px;height:40px"></div></div>',
    ),
)
def test_non_visible_skeleton_markers_do_not_block_ready_page(tmp_path, marker: str) -> None:
    report = _run_local_page(
        f"""
        <main><h1>Public dashboard</h1><p>Stable content is visible.</p>{marker}</main>
        """,
        tmp_path,
    )

    record = report["records"][0]
    assert record["readiness"]["skeletonCount"] == 0
    assert record["readiness"]["status"] == "READY"
    assert "PAGE-DATA-NOT-READY" not in {item["id"] for item in report["topIssues"]}


def test_runtime_error_remains_a_runtime_failure_when_skeleton_is_hidden(tmp_path) -> None:
    report = _run_local_page(
        """
        <main><h1>Public dashboard</h1><p>Stable content is visible.</p>
          <div class="skeleton" aria-hidden="true" style="width:300px;height:40px"></div>
        </main>
        <script>setTimeout(() => { throw new Error('task18 runtime sentinel'); }, 20);</script>
        """,
        tmp_path,
    )

    record = report["records"][0]
    assert record["readiness"]["skeletonCount"] == 0
    assert record["readiness"]["status"] == "RUNTIME_BROKEN"
    assert "PAGE-RUNTIME-BROKEN" in {item["id"] for item in report["topIssues"]}
