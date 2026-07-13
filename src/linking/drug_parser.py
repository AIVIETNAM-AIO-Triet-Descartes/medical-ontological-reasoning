"""Parse chuỗi thuốc -> hoạt chất / hàm lượng / đơn vị (MG vs MG/ML) / dạng / tần suất.

Hàm lượng + đơn vị quyết định mã RxCUI (clonazepam 0.5 vs 1.5 -> mã khác).
"""

# TODO: parser cho 'amlodipine 10 mg po daily'; xử lý MG/ML (nồng độ).


def parse(drug_str: str) -> dict:
    raise NotImplementedError
