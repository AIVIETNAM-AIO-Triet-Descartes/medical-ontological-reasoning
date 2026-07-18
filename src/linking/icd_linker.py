"""Linker CHẨN_ĐOÁN -> ICD-10 bản Việt (linking VN↔VN).

KB có TÊN BỆNH tiếng Việt (data/kb/icd10_vn.parquet) → không cần embedding đa ngữ.
Cascade: exact (chuẩn hoá) → fuzzy (rapidfuzz trên tên bệnh VN).
Embedding đa ngữ để dành làm tầng dự phòng (chưa bật ở baseline này).

Chuẩn hoá tên bệnh: lowercase, bỏ tiền tố "bệnh ", bỏ cụm trong ngoặc, gộp khoảng trắng
— vì tên KB kiểu "Bệnh tăng huyết áp vô căn (nguyên phát)" còn diễn đạt trong note ngắn hơn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property

from rapidfuzz import fuzz, process

from src.linking.kb import KnowledgeBase

_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\([^)]*\)")
_LEAD_BENH = re.compile(r"^bệnh\s+")


def _norm_dx(s: str) -> str:
    s = s.lower().strip()
    s = _PAREN.sub(" ", s)          # bỏ (nguyên phát), (primary)...
    s = _LEAD_BENH.sub("", s)       # bỏ tiền tố "bệnh "
    return _WS.sub(" ", s).strip()


@dataclass
class Candidate:
    code: str
    score: float
    method: str          # exact | fuzzy | embed
    kb_name: str = "icd_vn"


class IcdLinker:
    def __init__(self, kb: KnowledgeBase, fuzzy_threshold: float = 80.0):
        self.kb = kb
        self.fuzzy_threshold = fuzzy_threshold

    @cached_property
    def _norm_to_codes(self) -> dict[str, list[str]]:
        idx: dict[str, list[str]] = {}
        for name, code in zip(self.kb.icd["ten_benh_vn"], self.kb.icd["code_dotted"]):
            key = _norm_dx(str(name))
            if key:
                idx.setdefault(key, []).append(str(code))
        return idx

    @cached_property
    def _keys(self) -> list[str]:
        return list(self._norm_to_codes.keys())

    def link(self, text: str, top_k: int = 5) -> list[Candidate]:
        q = _norm_dx(text)
        if not q:
            return []
        # 1) exact trên tên đã chuẩn hoá
        if q in self._norm_to_codes:
            return [Candidate(c, 1.0, "exact") for c in self._norm_to_codes[q]][:top_k]
        # 2) fuzzy
        hits = process.extract(
            q, self._keys, scorer=fuzz.token_sort_ratio,
            score_cutoff=self.fuzzy_threshold, limit=top_k,
        )
        out: list[Candidate] = []
        seen: set[str] = set()
        for key, score, _ in hits:
            for c in self._norm_to_codes[key]:
                if c not in seen:
                    seen.add(c)
                    out.append(Candidate(c, score / 100.0, "fuzzy"))
        return out[:top_k]
