#!/usr/bin/env python3
"""Inventory scoped CSS design values and token usage using the standard library."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator


GROUPS = {
    "colors": {"color", "background", "background-color", "border-color", "outline-color", "fill", "stroke"},
    "font_sizes": {"font-size"},
    "font_weights": {"font-weight"},
    "line_heights": {"line-height"},
    "radii": {"border-radius"},
    "gaps": {"gap", "row-gap", "column-gap"},
    "spacing": {
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    },
}
PROPERTY_TO_GROUP = {prop: group for group, props in GROUPS.items() for prop in props}
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
BLOCK_RE = re.compile(r"\{([^{}]*)\}", re.S)
DECL_RE = re.compile(r"(?:^|;)\s*([\w-]+)\s*:\s*([^;]+)")
VAR_RE = re.compile(r"var\(\s*(--[\w-]+)")
PX_RE = re.compile(r"^(-?(?:\d+(?:\.\d+)?|\.\d+))px$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory CSS values in an explicit file/directory scope")
    parser.add_argument("paths", nargs="+", help="CSS files or directories")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--sources", type=int, default=3)
    parser.add_argument("--near-px", type=float, default=1.0)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    return parser.parse_args()


def is_excluded(path: Path, patterns: list[str]) -> bool:
    value = path.as_posix()
    return any(fnmatch.fnmatch(value, pattern) or fnmatch.fnmatch(path.name, pattern) for pattern in patterns)


def collect_files(raw_paths: list[str], patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in raw_paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and path.suffix.casefold() == ".css" and not is_excluded(path, patterns):
            files.add(path)
        elif path.is_dir():
            files.update(
                child.resolve() for child in path.rglob("*.css")
                if child.is_file() and not is_excluded(child, patterns)
            )
        else:
            raise SystemExit(f"CSS path not found: {path}")
    if not files:
        raise SystemExit("No CSS files found in the declared scope")
    return sorted(files)


def declarations(css: str) -> Iterator[tuple[str, str, int]]:
    clean = COMMENT_RE.sub("", css)
    for block in BLOCK_RE.finditer(clean):
        content = block.group(1)
        base_line = clean.count("\n", 0, block.start(1)) + 1
        for match in DECL_RE.finditer(content):
            line = base_line + content.count("\n", 0, match.start(1))
            yield match.group(1).casefold(), re.sub(r"\s+", " ", match.group(2).strip().casefold()), line


def clusters(counter: Counter[str], distance: float) -> list[list[str]]:
    scalar: list[tuple[float, str]] = []
    for value in counter:
        match = PX_RE.fullmatch(value)
        if match:
            scalar.append((float(match.group(1)), value))
    scalar.sort()
    groups: list[list[tuple[float, str]]] = []
    for item in scalar:
        if groups and item[0] - groups[-1][-1][0] <= distance:
            groups[-1].append(item)
        else:
            groups.append([item])
    return [[value for _, value in group] for group in groups if len(group) > 1]


def inventory(files: list[Path], top: int, source_limit: int, near_px: float) -> dict[str, Any]:
    values = {name: Counter() for name in GROUPS}
    sources: dict[str, dict[str, list[dict[str, Any]]]] = {
        name: defaultdict(list) for name in GROUPS
    }
    tokenized = Counter()
    literals = Counter()
    custom = Counter()
    references = Counter()
    total = 0

    for path in files:
        css = path.read_text(encoding="utf-8")
        for prop, value, line in declarations(css):
            total += 1
            if prop.startswith("--"):
                custom[prop] += 1
            for name in VAR_RE.findall(value):
                references[name] += 1
            group = PROPERTY_TO_GROUP.get(prop)
            if group is None:
                continue
            values[group][value] += 1
            source = {"file": str(path), "line": line}
            if source not in sources[group][value]:
                sources[group][value].append(source)
            if VAR_RE.search(value):
                tokenized[group] += 1
            else:
                literals[group] += 1

    grouped: dict[str, Any] = {}
    for name, counter in values.items():
        common = counter.most_common(max(0, top))
        grouped[name] = {
            "declarations": sum(counter.values()),
            "uniqueValues": len(counter),
            "oneOffValues": sum(1 for count in counter.values() if count == 1),
            "tokenizedDeclarations": tokenized[name],
            "literalDeclarations": literals[name],
            "topValues": common,
            "topValueSources": {
                value: sources[name][value][:max(0, source_limit)] for value, _ in common
            },
            "nearPxClusters": clusters(counter, max(0.0, near_px)),
        }
    return {
        "parser": "stdlib-fallback",
        "files": [str(path) for path in files],
        "fileCount": len(files),
        "declarations": total,
        "customProperties": {"unique": len(custom), "definitions": sum(custom.values()), "top": custom.most_common(max(0, top))},
        "variableReferences": {"unique": len(references), "references": sum(references.values()), "top": references.most_common(max(0, top))},
        "groups": grouped,
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"Parser: {result['parser']}",
        f"CSS files: {result['fileCount']}",
        f"Declarations: {result['declarations']}",
        f"Custom properties: {result['customProperties']['unique']} unique / {result['customProperties']['definitions']} definitions",
        f"var() references: {result['variableReferences']['unique']} unique / {result['variableReferences']['references']} uses",
    ]
    for name, stats in result["groups"].items():
        lines.append("")
        lines.append(
            f"[{name}] declarations={stats['declarations']} unique={stats['uniqueValues']} "
            f"one_off={stats['oneOffValues']} tokenized={stats['tokenizedDeclarations']} "
            f"literal={stats['literalDeclarations']}"
        )
        for value, count in stats["topValues"]:
            locations = ", ".join(
                f"{Path(item['file']).name}:{item['line']}"
                for item in stats["topValueSources"].get(value, [])
            )
            lines.append(f"  {count:>5}  {value}  [{locations}]")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = inventory(
        collect_files(args.paths, args.exclude), args.top, args.sources, args.near_px
    )
    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
