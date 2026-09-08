#!/usr/bin/env python3
"""Calculate WCAG contrast ratios for explicit opaque CSS colors."""

from __future__ import annotations

import argparse
import re


HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RGB_RE = re.compile(r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", re.I)


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    match = HEX_RE.fullmatch(value)
    if match:
        raw = match.group(1)
        if len(raw) == 3:
            raw = "".join(char * 2 for char in raw)
        return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
    match = RGB_RE.fullmatch(value)
    if match:
        channels = tuple(int(channel) for channel in match.groups())
        if all(0 <= channel <= 255 for channel in channels):
            return channels
    raise ValueError(f"Unsupported opaque color: {value}")


def luminance(color: tuple[int, int, int]) -> float:
    channels: list[float] = []
    for value in color:
        normalized = value / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate contrast for a supplied opaque color pair; this is not rendered-page proof."
    )
    parser.add_argument("foreground", help="opaque #rgb, #rrggbb or rgb(r,g,b)")
    parser.add_argument("background", help="opaque #rgb, #rrggbb or rgb(r,g,b)")
    parser.add_argument("--normal-threshold", type=float, default=4.5)
    parser.add_argument("--large-threshold", type=float, default=3.0)
    parser.add_argument("--require", choices=("none", "normal", "large"), default="none")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ratio = contrast(parse_color(args.foreground), parse_color(args.background))
    except ValueError as error:
        print(error)
        return 2
    normal_pass = ratio >= args.normal_threshold
    large_pass = ratio >= args.large_threshold
    print(f"Contrast ratio: {ratio:.2f}:1")
    print(f"Normal text ({args.normal_threshold:g}:1): {'PASS' if normal_pass else 'FAIL'}")
    print(f"Large text ({args.large_threshold:g}:1): {'PASS' if large_pass else 'FAIL'}")
    if args.require == "normal" and not normal_pass:
        return 1
    if args.require == "large" and not large_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
