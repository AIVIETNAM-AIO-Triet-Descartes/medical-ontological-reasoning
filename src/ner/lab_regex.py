"""NER rule-based cho TÊN_XÉT_NGHIỆM + KẾT_QUẢ_XÉT_NGHIỆM.

GLiNER không tag được số trần (KẾT_QUẢ) và viết tắt ngắn (TÊN_XÉT_NGHIỆM) — xem
docs. Regex bù đúng 2 loại này. Offset lấy từ finditer trên text gốc -> input[s:e]==text.

Gold dev cho thấy:
  TÊN_XÉT_NGHIỆM: 'WBC','HGB','PLT','Glucose','Creatinin','Kali','ECG','Điện tâm đồ',
                  'HbA1c','NEUT% (Tỷ lệ % bạch cầu trung tính)','Chụp X-quang ngực','Siêu âm bụng'
  KẾT_QUẢ:        '14,43','76,4','410','0.01','8,9 mmol/L','118 umol/L','8,7%'
"""

from __future__ import annotations

import re

from src.schema import Concept, ConceptType

# ── TÊN_XÉT_NGHIỆM ────────────────────────────────────────────────────────────
# viết tắt + tên xét nghiệm chuẩn (≥2 ký tự để tránh nhiễu 1 chữ như K/Na).
_LAB_TERMS = [
    # huyết học
    "wbc", "rbc", "hgb", "hct", "plt", "neut", "lymph", "lym", "lyph", "mono", "eos",
    "baso", "mcv", "mch", "mchc", "rdw", "twbc", "hb",
    # sinh hoá
    "glucose đói", "glucose", "creatinin", "creatinine", "ure", "bun", "ast", "alt",
    "alp", "ggt", "albumin", "bilirubin toàn phần", "bilirubin", "tbili", "kali",
    "natri", "clo", "canxi", "hba1c", "troponin", "bnp", "crp", "esr", "inr", "aptt",
    "ldl", "hdl", "triglycerid", "cholesterol", "egfr", "ck", "ckmb", "ldh", "ferritin",
    "amylase", "lipase", "procalcitonin", "lactate", "tsh", "ft4", "ft3", "d-dimer",
    # thăm dò / hình ảnh
    "ecg", "điện tâm đồ", "điện tim",
]
_LAB_TERMS.sort(key=len, reverse=True)
_LAB_ALT = "|".join(re.escape(t) for t in _LAB_TERMS)
# viết tắt/tên + optional '%' + optional cụm '(gloss)'  (vd 'NEUT% (Tỷ lệ ...)')
_LAB_NAME_RE = re.compile(rf"\b(?:{_LAB_ALT})\b\s*%?(?:\s*\([^)]*\))?", re.I)

# hình ảnh/thủ thuật: từ khoá + tối đa 3 từ cơ quan theo sau
_IMAGING_RE = re.compile(
    r"\b(?:chụp\s+x-?quang|siêu\s+âm|chụp\s+cắt\s+lớp(?:\s+vi\s+tính)?|chụp\s+ct|"
    r"chụp\s+mri|chụp\s+cộng\s+hưởng\s+từ|nội\s+soi|x-?quang)"
    r"(?:\s+[A-Za-zÀ-ỹ]+){0,3}",
    re.I,
)

# ── KẾT_QUẢ_XÉT_NGHIỆM ────────────────────────────────────────────────────────
_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = (r"mmol/l|umol/l|µmol/l|nmol/l|mg/dl|mcg/dl|g/l|g/dl|mg/l|meq/l|ng/ml|ng/l|"
         r"pg/ml|u/l|iu/l|mu/l|mmhg|%|tb/l|x?10\^?\d+/l|/µl|/ul")
_RESULT_UNIT_RE = re.compile(rf"\b{_NUM}\s*(?:{_UNIT})", re.I)
# số ngay sau tên xét nghiệm ('WBC: 14,43', 'PLT 410')
_NUM_AFTER_RE = re.compile(rf"[:\s]+({_NUM})\s*%?")


def _add(spans, s, e, ctype):
    if e - s >= 1:
        spans.append((s, e, ctype))


def extract(text: str) -> list[Concept]:
    spans: list[tuple[int, int, ConceptType]] = []
    name_spans: list[tuple[int, int]] = []

    for m in _LAB_NAME_RE.finditer(text):
        s, e = m.start(), m.end()
        _add(spans, s, e, ConceptType.TEN_XET_NGHIEM)
        name_spans.append((s, e))
    for m in _IMAGING_RE.finditer(text):
        _add(spans, m.start(), m.end(), ConceptType.TEN_XET_NGHIEM)

    # KẾT_QUẢ: số + đơn vị (span gồm cả đơn vị, đúng gold '8,9 mmol/L')
    for m in _RESULT_UNIT_RE.finditer(text):
        _add(spans, m.start(), m.end(), ConceptType.KET_QUA_XET_NGHIEM)
    # KẾT_QUẢ: số trần ngay sau tên xét nghiệm ('WBC: 14,43')
    for _ns, ne in name_spans:
        m = _NUM_AFTER_RE.match(text, ne)
        if m:
            _add(spans, m.start(1), m.end(1), ConceptType.KET_QUA_XET_NGHIEM)

    return _resolve(text, spans)


def _resolve(text: str, spans: list[tuple[int, int, ConceptType]]) -> list[Concept]:
    # giữ span dài hơn khi chồng lấn; TÊN trước KẾT_QUẢ khi cùng độ dài.
    prio = {ConceptType.TEN_XET_NGHIEM: 1, ConceptType.KET_QUA_XET_NGHIEM: 0}
    spans = sorted(set(spans), key=lambda s: (-(s[1] - s[0]), -prio[s[2]], s[0]))
    kept: list[tuple[int, int, ConceptType]] = []
    for s in spans:
        if any(s[0] < k[1] and k[0] < s[1] for k in kept):
            continue
        kept.append(s)
    kept.sort(key=lambda s: (s[0], s[1]))
    return [Concept(text=text[s:e], type=t, position=(s, e)) for s, e, t in kept]
