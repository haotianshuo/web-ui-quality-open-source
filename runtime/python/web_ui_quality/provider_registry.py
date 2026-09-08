"""Deterministic, install-free Provider registry and capability router."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.metadata
import shutil
from typing import Iterable, Mapping

from .contracts import ContractViolation, digest_json


SAFE_EXECUTION_PLANES = {"builtin", "local-read-only", "host-gated"}


@dataclass(frozen=True)
class CapabilityDescriptor:
    provider_id: str
    version: str
    license: str
    capabilities: tuple[str, ...]
    input_types: tuple[str, ...]
    execution_plane: str
    prerequisites: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    executes_project_code: bool = False
    requires_network: bool = False
    produces_files: bool = False
    requires_browser: bool = False
    requires_sensitive_data: bool = False

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        for key in ("capabilities", "input_types", "prerequisites", "limitations"):
            value[key] = list(value[key])
        return value


@dataclass(frozen=True)
class CapabilityProbe:
    provider_id: str
    status: str
    detected_version: str | None
    limitations: tuple[str, ...]
    install_attempts: int = 0
    network_requests: int = 0
    writes: int = 0


def probe_provider(descriptor: CapabilityDescriptor) -> CapabilityProbe:
    """Probe only PATH/package metadata; never import or execute Provider code."""

    value = validate_descriptor(descriptor)
    if value.execution_plane == "builtin":
        return CapabilityProbe(value.provider_id, "available", value.version, value.limitations)
    detected: list[str] = []
    for prerequisite in value.prerequisites:
        kind, separator, name = prerequisite.partition(":")
        if not separator or not name:
            raise ContractViolation("PROVIDER_PREREQUISITE_INVALID", ["$.prerequisites: expected kind:name"])
        if kind == "command":
            if shutil.which(name) is None:
                return CapabilityProbe(value.provider_id, "unavailable", None, value.limitations + (f"missing command:{name}",))
        elif kind == "python-package":
            try:
                detected.append(importlib.metadata.version(name))
            except importlib.metadata.PackageNotFoundError:
                return CapabilityProbe(value.provider_id, "unavailable", None, value.limitations + (f"missing package:{name}",))
        else:
            raise ContractViolation("PROVIDER_PREREQUISITE_INVALID", ["$.prerequisites: unsupported probe kind"])
    return CapabilityProbe(value.provider_id, "available", detected[0] if len(detected) == 1 else value.version, value.limitations)


def validate_descriptor(value: CapabilityDescriptor) -> CapabilityDescriptor:
    errors: list[str] = []
    if not value.provider_id or not value.provider_id.replace("-", "").replace(".", "").isalnum():
        errors.append("$.providerId: expected stable identifier")
    if not value.version or value.version.casefold() in {"unknown", "latest"}:
        errors.append("$.version: pinned recognized version required")
    if not value.license or value.license.casefold() in {"unknown", "unlicensed"}:
        errors.append("$.license: recognized license required")
    if value.execution_plane not in SAFE_EXECUTION_PLANES:
        errors.append("$.executionPlane: unsupported execution plane")
    if not value.capabilities or not value.input_types:
        errors.append("$: capabilities and input types must be non-empty")
    if value.executes_project_code or value.requires_network or value.produces_files or value.requires_sensitive_data:
        errors.append("$: unsafe provider metadata is not eligible for automatic routing")
    if errors:
        raise ContractViolation("PROVIDER_DESCRIPTOR_REJECTED", errors)
    return value


class ProviderRegistry:
    """Main-agent-owned immutable-by-default registry."""

    def __init__(self, descriptors: Iterable[CapabilityDescriptor] = ()) -> None:
        self._items: dict[str, CapabilityDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: CapabilityDescriptor) -> None:
        value = validate_descriptor(descriptor)
        if value.provider_id in self._items:
            raise ContractViolation("PROVIDER_DUPLICATE", ["$.providerId: duplicate provider"])
        self._items[value.provider_id] = value

    def snapshot(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def digest(self) -> str:
        return digest_json([item.payload() for item in self.snapshot()])

    def route(
        self,
        capabilities: Iterable[str],
        *,
        available: Mapping[str, bool],
        allow_browser: bool = False,
    ) -> dict[str, object]:
        requested = tuple(sorted(set(capabilities)))
        selected: list[str] = []
        reasons: list[dict[str, object]] = []
        unavailable: list[str] = []
        for capability in requested:
            candidates = [
                item for item in self.snapshot()
                if capability in item.capabilities and (allow_browser or not item.requires_browser)
            ]
            eligible = [item for item in candidates if available.get(item.provider_id, False)]
            builtin = [item for item in eligible if item.execution_plane == "builtin"]
            choice = (builtin or eligible)
            if choice:
                if choice[0].provider_id not in selected:
                    selected.append(choice[0].provider_id)
                reasons.append({"capability": capability, "providerId": choice[0].provider_id, "limitations": list(choice[0].limitations), "reason": "builtin-first-safe-available"})
            else:
                unavailable.append(capability)
        payload: dict[str, object] = {
            "requested": list(requested),
            "selected": selected,
            "selectionReasons": reasons,
            "unavailable": unavailable,
            "result": "NOT_VERIFIED" if unavailable else "PASS",
            "installAttempts": 0,
            "networkRequests": 0,
            "writes": 0,
        }
        payload["digest"] = digest_json(payload)
        return payload


def default_provider_registry() -> ProviderRegistry:
    return ProviderRegistry((CapabilityDescriptor(
        provider_id="builtin-lite",
        version="0.3.0",
        license="project-internal",
        capabilities=("static-audit", "rule-coverage", "design-context", "evidence-normalization"),
        input_types=("html", "css", "javascript", "typescript", "jsx", "tsx", "vue", "svelte"),
        execution_plane="builtin",
        limitations=("static evidence only", "no complete control-flow or type analysis"),
    ),))
