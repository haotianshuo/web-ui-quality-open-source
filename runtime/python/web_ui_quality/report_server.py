"""Serve a generated review workbench on localhost without external services."""
from __future__ import annotations

import contextlib
import http.server
import socket
import socketserver
import webbrowser
from pathlib import Path
from typing import Any


def _free_port(host: str = "127.0.0.1") -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def serve_report(report_dir: str | Path, *, host: str = "127.0.0.1", port: int = 0, open_browser: bool = False) -> dict[str, Any]:
    root = Path(report_dir).expanduser().resolve(strict=True)
    if root.is_file():
        root = root.parent
    if not (root / "index.html").is_file():
        raise FileNotFoundError(f"index.html not found under {root}")
    selected_port = int(port or _free_port(host))
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=str(root), **kwargs)
    with socketserver.TCPServer((host, selected_port), handler) as server:
        url = f"http://{host}:{selected_port}/"
        print(f"Web UI Quality workbench: {url}", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return {"status": "STOPPED", "url": url, "directory": str(root)}
