"""Tầng 2 — Entity Linking (40% điểm): THUỐC->RxNorm, CHẨN_ĐOÁN->ICD-10.

Interface thống nhất `link(text, concept_type)` -> list[Candidate(code, score, method, kb_name)].
KB nạp 1 lần (lazy singleton) từ config/kb.yaml — swap prescribe<->full không sửa code.
"""

from __future__ import annotations

from functools import lru_cache

from src.linking.icd_linker import IcdLinker
from src.linking.kb import KnowledgeBase
from src.linking.matcher import DrugMatcher


@lru_cache(maxsize=1)
def _kb() -> KnowledgeBase:
    return KnowledgeBase.from_config()


@lru_cache(maxsize=1)
def _drug() -> DrugMatcher:
    return DrugMatcher(_kb())


@lru_cache(maxsize=1)
def _icd() -> IcdLinker:
    return IcdLinker(_kb())


def link(text: str, concept_type: str, top_k: int = 5) -> list:
    """concept_type: 'THUỐC' -> RxNorm; 'CHẨN_ĐOÁN' -> ICD-10. Khác -> []."""
    if concept_type == "THUỐC":
        return _drug().match(text, top_k=top_k)
    if concept_type == "CHẨN_ĐOÁN":
        return _icd().link(text, top_k=top_k)
    return []
