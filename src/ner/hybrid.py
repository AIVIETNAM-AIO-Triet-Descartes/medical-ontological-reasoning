"""NER hybrid: GLiNER (triệu chứng/chẩn đoán/thuốc) + regex (2 loại xét nghiệm).

GLiNER yếu với số trần & viết tắt xét nghiệm → giao 2 loại đó cho lab_regex;
giữ 3 loại còn lại cho GLiNER. Gộp + giải chồng lấn.
"""

from __future__ import annotations

from src.ner import gliner_extractor, lab_regex
from src.schema import Concept, ConceptType

_LAB_TYPES = {ConceptType.TEN_XET_NGHIEM, ConceptType.KET_QUA_XET_NGHIEM}


def _resolve(concepts: list[Concept]) -> list[Concept]:
    # span dài hơn thắng khi chồng lấn (greedy).
    concepts = sorted(concepts, key=lambda c: -(c.position[1] - c.position[0]))
    kept: list[Concept] = []
    for c in concepts:
        s, e = c.position
        if any(s < k.position[1] and k.position[0] < e for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda c: (c.position[0], c.position[1]))
    return kept


def extract(text: str, threshold: float = 0.2) -> list[Concept]:
    g = [c for c in gliner_extractor.extract(text, threshold=threshold)
         if c.type not in _LAB_TYPES]        # GLiNER: bỏ 2 loại xét nghiệm
    lab = lab_regex.extract(text)             # regex: 2 loại xét nghiệm
    return _resolve(g + lab)
