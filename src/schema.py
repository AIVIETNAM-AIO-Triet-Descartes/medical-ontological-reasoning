"""Hợp đồng dữ liệu chung: Concept + các Enum. Dùng xuyên suốt 3 tầng pipeline.

Ma trận field theo type (từ research.md §1):
    type                 | assertions | candidates
    ---------------------|:----------:|:----------------:
    TRIỆU_CHỨNG          |    ✅      |     ❌
    CHẨN_ĐOÁN            |    ✅      |     ✅ ICD-10
    THUỐC                |    ✅      |     ✅ RxNorm
    TÊN_XÉT_NGHIỆM       |    ❌      |     ❌
    KẾT_QUẢ_XÉT_NGHIỆM   |    ❌      |     ❌
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConceptType(str, Enum):
    TRIEU_CHUNG = "TRIỆU_CHỨNG"
    TEN_XET_NGHIEM = "TÊN_XÉT_NGHIỆM"
    KET_QUA_XET_NGHIEM = "KẾT_QUẢ_XÉT_NGHIỆM"
    CHAN_DOAN = "CHẨN_ĐOÁN"
    THUOC = "THUỐC"


class Assertion(str, Enum):
    NEGATED = "isNegated"
    FAMILY = "isFamily"
    HISTORICAL = "isHistorical"


# type nào được phép có assertions / candidates
TYPES_WITH_ASSERTIONS = {
    ConceptType.TRIEU_CHUNG,
    ConceptType.CHAN_DOAN,
    ConceptType.THUOC,
}
TYPES_WITH_CANDIDATES = {
    ConceptType.CHAN_DOAN,  # ICD-10
    ConceptType.THUOC,      # RxNorm
}


@dataclass
class Concept:
    """Một khái niệm trích xuất từ văn bản.

    position: offset ký tự [start, end) trong text gốc (quan trọng cho WER).
    candidates: list mã (ICD-10 hoặc RxCUI) — list vì 1 khái niệm có thể nhiều mã.
    assertions: subset của {isNegated, isFamily, isHistorical}.
    """

    text: str
    type: ConceptType
    position: tuple[int, int]
    assertions: list[Assertion] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        # TODO: chốt đúng format JSON BTC yêu cầu (key names, position schema)
        raise NotImplementedError
