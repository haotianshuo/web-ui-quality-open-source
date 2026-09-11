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


_SCOPED_WRITE_SCOPE = re.compile(
    r"(?:只允许|仅允许|只能|只可)\s*(?:修改|改|编辑|动)\s*(?P<scope>[^，。,!！;；\n]+)"
    r"|(?:only|just)\s*(?:edit|change|modify|touch)\s+(?P<scope_en>[^,!?;\n]+)",
    re.IGNORECASE,
)


_SCOPED_PROTECTED_SCOPE = re.compile(
    r"(?:其它|其他|其余)\s*(?:文件|代码|项目)\s*(?:包括|包含)?\s*"
    r"(?P<scope>[^，。,!！;；\n]+?)\s*(?:都|均|全部)?\s*(?:禁止|不得|不允许)\s*(?:修改|改|编辑|动|碰)"
    r"|(?:all\s+other|other)\s+(?:files?|code|projects?)\s*(?:including)?\s*"
    r"(?P<scope_en>[^,!?;\n]+?)\s*(?:must\s+not|may\s+not)\s*(?:edit|change|modify|touch)",
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
    source = str(text or "")
    for match in WHOLE_TASK_READ_ONLY.finditer(source):
        # “其它文件……禁止修改” is a protected sub-scope when it appears
        # after an explicit allowed-write clause.  It must not turn a bounded
        # repair into a contradictory whole-task read-only request.
        prefix = source[max(0, match.start() - 96):match.start()]
        if _SCOPED_PROTECTED_SCOPE.search(prefix + match.group(0)):
            continue
        if re.search(r"(?:其它|其他|其余|all\s+other|other)\s+(?:文件|代码|项目|files?|code|projects?)", prefix, flags=re.IGNORECASE):
            continue
        return True
    return False


def extract_scoped_write_scope(text: str) -> list[str]:
    """Return explicit allowed-write subjects without granting authority."""
    scopes: list[str] = []
    for match in _SCOPED_WRITE_SCOPE.finditer(str(text or "")):
        value = str(match.group("scope") or match.group("scope_en") or "").strip().rstrip(".")
        if value and value not in scopes:
            scopes.append(value)
    return scopes


def extract_scoped_protected_scope(text: str) -> list[str]:
    """Return the subjects explicitly excluded from a bounded write."""
    scopes: list[str] = []
    for match in _SCOPED_PROTECTED_SCOPE.finditer(str(text or "")):
        value = str(match.group("scope") or match.group("scope_en") or "").strip().rstrip(".")
        if value and value not in scopes:
            scopes.append(value)
    return scopes


def strip_negated_write_clauses(text: str) -> str:
    return NEGATED_WRITE_CLAUSE.sub("", str(text or ""))


__all__ = [
    "NEGATED_WRITE_CLAUSE",
    "extract_scoped_protected_scope",
    "extract_scoped_write_scope",
    "WHOLE_TASK_READ_ONLY",
    "has_whole_task_read_only",
    "strip_negated_write_clauses",
]
