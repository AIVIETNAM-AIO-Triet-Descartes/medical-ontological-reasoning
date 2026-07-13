"""Hợp đồng dữ liệu chung: Concept + các Enum. Dùng xuyên suốt 3 tầng pipeline.

Ma trận field theo type (từ DeBai.txt §3.2):
    type                 | assertions | candidates
    ---------------------|:----------:|:----------------:
    TRIỆU_CHỨNG          |    ✅      |     ❌
    CHẨN_ĐOÁN            |    ✅      |     ✅ ICD-10
    THUỐC                |    ✅      |     ✅ RxNorm
    TÊN_XÉT_NGHIỆM       |    ❌      |     ❌
    KẾT_QUẢ_XÉT_NGHIỆM   |    ❌      |     ❌

position: [start, end) — offset ký tự nửa mở, 0-indexed. input[start:end] == text.
(Xác nhận từ ví dụ DeBai: "amlodipine 10 mg po daily" tại [58, 83], 83-58 = 25 = len.)
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

    candidates: list mã (ICD-10 hoặc RxCUI) — list vì 1 khái niệm có thể nhiều mã.
    assertions: subset của {isNegated, isFamily, isHistorical}.
    """

    text: str
    type: ConceptType
    position: tuple[int, int]
    assertions: list[Assertion] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Concept":
        pos = d.get("position", [0, 0])
        return cls(
            text=d.get("text", ""),
            type=ConceptType(d["type"]),
            position=(int(pos[0]), int(pos[1])),
            assertions=[Assertion(a) for a in d.get("assertions", []) or []],
            candidates=[str(c) for c in d.get("candidates", []) or []],
        )

    def to_dict(self) -> dict:
        out: dict = {
            "text": self.text,
            "type": self.type.value,
            "position": [self.position[0], self.position[1]],
        }
        # Chỉ xuất field hợp lệ theo loại (khớp ví dụ output BTC).
        if self.type in TYPES_WITH_CANDIDATES:
            out["candidates"] = list(self.candidates)
        if self.type in TYPES_WITH_ASSERTIONS:
            out["assertions"] = [a.value for a in self.assertions]
        return out

    def key(self) -> tuple:
        """Khoá định danh concept để khớp gt <-> pred: (type, start, end).

        Note: gồm `type` nên đoán đúng span nhưng sai loại -> khoá khác -> 2 concept
        rời, mỗi cái 0 điểm (khớp Lưu ý metric của BTC).
        """
        return (self.type, self.position[0], self.position[1])
