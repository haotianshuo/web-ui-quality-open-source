#!/usr/bin/env python3
"""Explicit 4.2.3 trust-kernel public acceptance entry point.

Current kernel acceptance; kernelBaseVersion remains separately recorded for lineage.
"""
from __future__ import annotations
from public_acceptance import main
if __name__ == "__main__":
    raise SystemExit(main())
