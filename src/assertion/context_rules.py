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

# ── isFamily ──────────────────────────────────────────────────────────────────
# ⚠️ ĐÃ BỎ đại từ xưng hô phổ biến trần (em/anh/chị) khỏi trigger — chúng thường là
# BỆNH NHÂN tự xưng ("bác sỹ cho em hỏi..."), không phải người nhà (bẫy false-positive).
# Chúng chỉ tính là người nhà khi đứng trong cụm quan hệ rõ ("anh của em", "mẹ bệnh nhân").

_REL = (r"bố|mẹ|cha|ba|má|anh|chị|em|con|ông|bà|cô|chú|dì|cậu|mợ|bác|cháu|vợ|chồng|"
        r"dượng|thím|anh trai|chị gái|em trai|em gái|con trai|con gái")
_OWNER = r"em|tôi|con|cháu|mình|anh|chị|bệnh nhân|người bệnh|bn"
_DISEASE_CUE = (r"bị|mắc|có tiền sử|tiền sử|được chẩn đoán|chẩn đoán|tử vong|qua đời|"
                r"mất do|có triệu chứng|từng bị|điều trị")

# (A) từ quan hệ MẠNH đứng trần (rõ nghĩa người nhà; KHÔNG gồm em/anh/chị)
_FAM_STRONG = re.compile(
    r"\b(?:mẹ|bố|cha|con trai|con gái|anh trai|chị gái|em trai|em gái|"
    r"ông nội|bà nội|ông ngoại|bà ngoại|ông bà|gia đình|di truyền|họ hàng|người thân)\b",
    re.I,
)
# ba/má giữ trần nhưng chặn nhầm với đơn vị thời gian/số lượng ("ba ngày", "ba lần")
_FAM_BAMA = re.compile(
    r"\b(?:ba|má)\b(?!\s+(?:ngày|tuần|tháng|năm|lần|giờ|phút|viên|đứa|con|người|tuổi))",
    re.I,
)
# (B) quan hệ biểu thị qua đại từ khác: "anh của em", "mẹ bệnh nhân", "ba của chị"
_FAM_REL = re.compile(
    rf"\b(?:{_REL})\s+(?:của\s+(?:{_OWNER})|bệnh nhân|người bệnh)\b", re.I
)
# (C) ngữ cảnh sở hữu tình trạng bệnh: người thân + dấu hiệu bệnh ("mẹ bị tiểu đường",
#     "bố có tiền sử", "ông mắc lao"). Chủ ngữ chỉ dùng từ quan hệ rõ, KHÔNG dùng em/anh/chị.
_FAM_POSSESS = re.compile(
    r"\b(?:mẹ|bố|cha|ba|má|ông|bà|cô|chú|dì|cậu|bác|cháu|"
    r"anh trai|chị gái|em trai|em gái|con trai|con gái)\b"
    rf"[^.,;\n]{{0,20}}\b(?:{_DISEASE_CUE})\b",
    re.I,
)


def _is_family(clause: str) -> bool:
    return bool(
        _FAM_STRONG.search(clause)
        or _FAM_BAMA.search(clause)
        or _FAM_REL.search(clause)
        or _FAM_POSSESS.search(clause)
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
    if _is_family(clause):
        res.add(Assertion.FAMILY)
    return sorted(res, key=lambda a: a.value)
