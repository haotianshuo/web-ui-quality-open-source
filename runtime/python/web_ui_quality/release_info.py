"""Release identity for the Web UI Quality 4.3.0 Apache-2.0 source candidate.

Package, current kernel, protocol, evidence schema, and historical kernel-base
identity are deliberately separate.  Legacy evidence may reference the base
identity but may not upgrade itself into current 4.2.3 evidence.  The next
experimental capability line is versioned separately and remains advisory.
"""
from __future__ import annotations

import sys

PRODUCT_NAME = "web-ui-quality"
PLUGIN_VERSION = "4.3.0"
PACKAGE_VERSION = PLUGIN_VERSION
PACKAGE_STAGE = "4.3.0-open-source"
KERNEL_VERSION = "4.2.3"
KERNEL_BASE_VERSION = "4.0.0-rc.1"
LEGACY_PRODUCT_VERSION = KERNEL_BASE_VERSION
PROTOCOL_VERSION = "3.0"
RECEIPT_PROTOCOL_VERSION = "3.0"
EVIDENCE_SCHEMA_VERSION = "3.0"
CONTRACT_VERSION = "3.0"
WORKFLOW_CONTRACT_VERSION = "5"
RELEASE_STAGE = "4.3.0-open-source"
# The shadow archive used for this migration is kept outside the public
# package identity. It must not make a stable public release mutable.
EXPERIMENTAL_VERSION = "NOT_INCLUDED"
EXPERIMENTAL_STAGE = "NOT_INCLUDED"


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError, LookupError):
            continue


def release_identity() -> dict[str, str]:
    """Current package identity with a separately versioned 4.2.3 Trust Kernel."""
    return {
        "name": PRODUCT_NAME,
        "pluginVersion": PLUGIN_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelVersion": KERNEL_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "evidenceSchemaVersion": EVIDENCE_SCHEMA_VERSION,
        "contractVersion": CONTRACT_VERSION,
        "workflowContractVersion": WORKFLOW_CONTRACT_VERSION,
        "stage": RELEASE_STAGE,
    }


def legacy_kernel_identity() -> dict[str, str]:
    """Historical identity only; never sufficient for a 4.2.3 VERIFIED claim."""
    return {
        "name": PRODUCT_NAME,
        "legacyProductVersion": LEGACY_PRODUCT_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
    }


def package_identity() -> dict[str, str]:
    return {
        "name": PRODUCT_NAME,
        "pluginVersion": PLUGIN_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "stage": PACKAGE_STAGE,
        "kernelVersion": KERNEL_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "evidenceSchemaVersion": EVIDENCE_SCHEMA_VERSION,
    }


def experimental_identity() -> dict[str, str]:
    """Identity for the additive 4.4 alpha Shadow/Advisory track."""
    return {
        "name": PRODUCT_NAME,
        "experimentalVersion": EXPERIMENTAL_VERSION,
        "stage": EXPERIMENTAL_STAGE,
        "kernelVersion": KERNEL_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "authorityMode": "SHADOW_ADVISORY_ONLY",
    }
