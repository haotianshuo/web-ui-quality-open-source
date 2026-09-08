"""Authoritative runtime conditions for comparable Web experience evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from .contracts import ContractViolation, digest_json

STANDARD_VIEWPORTS: tuple[tuple[int, int], ...] = ((390, 844), (768, 1024), (1440, 900))


@dataclass(frozen=True, slots=True)
class ViewportCondition:
    width: int
    height: int
    dpr: float
    touch: bool
    mobile: bool

    @classmethod
    def from_size(cls, width: int, height: int, *, dpr: float | None = None) -> "ViewportCondition":
        if width < 320 or height < 480 or width > 3840 or height > 2160:
            raise ContractViolation("BROWSER_VIEWPORT_INVALID", [f"$: unsupported viewport {width}x{height}"])
        if width <= 480:
            return cls(width, height, float(dpr or 2), True, True)
        if width <= 900:
            return cls(width, height, float(dpr or 1.5), True, False)
        return cls(width, height, float(dpr or 1), False, False)


@dataclass(frozen=True, slots=True)
class RunConditions:
    url: str | None
    route: str | None
    source_fingerprint: str | None
    scheme: str | None = None
    host: str | None = None
    port: int | None = None
    query_policy: str = "exact"
    query: str | None = None
    target_kind: str | None = None
    project_root: str | None = None
    user_role: str | None = None
    auth_state: str = "anonymous"
    test_data_state: str = "unspecified"
    locale: str = "zh-CN"
    theme: str = "light"
    reduced_motion: str = "reduce"
    browser: str = "chromium"
    browser_version: str | None = None
    viewports: tuple[ViewportCondition, ...] = field(default_factory=lambda: tuple(ViewportCondition.from_size(*v) for v in STANDARD_VIEWPORTS))
    service_worker_policy: str = "block"
    allowed_origins: tuple[str, ...] = ()
    approved_request_policy: tuple[Mapping[str, Any], ...] = ()
    readiness_rule: Mapping[str, Any] = field(default_factory=dict)
    safe_task: Mapping[str, Any] = field(default_factory=dict)
    feature_flags: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["viewports"] = [asdict(item) for item in self.viewports]
        value["allowed_origins"] = list(self.allowed_origins)
        value["approved_request_policy"] = [dict(item) for item in self.approved_request_policy]
        return value

    @property
    def digest(self) -> str:
        return digest_json(self.to_dict())


def normalize_viewports(raw: Sequence[Sequence[int]] | None) -> tuple[ViewportCondition, ...]:
    values = raw or STANDARD_VIEWPORTS
    normalized = tuple(ViewportCondition.from_size(int(item[0]), int(item[1])) for item in values)
    keys = {(item.width, item.height) for item in normalized}
    if len(keys) != len(normalized):
        raise ContractViolation("BROWSER_VIEWPORT_INVALID", ["$: duplicate viewport"])
    return normalized


def compare_conditions(
    before: Mapping[str, Any], after: Mapping[str, Any], *, allowed_differences: Sequence[str] = (),
) -> dict[str, Any]:
    keys = (
        "url", "route", "source_fingerprint", "scheme", "host", "port", "query_policy", "query", "target_kind", "project_root", "user_role", "auth_state", "test_data_state",
        "locale", "theme", "reduced_motion", "browser", "browser_version", "viewports",
        "service_worker_policy", "allowed_origins", "approved_request_policy", "readiness_rule", "safe_task", "feature_flags",
    )
    allowed = set(allowed_differences)
    mismatches = {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if key not in allowed and before.get(key) != after.get(key)
    }
    allowed_changes = {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if key in allowed and before.get(key) != after.get(key)
    }
    return {
        "match": not mismatches,
        "mismatches": mismatches,
        "allowedChanges": allowed_changes,
        "beforeDigest": digest_json(dict(before)),
        "afterDigest": digest_json(dict(after)),
    }


__all__ = ["STANDARD_VIEWPORTS", "ViewportCondition", "RunConditions", "normalize_viewports", "compare_conditions"]
