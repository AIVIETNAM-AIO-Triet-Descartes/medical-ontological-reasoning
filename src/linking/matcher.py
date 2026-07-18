"""Cascade matcher THUỐC -> RxCUI. Trả list Candidate xếp hạng.

Tầng:
  1. exact       — chuỗi chuẩn hoá khớp nguyên văn KB.
  2. structured  — (ingredient + strength + unit) khớp thành phần tên SCD (ăn điểm chính).
  3. ingredient  — khớp tên hoạt chất mức IN/PIN (cho gold cấp ingredient, vd nystatin 7597).
  4. fuzzy       — rapidfuzz, bắt viết tắt/sai chính tả (ngưỡng cấu hình).
  (embedding SapBERT: để dành, bật khi hit thấp — tránh tải model nặng lúc này.)
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from src.linking.drug_parser import DrugMention, parse
from src.linking.kb import KnowledgeBase, normalize

_TTY_SCORE = {"SCD": 1.0, "SBD": 0.95, "GPCK": 0.9, "BPCK": 0.9, "SCDC": 0.85,
              "SY": 0.8, "PSN": 0.8, "TMSY": 0.75, "IN": 0.5, "PIN": 0.5, "BN": 0.5}


@dataclass
class Candidate:
    code: str
    score: float
    method: str          # exact | structured | ingredient | fuzzy
    kb_name: str = "rxnorm"


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else f"{x:g}"


class DrugMatcher:
    def __init__(self, kb: KnowledgeBase, fuzzy_threshold: float = 88.0):
        self.kb = kb
        self.fuzzy_threshold = fuzzy_threshold
        df = kb.rxnorm
        self._rows = list(zip(df["rxcui"], df["tty"], df["str_norm"]))
        self._by_token: dict[str, list[int]] = {}
        for i, (_rxcui, _tty, norm) in enumerate(self._rows):
            for tok in set(norm.split()):
                self._by_token.setdefault(tok, []).append(i)

    # đơn vị THỂ TÍCH (không phải hàm lượng) -> bỏ qua structured, để về ingredient.
    _VOLUME_UNITS = {"ML", "CC"}

    # ── tầng 2: structured ───────────────────────────────────────────────────
    def _structured(self, men: DrugMention) -> list[Candidate]:
        toks = men.ingredient_tokens
        if not toks or men.strength is None or men.unit is None:
            return []
        if men.unit in self._VOLUME_UNITS:  # "5 ml" là thể tích, không phải potency
            return []
        unit_l = men.unit.lower()
        strengths = [men.strength] + ([men.strength_high] if men.strength_high else [])

        out: dict[str, Candidate] = {}
        # anchor trên token SỐ hàm lượng (robust khi tên là biến thể: senna⊂sennosides).
        for idx, s in enumerate(strengths):
            needle = f" {_fmt(s)} {unit_l}"
            for i in self._by_token.get(_fmt(s), []):
                rxcui, tty, norm = self._rows[i]
                if not all(t in norm for t in toks):
                    continue
                if needle not in (" " + norm):
                    continue
                # ưu tiên: SCD > ...; cận dưới range; mono-ingredient (không '/'); tên ngắn.
                sc = (
                    _TTY_SCORE.get(tty, 0.6)
                    - 0.01 * idx
                    - (0.2 if "/" in norm else 0.0)
                    - 1e-5 * len(norm)
                )
                if rxcui not in out or sc > out[rxcui].score:
                    out[rxcui] = Candidate(rxcui, sc, "structured")
        return list(out.values())

    # ── tầng 3: ingredient-level ─────────────────────────────────────────────
    def _ingredient(self, men: DrugMention) -> list[Candidate]:
        ing = normalize(men.ingredient)
        if not ing:
            return []
        out: dict[str, Candidate] = {}
        for i in self._by_token.get(men.ingredient_tokens[0], []):
            rxcui, tty, norm = self._rows[i]
            if norm == ing and tty in {"IN", "PIN", "MIN"}:
                out.setdefault(rxcui, Candidate(rxcui, 0.5, "ingredient"))
        return list(out.values())

    # ── tầng 4: fuzzy ────────────────────────────────────────────────────────
    def _fuzzy(self, raw: str) -> list[Candidate]:
        norm = normalize(raw)
        choices = self.kb._rx_index  # dict str_norm -> [rxcui]
        hit = process.extractOne(norm, choices.keys(), scorer=fuzz.token_sort_ratio,
                                 score_cutoff=self.fuzzy_threshold)
        if not hit:
            return []
        matched_norm, score, _ = hit
        return [Candidate(rx, score / 100.0, "fuzzy") for rx in choices[matched_norm]]

    def match(self, raw: str, top_k: int = 5) -> list[Candidate]:
        men = parse(raw)
        cands: dict[str, Candidate] = {}

        for rx in self.kb.lookup(raw, "rxnorm"):        # tầng 1 exact
            cands[rx] = Candidate(rx, 1.0, "exact")
        for c in self._structured(men):                  # tầng 2
            if c.code not in cands or c.score > cands[c.code].score:
                cands[c.code] = c
        for c in self._ingredient(men):                  # tầng 3
            cands.setdefault(c.code, c)
        if not cands:                                    # tầng 4 chỉ khi 1-3 miss
            for c in self._fuzzy(raw):
                cands.setdefault(c.code, c)

        ranked = sorted(cands.values(), key=lambda c: -c.score)
        return ranked[:top_k]
