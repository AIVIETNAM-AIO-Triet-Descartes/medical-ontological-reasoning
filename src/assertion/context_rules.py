"""Module 2 — Assertion Detection kiểu ConText/NegEx (rule-based, không cần training).

Áp dụng cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC. Trả subset {isNegated, isFamily, isHistorical}.

Scope: quét trigger trong CỤM chứa span, ranh giới = dấu câu + từ đảo chiều (nhưng/tuy nhiên/song).
isHistorical: trigger trong câu HOẶC section header ("tiền sử", "trước nhập viện").
isFamily: yêu cầu danh từ quan hệ cụ thể (mẹ/bố/anh/chị...); KHÔNG suy từ "ông ấy/bà ấy" (= bệnh nhân).

Xem docs/baseline-implementation.md §3. Thiết kế có thể sai — chờ gold kiểm chứng.
"""

from __future__ import annotations

import re

from src.schema import Assertion

_NEG = re.compile(r"\bkhông\b|\bchưa\b|phủ nhận|âm tính|loại trừ|\bkhông có\b", re.I)
_HIST = re.compile(r"tiền sử|tiền căn|trước đây|cách đây|nhiều năm|đã từng", re.I)
_FAM = re.compile(
    r"\b(mẹ|bố|cha|ba|má|anh trai|chị gái|em trai|em gái|anh|chị|em|con trai|con gái|"
    r"ông nội|bà nội|ông ngoại|bà ngoại|gia đình|di truyền|họ hàng|người thân)\b",
    re.I,
)
# ranh giới cụm: dấu câu + từ đảo chiều mạch
_BOUND = re.compile(r"[.;\n,]|\bnhưng\b|\btuy nhiên\b|\bsong\b", re.I)
_HIST_HEADER = re.compile(r"tiền sử|tiền căn|trước (khi )?nhập viện|thuốc trước", re.I)
_NUM_HEADER = re.compile(r"^\s*\d+\s*\.")


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Cụm chứa span: mở rộng tới ranh giới gần nhất hai bên."""
    left = 0
    for m in _BOUND.finditer(text, 0, start):
        left = m.end()
    right_m = _BOUND.search(text, end)
    right = right_m.start() if right_m else len(text)
    return left, right


def _in_historical_section(text: str, start: int) -> bool:
    """Section header gần nhất phía trên span có phải mục tiền sử không."""
    lines = text[:start].split("\n")
    for line in reversed(lines[-20:]):
        low = line.strip().lower()
        if not low:
            continue
        if _HIST_HEADER.search(low):
            return True
        if _NUM_HEADER.match(low):     # gặp section đánh số khác (không tiền sử) trước
            return _HIST_HEADER.search(low) is not None
    return False


def detect(text: str, start: int, end: int) -> list[Assertion]:
    cstart, cend = _clause_bounds(text, start, end)
    before = text[cstart:start]          # phần trước span trong cụm
    clause = text[cstart:cend]

    res: set[Assertion] = set()
    if _NEG.search(before):
        res.add(Assertion.NEGATED)
    if _HIST.search(clause) or _in_historical_section(text, start):
        res.add(Assertion.HISTORICAL)
    if _FAM.search(clause):
        res.add(Assertion.FAMILY)
    return sorted(res, key=lambda a: a.value)
