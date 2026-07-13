"""Pipeline chính: 1 file text -> list[Concept].

Thứ tự: NER (span+type) -> Linking (candidates cho THUỐC/CHẨN_ĐOÁN)
        -> Assertion (cho THUỐC/CHẨN_ĐOÁN/TRIỆU_CHỨNG).
"""

from src.schema import Concept


def process_document(text: str) -> list[Concept]:
    # TODO: gọi tầng 1/2/3 theo config.
    raise NotImplementedError
