"""First-wave BrowserProvider interface only; no browser implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class BrowserProvider(ABC):
    @abstractmethod
    def probe_capabilities(self) -> Mapping[str, object]: ...
    @abstractmethod
    def start_isolated_session(self, contract: Mapping[str, object]) -> object: ...
    @abstractmethod
    def navigate(self, session: object, url: str) -> Mapping[str, object]: ...
    @abstractmethod
    def capture_semantic_snapshot(self, session: object) -> Mapping[str, object]: ...
    @abstractmethod
    def capture_console(self, session: object) -> Mapping[str, object]: ...
    @abstractmethod
    def capture_network(self, session: object) -> Mapping[str, object]: ...
    @abstractmethod
    def capture_screenshot(self, session: object) -> Mapping[str, object]: ...
    @abstractmethod
    def capture_trace_on_failure(self, session: object) -> Mapping[str, object]: ...
    @abstractmethod
    def close_session(self, session: object) -> Mapping[str, object]: ...


def unavailable_browser_capability(provider_id: str, limitation: str) -> dict[str, object]:
    return {
        "providerId": provider_id,
        "status": "unavailable",
        "result": "NOT_VERIFIED",
        "reasonCode": "BROWSER_PROVIDER_UNAVAILABLE",
        "limitation": limitation,
        "installAttempts": 0,
        "networkRequests": 0,
        "writes": 0,
    }
