"""Jaccard similarity cho assertions và candidates (DeBai.txt, Metric đánh giá).

Định nghĩa J_X(i) của BTC:
    - = 1 nếu len(gt) = 0 VÀ len(pred) = 0
    - = 0 nếu len(gt) = 0 VÀ len(pred) != 0
    - = |gt ∩ pred| / |gt ∪ pred| trong các trường hợp còn lại

Cả 3 nhánh gom lại chính là: 1.0 nếu union rỗng, ngược lại |∩|/|∪|.
(Kiểm chứng: gt rỗng & pred khác rỗng -> |∩|=0, |∪|=|pred|>0 -> 0, đúng nhánh 2.
 gt khác rỗng & pred rỗng -> 0/|gt| = 0, thuộc "các trường hợp còn lại".)
"""

from __future__ import annotations

from collections.abc import Iterable


def jaccard(gt: Iterable, pred: Iterable) -> float:
    gt_set = set(gt)
    pred_set = set(pred)
    union = gt_set | pred_set
    if not union:
        return 1.0
    return len(gt_set & pred_set) / len(union)
