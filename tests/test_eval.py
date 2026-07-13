"""Kiểm công thức WER/Jaccard/harness khớp DeBai.txt.

Chạy: python -m tests.test_eval   (hoặc: pytest tests/test_eval.py)
"""

from __future__ import annotations

from src.eval.harness import score, score_sample
from src.eval.jaccard import jaccard
from src.eval.wer import word_error_rate
from src.schema import Assertion, Concept, ConceptType


def _c(text, type_, pos, assertions=(), candidates=()):
    return Concept(
        text=text,
        type=type_,
        position=pos,
        assertions=[Assertion(a) for a in assertions],
        candidates=list(candidates),
    )


def test_jaccard_rules():
    # cả hai rỗng -> 1
    assert jaccard([], []) == 1.0
    # gt rỗng, pred khác rỗng -> 0
    assert jaccard([], ["x"]) == 0.0
    # gt khác rỗng, pred rỗng -> 0
    assert jaccard(["x"], []) == 0.0
    # trùng hoàn toàn -> 1
    assert jaccard(["a", "b"], ["b", "a"]) == 1.0
    # {a,b} vs {b,c} -> 1/3
    assert abs(jaccard(["a", "b"], ["b", "c"]) - 1 / 3) < 1e-9


def test_wer_basic():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("a b c", "a b c") == 0.0
    # 1 substitution / 3 -> 1/3
    assert abs(word_error_rate("a b c", "a x c") - 1 / 3) < 1e-9
    # ref rỗng, hyp khác rỗng -> 1
    assert word_error_rate("", "a b") == 1.0
    # 1 deletion / 3
    assert abs(word_error_rate("a b c", "a c") - 1 / 3) < 1e-9


def test_perfect_match():
    gold = [
        _c("ho", ConceptType.TRIEU_CHUNG, (0, 2)),
        _c("aspirin 81 mg", ConceptType.THUOC, (10, 23), ["isHistorical"], ["243670"]),
    ]
    pred = [
        _c("ho", ConceptType.TRIEU_CHUNG, (0, 2)),
        _c("aspirin 81 mg", ConceptType.THUOC, (10, 23), ["isHistorical"], ["243670"]),
    ]
    rep = score({"1": gold}, {"1": pred})
    assert abs(rep.text_score - 1.0) < 1e-9
    assert abs(rep.assertions_score - 1.0) < 1e-9
    assert abs(rep.candidates_score - 1.0) < 1e-9
    assert abs(rep.final_score - 1.0) < 1e-9


def test_wrong_type_double_penalty():
    # gt: TRIỆU_CHỨNG tại (0,5); pred: CHẨN_ĐOÁN cùng span -> 2 khoá khác nhau.
    gold = [_c("abcde", ConceptType.TRIEU_CHUNG, (0, 5))]
    pred = [_c("abcde", ConceptType.CHAN_DOAN, (0, 5), candidates=["K00"])]
    s = score_sample(gold, pred)
    # assertions: gt TRIỆU_CHỨNG (rỗng) vs không có pred -> jaccard([],[]) =1 ;
    #   pred CHẨN_ĐOÁN (rỗng assertion) vs không gt -> jaccard([],[]) =1
    #   -> j_assertions = 1.0 (assertion cả hai đều rỗng, không bị phạt ở đây)
    # candidates: chỉ CHẨN_ĐOÁN (pred-only) -> jaccard(gt=[], pred=[K00]) = 0
    assert s.j_candidates == 0.0
    # text WER: "abcde" vs "abcde" -> 0 (text đúng, nhưng type sai bị phạt ở candidates)
    assert s.wer == 0.0


def test_debai_multi_icd_example():
    # "bệnh trào ngược dạ dày - thực quản" -> gt K21.0, K21.9
    gold = [_c("trào ngược", ConceptType.CHAN_DOAN, (0, 10), candidates=["K21.0", "K21.9"])]
    # pred chỉ trả 1 mã đúng -> jaccard = |{K21.0}| / |{K21.0,K21.9}| = 1/2
    pred = [_c("trào ngược", ConceptType.CHAN_DOAN, (0, 10), candidates=["K21.0"])]
    s = score_sample(gold, pred)
    assert abs(s.j_candidates - 0.5) < 1e-9
    # weight = len(gt_codes)+1 = 3
    assert s.weight_candidates == 3.0


def test_candidates_weighting_across_samples():
    # sample A: 1 concept, 2 gt codes, pred đúng 1 -> J=0.5, W=3
    a_gold = [_c("dx", ConceptType.CHAN_DOAN, (0, 2), candidates=["A", "B"])]
    a_pred = [_c("dx", ConceptType.CHAN_DOAN, (0, 2), candidates=["A"])]
    # sample B: 1 concept, 1 gt code, pred sai -> J=0, W=2
    b_gold = [_c("drug", ConceptType.THUOC, (0, 4), candidates=["X"])]
    b_pred = [_c("drug", ConceptType.THUOC, (0, 4), candidates=["Y"])]
    rep = score({"A": a_gold, "B": b_gold}, {"A": a_pred, "B": b_pred})
    # candidates_score = (0.5*3 + 0*2)/(3+2) = 1.5/5 = 0.3
    assert abs(rep.candidates_score - 0.3) < 1e-9


def test_empty_prediction():
    gold = [_c("aspirin", ConceptType.THUOC, (0, 7), ["isHistorical"], ["243670"])]
    rep = score({"1": gold}, {"1": []})
    # text: ref="aspirin" hyp="" -> WER=1 -> text_score=0
    assert abs(rep.text_score - 0.0) < 1e-9
    # assertions: THUỐC gt {isHistorical} vs pred rỗng -> 0
    assert abs(rep.assertions_score - 0.0) < 1e-9
    # candidates: gt {243670} vs rỗng -> 0
    assert abs(rep.candidates_score - 0.0) < 1e-9


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
