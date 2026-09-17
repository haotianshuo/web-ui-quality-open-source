"""Release identity for the Web UI Quality 4.3.1 Apache-2.0 source release.

Package, current kernel, protocol, evidence schema, and historical kernel-base
identity are deliberately separate.  Legacy evidence may reference the base
identity but may not upgrade itself into current 4.2.3 evidence.  The next
experimental capability line is versioned separately and remains advisory.
"""
from __future__ import annotations

import sys

PRODUCT_NAME = "web-ui-quality"
PLUGIN_VERSION = "4.3.1"
PACKAGE_VERSION = PLUGIN_VERSION
PACKAGE_STAGE = "4.3.1-open-source"
KERNEL_VERSION = "4.2.3"
KERNEL_BASE_VERSION = "4.0.0-rc.1"
LEGACY_PRODUCT_VERSION = KERNEL_BASE_VERSION
PROTOCOL_VERSION = "3.0"
RECEIPT_PROTOCOL_VERSION = "3.0"
EVIDENCE_SCHEMA_VERSION = "3.0"
CONTRACT_VERSION = "3.0"
WORKFLOW_CONTRACT_VERSION = "5"
RELEASE_STAGE = "4.3.1-open-source"
# Stable publication identity; qualification and GA status remain separate.
PUBLICATION_STATUS = "NORMAL_RELEASE"
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


def installation_identity() -> dict[str, str]:
    """Report which installation is actually running.

    Version constants cannot tell two different source trees apart: a stale
    editable checkout and a wheel install both report the same ``packageVersion``.
    The resolved module location is the only reliable answer to "which code is
    running right now", so a user can notice that the code they are executing is
    not the checkout they think they are executing.
    """

    from pathlib import Path

    module = Path(__file__).resolve()
    package_root = module.parent
    under_site_packages = "site-packages" in str(package_root).lower()

    package = sys.modules.get(__package__ or "")
    declared = str(getattr(package, "__version__", "") or "").strip() or "UNKNOWN"

    return {
        "modulePath": str(module),
        "packageRoot": str(package_root),
        "installationKind": "site-packages" if under_site_packages else "source-tree-or-editable",
        "declaredVersion": declared,
        "packageVersion": PACKAGE_VERSION,
        "executablePath": sys.executable,
        "claimBoundary": (
            "This names the installation this process imported. It does not prove the installation is "
            "current, intact, or the one the user intended; compare modulePath against the intended checkout."
        ),
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
