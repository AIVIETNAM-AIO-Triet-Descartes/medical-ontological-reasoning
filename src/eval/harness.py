"""Chấm điểm tổng: final = 0.3·text + 0.3·assertions + 0.4·candidates.

Sai type bị phạt kép (0 điểm cả 3 metric) -> khi không chắc type, thà bỏ span.
Chạy: python -m src.eval.harness
"""


def score(gold: list, pred: list) -> dict:
    raise NotImplementedError


if __name__ == "__main__":
    raise NotImplementedError
