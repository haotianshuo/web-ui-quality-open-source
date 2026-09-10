"""Shared conservative signals for natural-language intent parsing."""
from __future__ import annotations

import re


# A whole-task prohibition may contain a short reason before the write verb,
# e.g. ``不要为了找问题修改文件``.  The terminal boundary is important: a
# scoped non-goal such as ``不要动登录逻辑`` must remain a protected scope,
# not become a whole-task read-only request.
WHOLE_TASK_READ_ONLY = re.compile(
    r"(?:先别改|不要改代码|别改代码|只看看|只检查|只分析|只解释|只告诉我|"
    r"(?:不要|别|不许|禁止)\s*(?:为了[^，。,.!！;；\n]{0,48}\s*)?"
    r"(?:修改|改|动|碰)(?:\s*(?:任何)?\s*(?:代码|项目|文件|东西))?"
    r"(?=\s*(?:[，。,.!！;；\n]|$)))|"
    r"check\s+only|read[- ]?only|"
    r"(?:do\s+not|don't)\s+(?:edit|change|modify|touch)"
    r"(?:\s+(?:any\s+)?(?:code|files?|project|anything))?"
    r"(?=\s*(?:[,.!;\n]|$))",
    re.IGNORECASE,
)


# Remove negative write clauses before looking for a positive mutation
# request.  This is intentionally broader than WHOLE_TASK_READ_ONLY because a
# scoped clause is still a non-goal and must not count as a write signal.
NEGATED_WRITE_CLAUSE = re.compile(
    r"(?:不要|别|不许|禁止)\s*(?:为了[^，。,.!！;；\n]{0,48}\s*)?"
    r"(?:修改|改|动|碰)[^，。,.!！;；\n]*|"
    r"(?:do\s+not|don't)\s+(?:touch|edit|change|modify|update|adjust)"
    r"[^,.!;\n]*",
    re.IGNORECASE,
)


def has_whole_task_read_only(text: str) -> bool:
    return bool(WHOLE_TASK_READ_ONLY.search(str(text or "")))


def strip_negated_write_clauses(text: str) -> str:
    return NEGATED_WRITE_CLAUSE.sub("", str(text or ""))


__all__ = [
    "NEGATED_WRITE_CLAUSE",
    "WHOLE_TASK_READ_ONLY",
    "has_whole_task_read_only",
    "strip_negated_write_clauses",
]
