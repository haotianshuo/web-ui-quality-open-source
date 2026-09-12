"""Shared conservative signals for natural-language intent parsing.

The signal layer deliberately describes language only.  It does not decide
whether a Host may write, and it keeps a positive bounded write clause
separate from a negative clause about the rest of a project.
"""
from __future__ import annotations

import re
import unicodedata


# A whole-task prohibition may contain a short reason before the write verb,
# e.g. ``不要为了找问题修改文件``.  The terminal boundary is important: a
# scoped non-goal such as ``不要动登录逻辑`` must remain a protected scope,
# not become a whole-task read-only request.
WHOLE_TASK_READ_ONLY = re.compile(
    r"(?:先别改|不要改代码|别改代码|只看看|只检查|只分析|只解释|只告诉我|"
    r"(?:不要|别|不许|禁止)\s*(?:为了[^，。,.!！;；\n]{0,48}\s*)?"
    r"(?:修改|改|动|碰)(?:\s*(?:任何)?\s*(?:代码|项目|文件|东西))?"
    r"(?=\s*(?:[，。,.!！;；\n]|$)))|"
    r"\bcheck\s+only\b|\bread[- ]?only\b|"
    r"\b(?:do\s+not|don't|dont)\s+(?:edit|change|modify|touch|alter|update)"
    r"(?:\s+(?:any|all|the|this|your)\s+)?(?:files?|code|project|anything|changes?)?"
    r"(?=\s*(?:[,.!;；\n]|$))|"
    r"\b(?:make\s+no\s+changes?|change\s+nothing|touch\s+nothing|"
    r"leave\s+(?:all\s+)?files?\s+unchanged|leave\s+everything\s+unchanged|"
    r"leave\s+the\s+project\s+unchanged|no\s+edits?|"
    r"without\s+(?:modifying|changing|editing|touching)\s+(?:any\s+)?"
    r"(?:files?|code|the\s+project|anything)(?:\s+in\s+(?:the\s+)?(?:project|repo))?)\b|"
    r"\b(?:do\s+not|don't|dont)\s+(?:edit|change|modify|touch|alter|update)\s+"
    r"(?:anything|any\s+files?|any\s+code|the\s+project|the\s+repo)\b(?!\s+else\b)|"
    r"ファイル\s*(?:を)?(?:変更|編集)しないで(?:ください)?|何も変更しない|"
    r"\bno\s+camb(?:ies|ies)\s+(?:ningún|ningun|ninguna)\s+archivo\b|"
    r"\bsin\s+(?:modificar|cambiar|editar)\s+(?:ningún|ningun|ninguna|los?\s+)?"
    r"(?:archivos?|proyecto)\b",
    re.IGNORECASE,
)


_SCOPED_WRITE_PATTERNS = (
    re.compile(
        r"(?:只允许|仅允许|只能|只可|只准)\s*(?:修改|改|编辑|动|调整)\s*"
        r"(?P<scope>[^，。,!?;；\n]+?)(?=\s*[，。,!?;；\n]|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"只\s*(?:修改|改|编辑|动|调整)\s*"
        r"(?P<scope>[^，。,!?;；\n]+?)(?=\s*[，。,!?;；\n]|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:only|just)\s+(?:edit|change|modify|touch)\s+"
        r"(?P<scope>[^,!?;；\n]+?)(?=\s*(?:[,!?;；\n]|\.(?=\s+(?:and|but|while|do\s+not|don't)\b|$))|\s+(?:and|but|while|do\s+not|don't)\b|\s*$)",
        re.IGNORECASE,
    ),
    # ``You may fix it, but change app.js only`` and its punctuation variants.
    re.compile(
        r"\b(?:edit|change|modify|update|touch)\s+(?P<scope>[^,!?;；\n]+?)\s+only\b",
        re.IGNORECASE,
    ),
    # A direct imperative with an explicit remainder restriction.
    re.compile(
        r"(?:^|[.!?;；]\s+|\b(?:and|but)\s+)(?:edit|change|modify|update)\s+(?P<scope>[^,!?;；\n]+?)"
        r"(?=\s+(?:and|but)\s+leave\b|\s*$|[,!?;；]|\.(?=\s+(?:and|but)\s+leave\b|\s+(?:do\s+not|don't)\b|$))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bonly\s+(?P<scope>this\s+file)\s+(?:may|can)\s+be\s+"
        r"(?:changed|modified|edited)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<scope>[^\s，。,!?;；\n]+)\s+だけ変更(?:して|し)ください",
        re.IGNORECASE,
    ),
)


# These are deliberately clause-shaped.  A negative restriction on ``other``
# files is a protected sub-scope when a positive allowed-write clause exists.
_SCOPED_PROTECTED_PATTERNS = (
    re.compile(
        r"(?:其它|其他|其余)\s*(?:文件|代码|项目)\s*(?:包括|包含)?\s*"
        r"(?P<scope>[^，。,!！;；\n]+?)\s*(?:都|均|全部)?\s*"
        r"(?:禁止|不得|不允许)\s*(?:修改|改|编辑|动|碰)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:all\s+other|other)\s+(?:files?|code|projects?)\s*"
        r"(?:including)?\s*(?P<scope>[^,!?;；\n]*?)\s*"
        r"(?:must\s+not|may\s+not)\s*(?:edit|change|modify|touch)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\b(?:do\s+not|don't|dont)\s+(?:touch|edit|change|modify|update)\s+)"
        r"(?P<scope>(?:any\s+)?other\s+files?|everything\s+else|anything\s+else|the\s+rest|all\s+other\s+files?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\b(?:leave)\s+)(?P<scope>everything\s+else|all\s+other\s+files?|the\s+rest)\s+"
        r"unchanged\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:别|不要|不许|禁止)\s*(?:修改|改|编辑|动|碰)\s*"
        r"(?P<scope>任何?其他文件|其它文件|其余文件|配置文件)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<scope>配置文件|其它文件|其他文件|其余文件)\s*"
        r"(?:不要|别|不许|禁止)\s*(?:修改|改|编辑|动|碰)",
        re.IGNORECASE,
    ),
)


# Remove negative write clauses before looking for a positive mutation
# request.  This is intentionally broader than WHOLE_TASK_READ_ONLY because a
# scoped clause is still a non-goal and must not count as a write signal.
NEGATED_WRITE_CLAUSE = re.compile(
    r"(?:不要|别|不许|禁止)\s*(?:为了[^，。,.!！;；\n]{0,48}\s*)?"
    r"(?:修改|改|动|碰|编辑)[^，。,.!！;；\n]*|"
    r"(?:\bdo\s+not|\bdon't|\bdont)\s+(?:touch|edit|change|modify|update|adjust|alter)"
    r"[^,.!?;；\n]*|"
    r"\b(?:make\s+no\s+changes?|change\s+nothing|touch\s+nothing|"
    r"leave\s+(?:all\s+)?files?\s+unchanged|leave\s+everything\s+unchanged|"
    r"leave\s+the\s+project\s+unchanged|no\s+edits?)\b|"
    r"\bwithout\s+(?:modifying|changing|editing|touching)\s+(?:any\s+)?"
    r"(?:files?|code|the\s+project|the\s+repo|anything)\b[^,.!?;；\n]*|"
    r"ファイル\s*(?:を)?(?:変更|編集)しないで(?:ください)?|何も変更しない|"
    r"\bno\s+camb(?:ies|ies)\s+(?:ningún|ningun|ninguna)\s+archivo\b|"
    r"\bsin\s+(?:modificar|cambiar|editar)\s+(?:ningún|ningun|ninguna|los?\s+)?"
    r"(?:archivos?|proyecto)\b[^,.!?;；\n]*",
    re.IGNORECASE,
)


def normalize_signal_text(text: str | None) -> str:
    """Normalize Unicode, whitespace, and standalone polite tails for matching."""

    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("\u3000", " ")
    value = re.sub(r"[\r\n\t]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    # Courtesy words are semantically inert only when they are a tail.  Do not
    # strip Japanese ``ください`` because it is attached to the verb phrase.
    tail = re.compile(
        r"(?:\s*(?:please|thanks|thank\s+you|now|for\s+me|if\s+possible|"
        r"if\s+you\s+can|por\s+favor|gracias|ahora|si\s+es\s+posible))"
        r"[\s.,!?;:，。！？；、…]*$",
        re.IGNORECASE,
    )
    previous = None
    while value and value != previous:
        previous = value
        value = tail.sub("", value).rstrip()
    return value


def _clean_scope(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    cleaned = cleaned.rstrip(" .,!?:;，。！？；、")
    cleaned = re.sub(r"\s+only$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _is_non_scope(value: str) -> bool:
    return value.casefold() in {
        "nothing", "anything", "no files", "any files", "all files", "files",
        "任何文件", "所有文件", "任何东西", "nothing in the project",
    }


def extract_scoped_write_scope(text: str) -> list[str]:
    """Return explicit allowed-write subjects without granting authority."""

    # Negative clauses contain ordinary write verbs ("do not change source").
    # Remove those clauses before looking for an allowed imperative so a
    # verification or no-mutation request cannot be mistaken for a scope.
    source = strip_negated_write_clauses(normalize_signal_text(text))
    scopes: list[str] = []
    for pattern in _SCOPED_WRITE_PATTERNS:
        for match in pattern.finditer(source):
            value = _clean_scope(match.groupdict().get("scope") or match.group(0))
            if value and not _is_non_scope(value) and value not in scopes:
                scopes.append(value)
    return scopes


def extract_scoped_protected_scope(text: str) -> list[str]:
    """Return the subjects explicitly excluded from a bounded write."""

    source = normalize_signal_text(text)
    scopes: list[str] = []
    for pattern in _SCOPED_PROTECTED_PATTERNS:
        for match in pattern.finditer(source):
            value = _clean_scope(match.groupdict().get("scope") or "")
            if value and value not in scopes:
                scopes.append(value)
    return scopes


def _is_scoped_restriction(match: re.Match[str], source: str) -> bool:
    phrase = match.group(0).casefold()
    if re.search(r"\b(?:other|all\s+other|everything\s+else|anything\s+else|the\s+rest)\b", phrase) or re.search(r"(?:其它|其他|其余)", phrase):
        return True
    # The WHOLE_TASK pattern intentionally matches the short negative verb
    # phrase. Inspect the containing clause to distinguish ``配置文件不要碰``
    # from a genuinely global ``不要碰任何文件``.
    clause = re.split(r"[，。,!?;；\n]", source[:match.start()])[-1] + match.group(0)
    return bool(re.search(r"(?:配置文件|其它文件|其他文件|其余文件|other\s+files?|everything\s+else|anything\s+else|the\s+rest|all\s+other)", clause, flags=re.IGNORECASE))


def has_whole_task_read_only(text: str) -> bool:
    source = normalize_signal_text(text)
    if not source:
        return False
    scoped_write = extract_scoped_write_scope(source)
    for match in WHOLE_TASK_READ_ONLY.finditer(source):
        # “其它文件……禁止修改” and its English equivalents are protected
        # sub-scopes after an explicit allowed-write clause.  A global phrase
        # such as “do not modify any files” remains a whole-task prohibition.
        if scoped_write and _is_scoped_restriction(match, source):
            continue
        return True
    return False


def strip_negated_write_clauses(text: str) -> str:
    return NEGATED_WRITE_CLAUSE.sub(" ", normalize_signal_text(text))


__all__ = [
    "NEGATED_WRITE_CLAUSE",
    "extract_scoped_protected_scope",
    "extract_scoped_write_scope",
    "has_whole_task_read_only",
    "normalize_signal_text",
    "WHOLE_TASK_READ_ONLY",
    "strip_negated_write_clauses",
]
