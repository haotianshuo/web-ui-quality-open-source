#!/usr/bin/env python3
"""Run the current product-experience redesign workflow through the packaged runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.commercial_upgrade import run_commercial_upgrade  # noqa: E402
from web_ui_quality.workflow_policy import bind_trusted_workflow_approval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Northstar CRM implementation, Browser, and outcome artifacts")
    parser.add_argument("--output", type=Path, help="new or empty directory outside this demo source")
    parser.add_argument("--browser-executable", type=Path, help="Chromium/Chrome executable used by Playwright")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    output = args.output.expanduser().resolve() if args.output else Path(tempfile.mkdtemp(prefix="web-ui-quality-4.0.0a4-"))
    output.parent.mkdir(parents=True, exist_ok=True)
    confirmation = output.parent / f"{output.name}-current-conversation-approval.json"
    confirmation.write_text(json.dumps({
        "schemaVersion": "2",
        "action": "confirm-understanding",
        "answers": {},
        "source": "system-understanding-response",
        "requiresCurrentConversationApproval": True,
        "approvalReceipt": None,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Output: {output}", file=sys.stderr)
    packet = json.loads(confirmation.read_text(encoding="utf-8"))
    trusted = bind_trusted_workflow_approval(
        packet,
        evidence_ref="current-conversation:commercial-demo-full-upgrade",
        evidence_resolver=lambda reference: reference == "current-conversation:commercial-demo-full-upgrade",
        scope="FULL",
        requested_mode="full",
        statement="演示用户确认系统理解正确，可以生成隔离候选。",
    )
    result = run_commercial_upgrade(
        HERE,
        output,
        business_context=json.loads((HERE / "business-context.json").read_text(encoding="utf-8")),
        product_name="Northstar Customer Operations",
        product_type="crm",
        baseline_events=HERE / "baseline-events.csv",
        after_events=HERE / "after-events.csv",
        browser_executable=args.browser_executable.expanduser().resolve() if args.browser_executable else None,
        mode="full",
        product_confirmation=packet,
        approval_receipt=trusted,
    )
    if args.compact:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"COMMERCIAL_WORKFLOW_PASS", "COMMERCIAL_WORKFLOW_NOT_VERIFIED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
