"""Jaccard cho assertions và candidates.

Lưu ý: Jaccard = 1 khi cả GT lẫn prediction đều rỗng (để rỗng đúng cách vẫn được điểm).
candidates weighted theo len(ground_truth).
"""


def jaccard(gt: set, pred: set) -> float:
    raise NotImplementedError
