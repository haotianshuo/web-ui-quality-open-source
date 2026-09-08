"""Translate internal contracts into ordinary user language."""
from __future__ import annotations

_STATUS_LABELS = {
    "PASS": "已完成并验证",
    "PASS_WITH_WARNINGS": "基本可用，但仍有需要处理的问题",
    "FAIL": "当前检查未通过",
    "BLOCKED": "需要你处理",
    "NOT_VERIFIED": "已完成但部分未验证",
    "NOT_EXECUTED": "本次没有执行",
    "NOT_APPLICABLE": "本次不适用",
    "VERIFIED": "已完成并验证",
    "SOURCE_INFERRED": "根据源码推断，尚未实测",
    "PACKAGE_VERIFIED": "已确认安装包完整性",
    "SYNTHETIC_HYPOTHESIS": "模拟推测，不代表真实用户结果",
}

_AUTHORITY_LABELS = {
    "A0": "只查看",
    "A1": "安全页面操作",
    "A2": "修改指定文件",
    "A3": "高风险或破坏性操作",
}


def status_label(value: object) -> str:
    key = str(value or "UNKNOWN")
    return _STATUS_LABELS.get(key, key.replace("_", " ").title())


def authority_label(value: object) -> str:
    key = str(value or "")
    return _AUTHORITY_LABELS.get(key, key)


__all__ = ["authority_label", "status_label"]
