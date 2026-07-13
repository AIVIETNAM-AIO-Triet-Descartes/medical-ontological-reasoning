"""Evaluation harness local — tái hiện công thức chấm điểm của BTC (DeBai.txt).

    final_score = 0.3·text_score + 0.3·assertions_score + 0.4·candidates_score

    text_score       = Σ_i (1 - WER(i)) / len(test)
    assertions_score = Σ_i J_assertions(i) / len(test)
    candidates_score = Σ_i J_candidates(i)·W_i / Σ_i W_i,  W_i = Σ_{k∈i}(len(gt_codes(k))+1)

Trong đó i là 1 sample (1 file), k là 1 concept có candidate trong sample i,
J_X(i) = trung bình Jaccard trên field X của các concept trong sample i.

────────────────────────────────────────────────────────────────────────────
3 GIẢ ĐỊNH cần BTC/leaderboard xác nhận (spec không nói rõ) — để cấu hình được:

  [A1] WER(i) gộp ra sao khi 1 sample nhiều concept?
       -> nối `text` các concept theo thứ tự position thành 1 chuỗi ref vs hyp.
       (Phương án khác: WER trung bình từng concept đã-khớp.)

  [A2] Khớp concept gt<->pred để tính Jaccard bằng khoá nào?
       -> (type, start, end) exact. Lệch offset -> coi như concept khác.

  [A3] k chạy trên tập nào?
       -> UNION khoá gt ∪ pred (gồm cả false-positive concept do pred sinh thừa).
       Khớp Lưu ý BTC: concept sai loại bị tính thêm 1 lần với 0 điểm.
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from src.eval.jaccard import jaccard
from src.eval.wer import word_error_rate
from src.schema import (
    TYPES_WITH_ASSERTIONS,
    TYPES_WITH_CANDIDATES,
    Concept,
)

WEIGHTS = {"text": 0.3, "assertions": 0.3, "candidates": 0.4}


@dataclass
class SampleScore:
    wer: float
    j_assertions: float
    j_candidates: float
    weight_candidates: float  # W_i = Σ_k (len(gt_codes(k)) + 1)


def _sorted_texts(concepts: list[Concept]) -> str:
    ordered = sorted(concepts, key=lambda c: (c.position[0], c.position[1]))
    return " ".join(c.text for c in ordered)


def score_sample(
    gold: list[Concept],
    pred: list[Concept],
    *,
    lowercase_wer: bool = False,
) -> SampleScore:
    """Tính (WER, J_assert, J_cand, W) cho 1 sample."""
    # [A1] WER trên chuỗi text nối theo position.
    wer = word_error_rate(_sorted_texts(gold), _sorted_texts(pred), lowercase=lowercase_wer)

    # [A2] map theo khoá (type, start, end).
    gold_map = {c.key(): c for c in gold}
    pred_map = {c.key(): c for c in pred}
    all_keys = set(gold_map) | set(pred_map)  # [A3] union

    # assertions: các concept thuộc loại có assertion.
    assert_jaccs: list[float] = []
    for k in all_keys:
        if k[0] not in TYPES_WITH_ASSERTIONS:
            continue
        gt_a = gold_map[k].assertions if k in gold_map else []
        pr_a = pred_map[k].assertions if k in pred_map else []
        assert_jaccs.append(jaccard(gt_a, pr_a))
    # Sample không có concept mang assertion -> 1.0 (không có gì để sai).
    j_assertions = sum(assert_jaccs) / len(assert_jaccs) if assert_jaccs else 1.0

    # candidates: các concept thuộc loại có candidate.
    cand_jaccs: list[float] = []
    weight = 0.0
    for k in all_keys:
        if k[0] not in TYPES_WITH_CANDIDATES:
            continue
        gt_c = gold_map[k].candidates if k in gold_map else []
        pr_c = pred_map[k].candidates if k in pred_map else []
        cand_jaccs.append(jaccard(gt_c, pr_c))
        weight += len(gt_c) + 1  # len(ground_truth(k)) + 1
    j_candidates = sum(cand_jaccs) / len(cand_jaccs) if cand_jaccs else 1.0

    return SampleScore(wer=wer, j_assertions=j_assertions,
                       j_candidates=j_candidates, weight_candidates=weight)


@dataclass
class Report:
    text_score: float
    assertions_score: float
    candidates_score: float
    final_score: float
    n_samples: int
    per_sample: list[SampleScore]


def score(
    gold: dict[str, list[Concept]],
    pred: dict[str, list[Concept]],
    *,
    lowercase_wer: bool = False,
) -> Report:
    """Chấm toàn tập. gold/pred: {sample_id -> list[Concept]}.

    Sample thiếu trong pred -> coi như dự đoán rỗng.
    """
    ids = sorted(gold.keys())
    n = len(ids)
    if n == 0:
        return Report(0.0, 0.0, 0.0, 0.0, 0, [])

    per_sample: list[SampleScore] = []
    sum_text = 0.0
    sum_assert = 0.0
    cand_num = 0.0
    cand_den = 0.0
    for sid in ids:
        s = score_sample(gold[sid], pred.get(sid, []), lowercase_wer=lowercase_wer)
        per_sample.append(s)
        sum_text += 1.0 - s.wer
        sum_assert += s.j_assertions
        cand_num += s.j_candidates * s.weight_candidates
        cand_den += s.weight_candidates

    text_score = sum_text / n
    assertions_score = sum_assert / n
    candidates_score = cand_num / cand_den if cand_den > 0 else 1.0
    final = (
        WEIGHTS["text"] * text_score
        + WEIGHTS["assertions"] * assertions_score
        + WEIGHTS["candidates"] * candidates_score
    )
    return Report(text_score, assertions_score, candidates_score, final, n, per_sample)


def _cli() -> None:
    from src.utils.io import load_concept_dir

    ap = argparse.ArgumentParser(description="Chấm điểm local theo công thức BTC.")
    ap.add_argument("--gold", required=True, help="Thư mục *.json ground-truth (tự gán).")
    ap.add_argument("--pred", required=True, help="Thư mục *.json prediction.")
    ap.add_argument("--lowercase-wer", action="store_true", help="Chuẩn hoá hoa/thường khi tính WER.")
    args = ap.parse_args()

    gold = load_concept_dir(args.gold)
    pred = load_concept_dir(args.pred)
    rep = score(gold, pred, lowercase_wer=args.lowercase_wer)

    print(f"samples          : {rep.n_samples}")
    print(f"text_score       : {rep.text_score:.4f}")
    print(f"assertions_score : {rep.assertions_score:.4f}")
    print(f"candidates_score : {rep.candidates_score:.4f}")
    print(f"final_score      : {rep.final_score:.4f}")


if __name__ == "__main__":
    _cli()
