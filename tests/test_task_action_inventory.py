from __future__ import annotations

from web_ui_quality.rendered_quality import _RENDERED_QUALITY_JS
from web_ui_quality.smart_acceptance import summarize_task_action_inventory


def test_rendered_action_inventory_is_passive_and_reports_route_declarations() -> None:
    inventory_script = _RENDERED_QUALITY_JS.split("// Keep task-action discovery passive.", 1)[1].split("const headings=", 1)[0]

    assert "taskActionCandidates" in _RENDERED_QUALITY_JS
    assert "data-action" in inventory_script
    assert "destinationKind" in inventory_script
    assert "closest('nav,[role=\"navigation\"]')" in inventory_script
    assert ".click(" not in inventory_script
    assert "executionStatus:'NOT_EXECUTED'" in inventory_script


def test_action_inventory_deduplicates_viewports_without_claiming_success() -> None:
    quick_report = {
        "records": [
            {
                "label": "390x844",
                "renderedQuality": {
                    "raw": {
                        "taskActionCandidates": [{
                            "controlKind": "button", "label": "去处理", "dataAction": "review",
                            "destinationKind": "none", "destinationDeclared": False,
                            "containerKind": "article", "executionStatus": "NOT_EXECUTED",
                        }],
                    },
                },
            },
            {
                "label": "768x1024",
                "renderedQuality": {
                    "raw": {
                        "taskActionCandidates": [{
                            "controlKind": "button", "label": "去处理", "dataAction": "review",
                            "destinationKind": "none", "destinationDeclared": False,
                            "containerKind": "article", "executionStatus": "NOT_EXECUTED",
                        }],
                    },
                },
            },
        ],
    }

    inventory = summarize_task_action_inventory(quick_report)

    assert inventory["status"] == "CANDIDATES_RECORDED"
    assert inventory["executionStatus"] == "NOT_EXECUTED"
    assert len(inventory["candidates"]) == 1
    assert inventory["candidates"][0]["label"] == "去处理"
    assert inventory["candidates"][0]["dataAction"] == "review"
    assert inventory["candidates"][0]["destinationDeclared"] is False
    assert inventory["candidates"][0]["viewports"] == ["390x844", "768x1024"]
    assert "does not prove" in inventory["claimBoundary"]
    assert "severity" not in inventory["candidates"][0]


def test_declared_link_is_still_unverified_and_empty_inventory_is_not_a_finding() -> None:
    linked = summarize_task_action_inventory({
        "records": [{
            "label": "390x844",
            "renderedQuality": {"raw": {"taskActionCandidates": [{
                "controlKind": "link", "label": "查看任务", "destinationKind": "href",
                "destinationDeclared": True, "sameOriginTarget": True,
                "containerKind": "list-item",
            }]}},
        }],
    })
    empty = summarize_task_action_inventory(
        {"records": []},
        requested_outcome="打开任务，不要提交审核；联系 555-123-4567",
    )

    assert linked["candidates"][0]["destinationDeclared"] is True
    assert linked["candidates"][0]["executionStatus"] == "NOT_EXECUTED"
    assert empty["status"] == "NO_VISIBLE_CONTEXTUAL_ACTIONS"
    assert empty["candidates"] == []
    assert "severity" not in empty
    assert empty["requestedOutcome"] == "打开任务，不要提交审核；联系 [REDACTED]"
