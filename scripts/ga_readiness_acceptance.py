#!/usr/bin/env python3
"""Package-local 4.2.3 readiness gate.

This gate proves local package/kernel/protocol identity and honesty boundaries.
It does not prove native-Windows or real Codex Host qualification.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.phase1_shadow import adaptive_runtime_status  # noqa: E402
from web_ui_quality.release_info import (  # noqa: E402
    EVIDENCE_SCHEMA_VERSION,
    KERNEL_BASE_VERSION,
    KERNEL_VERSION,
    PACKAGE_STAGE,
    PACKAGE_VERSION,
    PROTOCOL_VERSION,
    RECEIPT_PROTOCOL_VERSION,
)


def check(cid: str, ok: bool, detail: object) -> dict[str, object]:
    return {"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail}


def main() -> int:
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
    composite = json.loads((ROOT / "COMPOSITE-RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    limitations = (ROOT / "KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
    declared = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    shadow = adaptive_runtime_status()
    checks = [
        check("GA422-001", PACKAGE_VERSION == "4.3.0" and plugin.get("version") == PACKAGE_VERSION and declared and declared.group(1) == PACKAGE_VERSION, {"runtime": PACKAGE_VERSION, "plugin": plugin.get("version"), "pyproject": declared.group(1) if declared else None}),
        check("GA422-001A", PACKAGE_STAGE == "4.3.0-stable" and release.get("packageStage") == PACKAGE_STAGE and composite.get("packageStage") == PACKAGE_STAGE, {"packageStage": PACKAGE_STAGE, "release": release.get("packageStage"), "composite": composite.get("packageStage")}),
        check("GA422-002", KERNEL_VERSION == "4.2.3" and KERNEL_BASE_VERSION == "4.0.0-rc.1", {"kernelVersion": KERNEL_VERSION, "kernelBaseVersion": KERNEL_BASE_VERSION}),
        check("GA420-003", PROTOCOL_VERSION == "3.0" and RECEIPT_PROTOCOL_VERSION == "3.0" and EVIDENCE_SCHEMA_VERSION == "3.0", {"protocolVersion": PROTOCOL_VERSION, "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION, "evidenceSchemaVersion": EVIDENCE_SCHEMA_VERSION}),
        check("GA420-004", release.get("packageVersion") == PACKAGE_VERSION and release.get("kernelVersion") == KERNEL_VERSION and release.get("kernelBaseVersion") == KERNEL_BASE_VERSION, {k: release.get(k) for k in ("packageVersion", "kernelVersion", "kernelBaseVersion")}),
        check("GA420-005", composite.get("packageVersion") == PACKAGE_VERSION and composite.get("realCodexHostQualification") == "NOT_MEASURED" and composite.get("nativeWindowsQualification") == "NOT_MEASURED", {"packageVersion": composite.get("packageVersion"), "realCodexHostQualification": composite.get("realCodexHostQualification"), "nativeWindowsQualification": composite.get("nativeWindowsQualification")}),
        check("GA420-006", composite.get("v5Included") is False and composite.get("adaptiveGuidanceActive") is False and composite.get("adaptiveExplorationActive") is False, {"v5Included": composite.get("v5Included"), "adaptiveGuidanceActive": composite.get("adaptiveGuidanceActive"), "adaptiveExplorationActive": composite.get("adaptiveExplorationActive")}),
        check("GA420-007", shadow.get("authoritative") is False and shadow.get("mayChangeWriteAuthority") is False and shadow.get("maySetClaimStatus") is False and shadow.get("mayChangeGuidance") is False and shadow.get("mayChangeExploration") is False, shadow),
        check("GA420-008", "Real Codex Host qualification" in readme and "NOT_MEASURED" in readme and "v5 Ranking = NOT_INCLUDED" in readme, "README current honesty boundary"),
        check("GA420-009", "Real Codex Host pre-write enforcement remains `NOT_MEASURED`" in limitations, "Known limitations preserve Host boundary"),
        check("GA420-010", "packageArtifactDigest" not in release and isinstance(release.get("packageTreeDigest"), str) and len(release.get("packageTreeDigest")) == 64, {"packageTreeDigest": release.get("packageTreeDigest"), "artifactDigestSelfReferenced": "packageArtifactDigest" in release}),
    ]
    failed = [row for row in checks if row["status"] != "PASS"]
    outcome = {
        "status": "FAIL" if failed else "PASS",
        "scope": "WUQ_4_2_LOCAL_READINESS",
        "packageVersion": PACKAGE_VERSION,
        "packageStage": PACKAGE_STAGE,
        "kernelVersion": KERNEL_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "realCodexHostQualification": "NOT_MEASURED",
        "nativeWindowsQualification": "NOT_MEASURED",
        "checks": checks,
        "claimBoundary": "Local readiness is not native-Windows qualification, real Host attestation, market validation, or proof of zero defects.",
    }
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
