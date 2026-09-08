#!/usr/bin/env python3
"""Re-run the shipped Phase-0 contract evidence suite from the package."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "docs" / "phase1" / "phase0-contract-suite.zip"


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--compact", action="store_true")
    args=parser.parse_args()
    if not SUITE.is_file():
        result={"status":"FAILED","reason":"PHASE0_SUITE_MISSING","passed":0,"failed":None}
        print(json.dumps(result,separators=(",",":")) if args.compact else json.dumps(result,indent=2))
        return 1
    with tempfile.TemporaryDirectory(prefix="wuq-phase0-suite-") as td:
        with zipfile.ZipFile(SUITE) as z:
            z.extractall(td)
        env=dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"]="1"
        proc=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=td,env=env,text=True,encoding="utf-8",errors="replace",capture_output=True)
        summary=(proc.stdout+"\n"+proc.stderr).strip()
        passed=46 if proc.returncode==0 and "46 passed" in summary else None
        result={
            "status":"PASS" if passed==46 else "FAILED",
            "evidence":"PACKAGE_SELF_REPRODUCIBLE",
            "expectedPassed":46,
            "passed":passed,
            "returnCode":proc.returncode,
            "suiteSha256":__import__('hashlib').sha256(SUITE.read_bytes()).hexdigest(),
            "summary":summary[-2000:],
        }
        print(json.dumps(result,ensure_ascii=False,separators=(",",":")) if args.compact else json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
