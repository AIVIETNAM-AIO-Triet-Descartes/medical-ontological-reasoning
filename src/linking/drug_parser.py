"""Parse chuỗi thuốc -> thành phần cấu trúc (DrugMention).

Hàm lượng + đơn vị quyết định RxCUI:
  clonazepam 0.5 mg -> 197527 ; clonazepam 1 mg -> 197528
  Chlorpheniramine 0.4 MG/ML -> 360047 (nồng độ, KHÁC mg khối lượng)
  acetaminophen 325-650 mg -> gold 313782 = bản 325 mg (range: lấy cận dưới)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# đơn vị: MG/ML (nồng độ) phải đứng TRƯỚC MG để regex ăn trọn.
_UNIT_ALT = r"mg/ml|mcg/ml|meq/ml|unit/ml|mg|mcg|meq|units?|iu|ml|gram|g|%|cc"
_STRENGTH_UNIT_RE = re.compile(
    r"(?P<low>\d+(?:[.,]\d+)?)(?:\s*-\s*(?P<high>\d+(?:[.,]\d+)?))?"
    r"\s*(?P<unit>" + _UNIT_ALT + r")\b",
    re.IGNORECASE,
)

# token KHÔNG phải tên hoạt chất (từ nối VN lọt vào, hoặc dạng bào chế).
_STOP_LEAD = {"cho", "do", "khi", "va", "la", "cac", "vao", "duoc", "dung", "nhan", "them"}
_DOSE_FORM = {
    "xl", "er", "sr", "cr", "dr", "ec", "la", "xr", "oral", "suspension", "susp",
    "tablet", "tab", "capsule", "cap", "solution", "soln", "cream", "ointment",
    "nebulizer", "inhaler", "patch", "syrup", "drops", "extended", "release",
}
_ROUTE = {"po", "iv", "im", "sc", "sq", "sl", "pr", "top", "topical", "inhaled", "gtt", "nebs", "neb"}
_FREQ_RE = re.compile(r"^(?:daily|bid|tid|qid|qhs|qam|qpm|qd|qod|q\d+h|q\d+hr|prn|once|weekly|nightly)(?::\w+)?$", re.IGNORECASE)


@dataclass
class DrugMention:
    raw: str
    ingredient: str
    strength: float | None
    strength_high: float | None
    unit: str | None            # chuẩn hoá: "MG" | "MG/ML" | "MEQ" | "%" ...
    dose_form: str | None
    route: str | None
    frequency: str | None

    @property
    def ingredient_tokens(self) -> list[str]:
        return [t for t in re.split(r"[\s\-]+", self.ingredient.lower()) if t]


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    return float(s.replace(",", "."))


def parse(raw: str) -> DrugMention:
    m = _STRENGTH_UNIT_RE.search(raw)
    if not m:
        # không có hàm lượng -> coi cả chuỗi là ingredient (bare drug name)
        ing = _clean_ingredient(raw)
        return DrugMention(raw, ing, None, None, None, None, None, None)

    ingredient = _clean_ingredient(raw[: m.start()])
    unit = m.group("unit").upper()
    tail = raw[m.end():].strip()

    dose_form = route = freq = None
    df_tokens: list[str] = []
    for tok in tail.split():
        low = tok.lower()
        if low in _ROUTE and route is None:
            route = low
        elif _FREQ_RE.match(low) and freq is None:
            freq = low
        elif low in _DOSE_FORM:
            df_tokens.append(low)
    if df_tokens:
        dose_form = " ".join(df_tokens)

    return DrugMention(
        raw=raw.strip(),
        ingredient=ingredient,
        strength=_to_float(m.group("low")),
        strength_high=_to_float(m.group("high")),
        unit=unit,
        dose_form=dose_form,
        route=route,
        frequency=freq,
    )


def _clean_ingredient(s: str) -> str:
    toks = re.split(r"\s+", s.strip())
    # bỏ token nối VN mở đầu
    while toks and toks[0].lower() in _STOP_LEAD:
        toks = toks[1:]
    # bỏ token dạng bào chế lẫn ở cuối (xl, er...) khỏi tên hoạt chất
    while toks and toks[-1].lower() in _DOSE_FORM:
        toks = toks[:-1]
    return " ".join(toks).strip()
