"""Rule-based assertion: ConText/NegEx.

Trigger:
- section header 'thuốc trước nhập viện' -> isHistorical toàn section.
- cụm 'tiền sử' / 'tiền căn' trong câu -> isHistorical (bắt trong narrative, không chỉ header).
- 'không' / 'phủ nhận' -> isNegated.
- 'gia đình' / 'mẹ' / 'bố' ... -> isFamily.
"""

# TODO: danh sách trigger phrase VN + phạm vi (scope) áp dụng.


def detect(text: str, span: tuple[int, int]) -> list:
    raise NotImplementedError
