"""CHẨN_ĐOÁN -> ICD-10. 1 chẩn đoán có thể nhiều mã (vd K21.0 + K21.9) -> trả list."""

# TODO: normalize thuật ngữ VN <-> mô tả ICD-10; embedding đa ngữ cho retrieval.


def link_diagnosis(dx: str) -> list[str]:
    raise NotImplementedError
