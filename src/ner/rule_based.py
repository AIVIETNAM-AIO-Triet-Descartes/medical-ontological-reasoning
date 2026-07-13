"""Baseline rule-based NER: regex medication list + pattern 'điều trị X' -> TRIỆU_CHỨNG."""

# TODO: regex 'số. tên_thuốc liều đường_dùng tần_suất' cho THUỐC;
#       heuristic section header cho xét nghiệm / triệu chứng.


def extract(text: str):
    raise NotImplementedError
