"""Word Error Rate trên trường `text` (DeBai.txt, Metric đánh giá).

WER = (S + D + I) / N_ref  — edit distance mức TỪ (Levenshtein) giữa chuỗi tham chiếu
và chuỗi giả thuyết, chia số từ tham chiếu.

Tokenize: tách theo khoảng trắng (mặc định). Có thể bật lowercase để normalize hoa/thường.
text_score của BTC = mean_i (1 - WER(i)); WER có thể > 1 khi nhiều insertion.
"""

from __future__ import annotations


def _tokenize(s: str, lowercase: bool) -> list[str]:
    if lowercase:
        s = s.lower()
    return s.split()


def word_error_rate(reference: str, hypothesis: str, *, lowercase: bool = False) -> float:
    ref = _tokenize(reference, lowercase)
    hyp = _tokenize(hypothesis, lowercase)

    if not ref and not hyp:
        return 0.0
    if not ref:
        # Không có từ tham chiếu nhưng có dự đoán -> sai hoàn toàn.
        return 1.0

    # Levenshtein DP mức từ.
    n, m = len(ref), len(hyp)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,        # deletion
                curr[j - 1] + 1,    # insertion
                prev[j - 1] + cost, # substitution / match
            )
        prev = curr
    return prev[m] / n
