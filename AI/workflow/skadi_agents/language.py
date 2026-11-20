"""Normalize familiar monitoring terms without changing IDs, numbers or dates."""

import re
import unicodedata

# Correct terminology and familiar spelling variants before intent extraction.
TERMS = {
    "대시보드": ("대쉬보드", "데쉬보드", "데시보드", "대시보도", "dashboard"),
    "트렌드": ("트랜드", "트렌트", "트랜트", "트랜 드", "trend", "추세", "그래프", "챠트"),
    "현황": ("현항", "현왕", "현홯", "현헝"),
    "설비": ("설피", "설미"),
    "센서": ("쎈서", "센써", "쎈써", "sensor"),
    "펌프": ("펌푸", "pump"),
    "진동": ("진둥", "진덩", "진둉", "vibration"),
    "온도": ("온두", "온됴", "temperature", "temp"),
    "전류": ("전루", "전뤼", "current"),
    "전압": ("전앞", "전앚", "voltage"),
    "회전수": ("회전속도", "회전 속도", "회전슈", "rpm", "알피엠"),
    "흡입압": ("흡입압력", "흡입 압력", "흡입압녁", "흡입압렵"),
    "토출압": ("토출압력", "토출 압력", "토출압녁", "토출압렵"),
    "압력": ("압녁", "압렵", "pressure", "프레셔"),
    "베어링": ("배어링", "베아링", "베어린", "bearing"),
    "모터": ("모타", "motor"),
    "유체": ("유채",),
    "알람": ("알럄", "alarm"),
    "보여줘": (
        "보여주세요",
        "보여 주세요",
        "보여주라",
        "보여쥐",
        "보여조",
        "보여죠",
        "보여저",
        "보여쥬",
        "띄워줘",
        "표시해줘",
    ),
    "알려줘": ("알려주세요", "알려 주세요", "알려주라", "알려조", "알려죠", "알려저"),
    "열어줘": ("열어주세요", "열어 주세요", "열어주라"),
}
KOREAN_FORMS = {
    form.replace(" ", ""): canonical
    for canonical, aliases in TERMS.items()
    for form in (canonical, *aliases)
    if re.fullmatch(r"[가-힣 ]+", form)
}
PHRASE_PATTERN = re.compile(
    "|".join(
        r"\s*".join(map(re.escape, form)) for form in sorted(KOREAN_FORMS, key=len, reverse=True)
    )
)

ALIASES = {alias.casefold(): canonical for canonical, aliases in TERMS.items() for alias in aliases}
ALIAS_PATTERN = re.compile(
    "|".join(re.escape(s) for s in sorted(ALIASES, key=len, reverse=True)), re.IGNORECASE
)
# Keep valid domain terms intact. Short, distinct sensors must never be fuzzy-remapped.
VALID = set(TERMS) | {
    "추이",
    "차트",
    "상태",
    "현재",
    "값",
    "정보",
    "데이터",
    "보고서",
    "사건",
    "원인",
}
KNOWN_PATTERN = re.compile(
    "(" + "|".join(re.escape(s) for s in sorted(VALID, key=len, reverse=True)) + ")"
)
WORD_PATTERN = re.compile(
    r"(?P<id>\d{2}-[A-Za-z]{2,8}-\d{4}|(?<![A-Za-z0-9])[Pp]\d+(?![A-Za-z0-9]))"
    r"|(?P<word>[가-힣A-Za-z]+)"
)


def _edit_distance(left: str, right: str) -> int:
    """Damerau distance also recognizes an adjacent keyboard transposition."""
    rows = [list(range(len(right) + 1))]
    for i, a in enumerate(left, 1):
        row = [i]
        for j, b in enumerate(right, 1):
            value = min(row[-1] + 1, rows[-1][j] + 1, rows[-1][j - 1] + (a != b))
            if i > 1 and j > 1 and a == right[j - 2] and left[i - 2] == b:
                value = min(value, rows[i - 2][j - 2] + 1)
            row.append(value)
        rows.append(row)
    return rows[-1][-1]


def close_spelling(left: str, right: str) -> bool:
    """A single Hangul key error or adjacent syllable swap is a plausible typo."""
    if left == right or not re.fullmatch(r"[가-힣]{2,}", left + right):
        return False
    a, b = unicodedata.normalize("NFD", left), unicodedata.normalize("NFD", right)
    if abs(len(a) - len(b)) <= 1 and _edit_distance(a, b) == 1:
        return True
    return (
        len(left) >= 3
        and len(left) == len(right)
        and any(
            left[:i] + left[i + 1] + left[i] + left[i + 2 :] == right for i in range(len(left) - 1)
        )
    )


def _unknown_term(text: str) -> str:
    if len(text) < 3:
        return text
    for suffix in ("", "으로", "를", "을", "만", "도", "은", "는", "요"):
        if suffix and not text.endswith(suffix):
            continue
        stem = text[: -len(suffix)] if suffix else text
        if len(stem) < 3:
            continue
        matches = [term for term in VALID if len(term) >= 3 and close_spelling(stem, term)]
        if len(matches) == 1:
            return matches[0] + suffix
    return text


def normalize_request(message: str) -> str:
    """Normalize only natural-language spans; leave registered tags and values alone."""

    def word(match: re.Match) -> str:
        if match["id"]:
            return match[0]
        text = ALIAS_PATTERN.sub(lambda m: ALIASES[m[0].casefold()], match["word"])
        return "".join(
            part if part in VALID else _unknown_term(part) for part in KNOWN_PATTERN.split(text)
        )

    text = unicodedata.normalize("NFKC", message)
    text = PHRASE_PATTERN.sub(lambda m: KOREAN_FORMS[re.sub(r"\s+", "", m[0])], text)
    text = WORD_PATTERN.sub(word, text)
    # Only grammatical whitespace/fillers are removed, never numeric query conditions.
    text = re.sub(r"(보여|알려|열어)\s+(줘|주세요)", r"\1\2", text)
    text = re.sub(r"좀\s*(?=보여줘|알려줘|열어줘)", "", text)
    text = re.sub(r"(보여줘|알려줘|열어줘)요(?=[?!.。]*$)", r"\1", text)
    return text
