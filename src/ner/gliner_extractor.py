"""Module 1 — NER bằng GLiNER (zero-shot, multilingual).

Chunk theo ranh giới DÒNG, giữ offset tuyệt đối về file gốc → bất biến
`input[start:end] == text` luôn đúng (chunk là substring nguyên văn, không normalize).

Xem docs/baseline-implementation.md §2.
"""

from __future__ import annotations

import re
from functools import lru_cache

from src.schema import Concept, ConceptType

# nhãn GLiNER = prompt tiếng Việt NGẮN (zero-shot nhạy với cách diễn đạt) -> ConceptType.
# Tuned trên dev/gold (20 file): prompt ngắn "bệnh"/"xét nghiệm" + thr 0.2 cho relaxed
# recall 0.74 (vs 0.43 với prompt dài). KẾT_QUẢ vẫn ~0 (GLiNER không tag số trần → cần regex).
_LABELS: dict[str, ConceptType] = {
    "triệu chứng": ConceptType.TRIEU_CHUNG,
    "xét nghiệm": ConceptType.TEN_XET_NGHIEM,
    "chỉ số kết quả xét nghiệm": ConceptType.KET_QUA_XET_NGHIEM,
    "bệnh": ConceptType.CHAN_DOAN,
    "thuốc": ConceptType.THUOC,
}
_LABEL_LIST = list(_LABELS.keys())
_MODEL_NAME = "urchade/gliner_multi-v2.1"

# Nới span THUỐC sang phải: GLiNER bắt đúng tên nhưng cắt đuôi liều+đường+tần suất.
# Chỉ dùng [ \t] (KHÔNG \n) để không nuốt lấn sang thuốc ở dòng kế trong med-list.
_SP = r"[ \t]+"
_DOSE_TAIL = re.compile(
    rf"(?:{_SP}?\d+(?:[.,]\d+)?(?:-\d+(?:[.,]\d+)?)?{_SP}?"
    r"(?:mg/ml|mcg/ml|meq/ml|mg|mcg|meq|units?|iu|ml|gram|g|%|cc))?"     # liều (optional)
    rf"(?:{_SP}(?:ml|cc|tab|viên))?"                                     # đơn vị thể tích trần
    rf"(?:{_SP}(?:po|iv|im|sc|sq|sl|pr|inhaled|nebulizer|nebs?|oral|susp\w*|topical|gtt))*"  # đường
    rf"(?:{_SP}(?:daily|bid|tid|qid|qhs|qam|qpm|qd|qod|q\d+h|q\d+hr|prn|once|weekly|nightly)(?::\w+)?)*",  # tần suất
    re.I,
)


def _expand_drug(text: str, end: int) -> int:
    """Nới `end` của span THUỐC để nuốt trọn đuôi liều/đường/tần suất. Offset gốc -> hợp lệ."""
    m = _DOSE_TAIL.match(text, end)
    if not m or m.end() <= end:
        return end
    e = m.end()
    while e > end and text[e - 1] in " \t\r\n":   # cắt khoảng trắng cuối
        e -= 1
    return e
_WS = " \t\r\n "


@lru_cache(maxsize=1)
def _model():
    from gliner import GLiNER
    return GLiNER.from_pretrained(_MODEL_NAME)


def _chunks(text: str, max_chars: int = 384) -> list[tuple[int, str]]:
    """Cắt theo dòng, gộp tới ~max_chars. Trả (offset_tuyệt_đối, chuỗi_con_nguyên_văn)."""
    out: list[tuple[int, str]] = []
    pos = 0
    n = len(text)
    while pos < n:
        end = min(pos + max_chars, n)
        if end < n:
            nl = text.rfind("\n", pos, end)     # cắt tại newline gần nhất
            if nl > pos:
                end = nl + 1
        chunk = text[pos:end]
        if chunk.strip():
            out.append((pos, chunk))
        pos = end
    return out


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in _WS:
        start += 1
    while end > start and text[end - 1] in _WS:
        end -= 1
    return start, end


def _resolve_overlaps(spans: list[tuple[int, int, ConceptType, float]]):
    # greedy: score cao trước; bỏ span giao với span đã giữ.
    spans = sorted(spans, key=lambda s: -s[3])
    kept: list[tuple[int, int, ConceptType, float]] = []
    for s in spans:
        if any(s[0] < k[1] and k[0] < s[1] for k in kept):
            continue
        kept.append(s)
    return sorted(kept, key=lambda s: (s[0], s[1]))


def extract(text: str, threshold: float = 0.2) -> list[Concept]:
    model = _model()
    chunks = _chunks(text)
    spans: list[tuple[int, int, ConceptType, float]] = []
    for base, chunk in chunks:
        for e in model.predict_entities(chunk, _LABEL_LIST, threshold=threshold):
            ctype = _LABELS.get(e["label"])
            if ctype is None:
                continue
            s, en = _trim(text, base + e["start"], base + e["end"])
            if en - s < 2:
                continue
            if ctype is ConceptType.THUOC:        # nới đuôi liều/đường/tần suất
                en = _expand_drug(text, en)
            spans.append((s, en, ctype, float(e["score"])))

    concepts: list[Concept] = []
    for s, en, ctype, _score in _resolve_overlaps(spans):
        span_text = text[s:en]
        assert span_text == text[s:en]  # bất biến offset (chunk là substring nguyên văn)
        concepts.append(Concept(text=span_text, type=ctype, position=(s, en)))
    return concepts
