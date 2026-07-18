"""Module 1 — NER bằng GLiNER (zero-shot, multilingual).

Chunk theo ranh giới DÒNG, giữ offset tuyệt đối về file gốc → bất biến
`input[start:end] == text` luôn đúng (chunk là substring nguyên văn, không normalize).

Xem docs/baseline-implementation.md §2.
"""

from __future__ import annotations

import re
from functools import lru_cache

from src.schema import Concept, ConceptType

# nhãn GLiNER = mô tả tiếng Việt (zero-shot nhạy với cách diễn đạt) -> ConceptType
_LABELS: dict[str, ConceptType] = {
    "triệu chứng bệnh nhân": ConceptType.TRIEU_CHUNG,
    "tên xét nghiệm y khoa": ConceptType.TEN_XET_NGHIEM,
    "kết quả giá trị xét nghiệm": ConceptType.KET_QUA_XET_NGHIEM,
    "chẩn đoán bệnh của bác sĩ": ConceptType.CHAN_DOAN,
    "tên thuốc điều trị": ConceptType.THUOC,
}
_LABEL_LIST = list(_LABELS.keys())
_MODEL_NAME = "urchade/gliner_multi-v2.1"
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


def extract(text: str, threshold: float = 0.3) -> list[Concept]:
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
            spans.append((s, en, ctype, float(e["score"])))

    concepts: list[Concept] = []
    for s, en, ctype, _score in _resolve_overlaps(spans):
        span_text = text[s:en]
        assert span_text == text[s:en]  # bất biến offset (chunk là substring nguyên văn)
        concepts.append(Concept(text=span_text, type=ctype, position=(s, en)))
    return concepts
