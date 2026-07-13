"""Baseline rule-based NER cho Tầng 1 (span + type), đủ 5 loại, ưu tiên precision.

Chiến lược (độ tin cao -> thấp):
  1. THUỐC        — regex tên_anh + liều + [đường dùng] + [tần suất] (chắc nhất).
  2. KẾT_QUẢ_XÉT_NGHIỆM — số + đơn vị lâm sàng (mmol/l, mg/dl, mmHg, lần/phút...).
  3. TÊN_XÉT_NGHIỆM     — cụm 'gloss VN (abbr)' theo whitelist viết tắt.
  4. CHẨN_ĐOÁN / TRIỆU_CHỨNG — lexicon VN nhỏ (recall thấp, chấp nhận ở baseline).

Bất biến: mọi span lấy từ re.finditer -> position = [m.start(), m.end()), text = m.group()
=> input[start:end] == text luôn đúng.

Overlap: giữ span ưu tiên cao hơn; cùng ưu tiên thì giữ span dài hơn.
Baseline KHÔNG gán candidates/assertions (tầng sau).
"""

from __future__ import annotations

import re

from src.schema import Concept, ConceptType

# ── THUỐC ────────────────────────────────────────────────────────────────────
# đơn vị: xếp dài trước ngắn (gram trước g, mcg trước mg) để regex ăn trọn.
_DRUG_UNIT = r"(?:gram|mcg|mg|meq|units?|iu|ml|cc|g|%)"
# token ascii KHÔNG được mở đầu tên thuốc (từ tiếng Việt/nối câu bị lọt vào [A-Za-z]).
_LEADING_STOP = {"cho", "do", "khi", "co", "va", "la", "ba", "cac", "thi", "ma", "vao", "ra"}
_ROUTE = r"(?:po|iv|im|sc|sq|sl|pr|inhaled|nebulizer|nebs?|oral|susp\w*|topical|gtt)"
_FREQ = r"(?:daily|bid|tid|qid|qhs|qam|qpm|qd|qod|qhr|q\d+h|q\d+hr|prn|once|weekly|nightly)"

# tên_anh (1-4 token Latin) + liều + optional đường dùng + optional (lặp) tần suất
_DRUG_RE = re.compile(
    r"\b[A-Za-z][A-Za-z\-]+(?:\s+[A-Za-z][A-Za-z\-]+){0,3}"          # tên
    r"\s+\d+(?:[.,]\d+)?(?:-\d+(?:[.,]\d+)?)?\s*" + _DRUG_UNIT +      # liều + đơn vị
    r"(?:\s+" + _ROUTE + r")?"                                        # đường dùng
    r"(?:\s+" + _FREQ + r"(?::" + _FREQ + r")?)*",                    # tần suất (lặp)
    re.IGNORECASE,
)

# ── KẾT_QUẢ_XÉT_NGHIỆM ────────────────────────────────────────────────────────
# số (thập phân . hoặc ,) + đơn vị lâm sàng; hoặc dạng huyết áp a/b mmHg.
_LAB_UNIT = r"(?:mmol/l|umol/l|mg/dl|g/dl|meq/l|ng/ml|mcg/ml|mg/ml|mmhg|lần/phút|bpm|°c)"
_LAB_RESULT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?(?:/\d+(?:[.,]\d+)?)?\s*" + _LAB_UNIT,
    re.IGNORECASE,
)

# ── TÊN_XÉT_NGHIỆM ────────────────────────────────────────────────────────────
_LAB_ABBR = {
    "wbc", "rbc", "hgb", "hct", "plt", "bun", "cr", "creatinine", "na", "k", "cl",
    "hco3", "ast", "alt", "inr", "bnp", "tbili", "ap", "neut", "lyph", "ure",
    "troponin", "glucose", "ptt", "pt", "egfr", "ck", "ldh", "esr", "crp",
}
# 'gloss VN (abbr)' — bắt cụm ngay trước dấu ngoặc chứa viết tắt whitelist.
_LAB_NAME_RE = re.compile(
    r"[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s\-%]*\((?P<abbr>[A-Za-z0-9%\-]{1,12})\)",
)

# ── CHẨN_ĐOÁN / TRIỆU_CHỨNG (lexicon VN) ─────────────────────────────────────
_DIAGNOSIS_LEX = [
    "tăng huyết áp vô căn", "tăng huyết áp", "đái tháo đường type 2",
    "đái tháo đường típ 2", "đái tháo đường", "tăng lipid máu", "suy tim",
    "nhồi máu cơ tim", "rung nhĩ", "xơ gan", "hội chứng não gan",
    "bệnh phổi tắc nghẽn mạn tính", "trào ngược dạ dày - thực quản",
    "trào ngược dạ dày", "đột quỵ", "thiếu máu", "viêm phổi", "viêm tụy",
    "suy thận", "bệnh tim mạch do xơ vữa động mạch", "hội chứng mạch vành cấp",
    "ngừng thở khi ngủ", "béo phì", "phình động mạch chủ",
]
_SYMPTOM_LEX = [
    "đau ngực", "khó thở khi gắng sức", "khó thở về đêm", "khó thở khi nằm",
    "khó thở", "đánh trống ngực", "tức ngực", "đau thượng vị", "đau bụng",
    "đau đầu", "đau chân", "ho có đờm", "ho đờm xanh", "ho", "sốt", "buồn nôn",
    "nôn", "chóng mặt", "choáng váng", "mệt mỏi", "phù chi dưới",
    "phù mắt cá chân", "phù", "ngất xỉu", "ngất", "ợ hơi", "mất ngủ", "lo âu",
    "táo bón", "tiêu chảy", "chảy máu mũi", "khó nuốt", "đổ mồ hôi",
]


def _lexicon_regex(terms: list[str]) -> re.Pattern:
    # sắp dài -> ngắn để ưu tiên khớp cụm dài; \b unicode-aware quanh diacritics.
    ordered = sorted(set(terms), key=len, reverse=True)
    alt = "|".join(re.escape(t) for t in ordered)
    return re.compile(r"\b(?:" + alt + r")\b", re.IGNORECASE)


_DIAGNOSIS_RE = _lexicon_regex(_DIAGNOSIS_LEX)
_SYMPTOM_RE = _lexicon_regex(_SYMPTOM_LEX)

# ưu tiên khi chồng lấn (cao thắng); tie-break bằng độ dài span.
_PRIORITY = {
    ConceptType.THUOC: 5,
    ConceptType.KET_QUA_XET_NGHIEM: 4,
    ConceptType.TEN_XET_NGHIEM: 3,
    ConceptType.CHAN_DOAN: 2,
    ConceptType.TRIEU_CHUNG: 1,
}


def _trim_leading_stop(text: str, start: int, end: int) -> int:
    """Bỏ token ascii mở đầu là từ nối tiếng Việt (vd 'cho' trong 'được cho X')."""
    while True:
        m = re.match(r"\s*([A-Za-z]+)\s+", text[start:end])
        if not m or m.group(1).lower() not in _LEADING_STOP:
            return start
        start += m.end()


def _collect(text: str) -> list[tuple[int, int, ConceptType]]:
    spans: list[tuple[int, int, ConceptType]] = []

    for m in _DRUG_RE.finditer(text):
        start = _trim_leading_stop(text, m.start(), m.end())
        spans.append((start, m.end(), ConceptType.THUOC))

    for m in _LAB_RESULT_RE.finditer(text):
        spans.append((m.start(), m.end(), ConceptType.KET_QUA_XET_NGHIEM))

    for m in _LAB_NAME_RE.finditer(text):
        if m.group("abbr").lower() in _LAB_ABBR:
            spans.append((m.start(), m.end(), ConceptType.TEN_XET_NGHIEM))

    for m in _DIAGNOSIS_RE.finditer(text):
        spans.append((m.start(), m.end(), ConceptType.CHAN_DOAN))

    for m in _SYMPTOM_RE.finditer(text):
        spans.append((m.start(), m.end(), ConceptType.TRIEU_CHUNG))

    return spans


def _resolve_overlaps(
    spans: list[tuple[int, int, ConceptType]],
) -> list[tuple[int, int, ConceptType]]:
    # sắp theo: ưu tiên cao trước, span dài trước -> greedy giữ, bỏ cái chồng lấn.
    spans = sorted(
        spans,
        key=lambda s: (-_PRIORITY[s[2]], -(s[1] - s[0]), s[0]),
    )
    kept: list[tuple[int, int, ConceptType]] = []
    for s in spans:
        if any(s[0] < k[1] and k[0] < s[1] for k in kept):  # có giao
            continue
        kept.append(s)
    return sorted(kept, key=lambda s: (s[0], s[1]))


def extract(text: str) -> list[Concept]:
    """Trích khái niệm y tế từ 1 văn bản. candidates/assertions để rỗng (Tầng 1)."""
    resolved = _resolve_overlaps(_collect(text))
    concepts: list[Concept] = []
    for start, end, ctype in resolved:
        concepts.append(
            Concept(text=text[start:end], type=ctype, position=(start, end))
        )
    return concepts
