"""Regression matrix for V2-F001 resource-console classification."""
from __future__ import annotations

import pytest

from web_ui_quality.page_health import evaluate_page_health
from web_ui_quality.playwright_adapter import _console_location
from web_ui_quality.readiness import assess_readiness


METRICS = {
    "readyState": "complete",
    "mainPresent": True,
    "textLength": 120,
}


def _resource_console(url: str = "http://127.0.0.1:9/definitely-missing-404.png") -> dict[str, object]:
    return {
        "type": "error",
        "text": "Failed to load resource: the server responded with a status of 404 (Not Found)",
        "location": {"url": url, "lineNumber": 0, "columnNumber": 0},
    }


def test_adapter_preserves_structured_console_location_without_query_data() -> None:
    class Message:
        location = {
            "url": "https://example.test/assets/missing.png?session=private-value#fragment",
            "lineNumber": 0,
            "columnNumber": 0,
        }

    assert _console_location(Message()) == {
        "url": "https://example.test/assets/missing.png",
        "lineNumber": 0,
        "columnNumber": 0,
    }


def test_missing_subresource_console_error_does_not_become_runtime_broken() -> None:
    result = assess_readiness(METRICS, http_status=200, console_errors=[_resource_console()])

    assert result["status"] == "READY"

    health = evaluate_page_health(readiness=result, resource_integrity={"status": "PASS"})
    assert health["runtimeStatus"] == "PASS"
    assert health["pageStatus"] != "RUNTIME_BROKEN"


def test_normal_resource_has_no_classification_regression() -> None:
    result = assess_readiness(METRICS, http_status=200, console_errors=[])

    assert result["status"] == "READY"
    assert evaluate_page_health(readiness=result, resource_integrity={"status": "PASS"})["pageStatus"] != "RUNTIME_BROKEN"


def test_unstructured_console_error_remains_fail_closed() -> None:
    result = assess_readiness(
        METRICS,
        http_status=200,
        console_errors=[{"type": "error", "text": "application console failure"}],
    )

    assert result["status"] == "RUNTIME_BROKEN"


@pytest.mark.parametrize(
    "resource_type",
    ["image", "stylesheet", "script", "font"],
)
def test_resource_failure_is_not_an_unhandled_runtime_exception(resource_type: str) -> None:
    result = assess_readiness(
        METRICS,
        http_status=200,
        console_errors=[_resource_console(f"http://127.0.0.1:9/assets/missing.{resource_type}")],
        core_resource_failures=[{"resourceType": resource_type}] if resource_type in {"stylesheet", "script", "font"} else [],
    )

    assert result["status"] == ("PARTIAL" if resource_type in {"stylesheet", "script", "font"} else "READY")
    health = evaluate_page_health(
        readiness=result,
        resource_integrity={"status": "BLOCKED"} if resource_type in {"stylesheet", "script", "font"} else {"status": "PASS_WITH_WARNINGS"},
    )
    assert health["runtimeStatus"] == "PASS"
    assert health["pageStatus"] == ("RESTRICTED_RENDER" if resource_type in {"stylesheet", "script", "font"} else "NOT_VERIFIED")


def test_genuine_pageerror_stays_runtime_broken() -> None:
    result = assess_readiness(METRICS, http_status=200, page_errors=["Error: genuine runtime exception"])

    assert result["status"] == "RUNTIME_BROKEN"
    assert evaluate_page_health(readiness=result, resource_integrity={"status": "PASS"})["pageStatus"] == "RUNTIME_BROKEN"


def test_resource_failure_plus_genuine_pageerror_stays_runtime_broken() -> None:
    result = assess_readiness(
        METRICS,
        http_status=200,
        page_errors=["Error: genuine exception with resource failure"],
        console_errors=[_resource_console("http://127.0.0.1:9/assets/missing-both.png")],
    )

    assert result["status"] == "RUNTIME_BROKEN"
    assert evaluate_page_health(readiness=result, resource_integrity={"status": "PASS_WITH_WARNINGS"})["pageStatus"] == "RUNTIME_BROKEN"


def test_resource_diagnostic_without_location_is_not_silently_ignored() -> None:
    result = assess_readiness(
        METRICS,
        http_status=200,
        console_errors=[{
            "type": "error",
            "text": "Failed to load resource: the server responded with a status of 404 (Not Found)",
        }],
    )

    assert result["status"] == "RUNTIME_BROKEN"
