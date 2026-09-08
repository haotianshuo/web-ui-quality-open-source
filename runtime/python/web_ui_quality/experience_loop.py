"""Continuous product-experience measurement and iteration planning."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_measurement_loop(journey: Mapping[str, Any], transformation: Mapping[str, Any]) -> dict[str, Any]:
    selected_id = transformation.get("selectedVariantId")
    return {
        "schemaVersion": "3.6",
        "readiness": "BASELINE_REQUIRED",
        "selectedVariantId": selected_id,
        "metrics": [
            {
                "id": "task-success",
                "label": "核心任务完成率",
                "definition": "进入任务的用户中，达到明确成功状态且未发生关键错误的比例",
                "baseline": None,
                "target": None,
                "source": "匿名任务事件或可用性观察",
                "guardrail": "不得以增加误操作或隐藏失败换取完成率",
            },
            {
                "id": "time-on-task",
                "label": "任务完成时间",
                "definition": "从任务入口到成功反馈的中位时长",
                "baseline": None,
                "target": None,
                "source": "受控任务测试或匿名时间事件",
                "guardrail": "同时观察成功率，避免只追求速度",
            },
            {
                "id": "recovery-success",
                "label": "异常恢复率",
                "definition": "遇到验证、网络或权限问题后最终完成任务的比例",
                "baseline": None,
                "target": None,
                "source": "错误与恢复事件",
                "guardrail": "不记录敏感字段或用户输入正文",
            },
            {
                "id": "support-signal",
                "label": "相关求助信号",
                "definition": "与该旅程相关的求助、返回和放弃信号",
                "baseline": None,
                "target": None,
                "source": "去标识化支持分类与行为事件",
                "guardrail": "仅作方向信号，不替代用户研究",
            },
        ],
        "cadence": [
            {"stage": "before", "action": "记录现状基线、样本和环境"},
            {"stage": "pilot", "action": "对一个可回滚切片进行三端和可访问性验证"},
            {"stage": "observe", "action": "在约定样本窗口观察任务、恢复和求助信号"},
            {"stage": "decide", "action": "扩展、修正或回滚；记录证据和原因"},
        ],
        "decisionRules": {
            "expand": "主要任务指标改善，且错误、恢复和可访问性护栏未退化",
            "iterate": "方向信号积极但证据不足，或某个状态/设备仍有明显摩擦",
            "rollback": "关键任务、错误率、恢复能力或业务规则出现退化",
        },
        "privacy": ["只收集完成决策所需的最少事件", "不采集密码、令牌、消息正文或业务敏感字段", "使用聚合结果并定义保留期限"],
        "claimBoundary": "Targets remain unset until the owner supplies a real baseline and acceptable business threshold.",
        "journeyId": journey.get("criticalStageId"),
    }
