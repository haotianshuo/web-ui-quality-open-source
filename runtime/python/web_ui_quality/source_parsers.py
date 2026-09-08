"""Trusted, local-only source parsers.

A readable text file is not a syntax pass.  Unsupported languages remain
NOT_VERIFIED instead of being promoted to deterministic correctness evidence.
"""
from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


class _StrictHTMLParser(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self._VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing tag </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            self.errors.append(f"misnested closing tag </{tag}>")
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"closing tag </{tag}> has no matching start tag")


def _parse_css(text: str) -> None:
    """Conservative CSS syntax check for braces, comments and declarations."""
    without_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    if without_comments.count("{") != without_comments.count("}"):
        raise ValueError("unbalanced CSS braces")
    depth = 0
    block_start = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(without_comments):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "{":
            if depth == 0:
                selector = without_comments[block_start:index].strip()
                if not selector:
                    raise ValueError("empty CSS selector")
            depth += 1
            block_start = index + 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("unexpected CSS closing brace")
            body = without_comments[block_start:index].strip()
            if depth == 0 and body:
                for declaration in [part.strip() for part in body.split(";") if part.strip()]:
                    if declaration.startswith("@"):
                        continue
                    if ":" not in declaration:
                        raise ValueError(f"CSS declaration missing colon: {declaration[:80]}")
                    name, value = declaration.split(":", 1)
                    if not name.strip() or not value.strip():
                        raise ValueError("CSS declaration has empty property or value")
            block_start = index + 1
    if quote:
        raise ValueError("unterminated CSS string")


def parse_source(path: Path, relative_path: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return {"file": relative_path, "status": "NOT_VERIFIED", "checker": "utf8-read", "reason": type(error).__name__, "syntaxVerified": False}
    if "\x00" in text:
        return {"file": relative_path, "status": "FAIL", "checker": "utf8-read", "reason": "NUL byte", "syntaxVerified": False}
    try:
        if suffix == ".py":
            ast.parse(text, filename=relative_path)
            checker = "python-ast"
        elif suffix == ".json":
            json.loads(text)
            checker = "json-parser"
        elif suffix == ".toml" and tomllib is not None:
            tomllib.loads(text)
            checker = "python-tomllib"
        elif suffix in {".html", ".htm"}:
            parser = _StrictHTMLParser()
            parser.feed(text)
            parser.close()
            if parser.stack:
                parser.errors.append("unclosed tags: " + ", ".join(parser.stack[-8:]))
            if parser.errors:
                raise ValueError("; ".join(parser.errors[:8]))
            checker = "builtin-html-parser"
        elif suffix == ".css":
            _parse_css(text)
            checker = "builtin-css-parser"
        else:
            return {
                "file": relative_path,
                "status": "NOT_VERIFIED",
                "checker": "text-readable-only",
                "reason": f"No trusted local parser is registered for {suffix or 'this file type'}.",
                "textReadable": True,
                "syntaxVerified": False,
                "claimBoundary": "Readable UTF-8 text is not syntax or semantic verification.",
            }
        return {"file": relative_path, "status": "PASS", "checker": checker, "textReadable": True, "syntaxVerified": True}
    except Exception as error:
        return {"file": relative_path, "status": "FAIL", "checker": "trusted-parser", "reason": f"{type(error).__name__}: {str(error)[:400]}", "textReadable": True, "syntaxVerified": False}


__all__ = ["parse_source"]
