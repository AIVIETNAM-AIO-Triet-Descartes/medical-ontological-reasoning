"""Parse số trong văn bản VN: dấu phẩy thập phân (14,43) LẪN dấu chấm (troponin 0.01).

Dùng cho KẾT_QUẢ_XÉT_NGHIỆM (giá trị + đơn vị).
"""

# TODO: phân biệt phẩy thập phân vs phẩy nghìn (21,000); giữ đơn vị.


def parse_number(token: str) -> float:
    raise NotImplementedError
