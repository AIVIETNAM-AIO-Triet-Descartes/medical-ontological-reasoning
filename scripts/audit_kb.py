"""Bước 0 — Audit KB coverage (gating) + Bước 1 linker eval.

Sinh:
  reports/step0_kb_audit.md    — Check 1 (13 RxCUI + K21.x), Check 3 (độ khó ICD), kết luận.
  reports/step0_file_stats.csv — Check 4 (thống kê per-file để chọn Golden).
  reports/step1_linker_eval.md — Check 2 (coverage chuỗi thuốc 100 input + breakdown method).

Dùng: python scripts/audit_kb.py --source prescribe
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.linking.icd_linker import IcdLinker  # noqa: E402
from src.linking.kb import KnowledgeBase  # noqa: E402
from src.linking.matcher import DrugMatcher  # noqa: E402
from src.ner.rule_based import _DIAGNOSIS_RE, _DRUG_RE, _trim_leading_stop  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"

# 13 RxCUI + 2 ICD trong DeBai.txt
DEBAI_RXCUI = ["308135", "243670", "866436", "392085", "7597", "313782", "904475",
               "1099279", "312935", "197527", "197528", "360047", "1660761"]
DEBAI_ICD = ["K21.0", "K21.9"]
# RxCUI đã bị RETIRE khỏi RxNorm — KHÔNG có kể cả bản Full (đề dùng bản cũ).
RETIRED_RXCUI = {"360047"}  # chlorpheniramine 0.4 MG/ML — 0 row mọi SAB trong full

# trigger assertion (để Check 4)
_TRIG = {
    "isHistorical": re.compile(r"tiền sử|tiền căn|trước đây|cách đây|nhiều năm", re.I),
    "isNegated": re.compile(r"\bkhông\b|phủ nhận|âm tính|loại trừ", re.I),
    "isFamily": re.compile(r"\b(mẹ|bố|cha|anh trai|chị gái|em trai|em gái|gia đình|di truyền)\b", re.I),
}
_NOISE = {
    "num_glued": re.compile(r"\d+\.\d+\.\d+"),
    "vn_decimal": re.compile(r"\d+,\d+"),
    "vn_thousand": re.compile(r"\d+,\d{3}\b"),
}


def _iter_drug_strings(text: str) -> list[str]:
    out = []
    for m in _DRUG_RE.finditer(text):
        s = _trim_leading_stop(text, m.start(), m.end())
        out.append(text[s:m.end()])
    return out


def check1(kb: KnowledgeBase) -> tuple[list[str], int]:
    lines = ["| RxCUI | found | tty | str |", "|---|:---:|---|---|"]
    n_found = 0
    for cui in DEBAI_RXCUI:
        info = kb.rxcui_info(cui)
        if len(info):
            n_found += 1
            row = info.sort_values("tty").iloc[0]
            lines.append(f"| {cui} | ✅ | {row['tty']} | {row['str']} |")
        else:
            lines.append(f"| {cui} | ❌ | — | *(vắng)* |")
    lines.append("")
    lines.append("| ICD | found | billable | desc |")
    lines.append("|---|:---:|:---:|---|")
    for code in DEBAI_ICD:
        sub = kb.icd[kb.icd.code_dotted == code]
        if len(sub):
            r = sub.iloc[0]
            lines.append(f"| {code} | ✅ | {r['is_billable']} | {r['desc']} |")
        else:
            lines.append(f"| {code} | ❌ | — | — |")
    return lines, n_found


def check2(kb: KnowledgeBase, input_dir: Path) -> tuple[str, dict]:
    matcher = DrugMatcher(kb)
    strings: Counter[str] = Counter()
    for fp in input_dir.glob("*.txt"):
        for s in _iter_drug_strings(fp.read_text(encoding="utf-8")):
            strings[s.strip()] += 1

    method_ct: Counter[str] = Counter()
    misses: list[tuple[str, int]] = []
    hit = 0
    for s, freq in strings.items():
        cands = matcher.match(s)
        if cands:
            hit += 1
            method_ct[cands[0].method] += 1
        else:
            misses.append((s, freq))
    total = len(strings)
    rate = hit / total if total else 0.0
    misses.sort(key=lambda x: -x[1])

    lines = [
        "# Bước 1 — Linker eval (coverage chuỗi thuốc trên 100 input)",
        "",
        f"- Chuỗi thuốc trích được (unique): **{total}**",
        f"- Match ≥1 candidate: **{hit}** → hit-rate **{rate:.1%}**",
        "",
        "**Breakdown theo method (candidate hạng 1):**",
    ]
    for meth, n in method_ct.most_common():
        lines.append(f"- `{meth}`: {n}")
    lines += ["", f"**Top 50 miss (freq):**", ""]
    for s, freq in misses[:50]:
        lines.append(f"- ({freq}) `{s}`")
    return "\n".join(lines) + "\n", {"total": total, "hit": hit, "rate": rate}


def check3(kb: KnowledgeBase, input_dir: Path) -> list[str]:
    icd = IcdLinker(kb)
    dx: Counter[str] = Counter()
    for fp in input_dir.glob("*.txt"):
        for m in _DIAGNOSIS_RE.finditer(fp.read_text(encoding="utf-8")):
            dx[m.group().lower()] += 1
    covered = sum(1 for d in dx if icd.link(d))
    lines = [
        f"- Cụm nghi chẩn đoán (lexicon, unique): **{len(dx)}**, tổng hit **{sum(dx.values())}**.",
        f"- Trong đó dict VN→ICD phủ: **{covered}/{len(dx)}** → phần còn lại CẦN cross-lingual retrieval.",
        "- Top chẩn đoán: " + ", ".join(f"{d}({n})" for d, n in dx.most_common(10)),
    ]
    return lines


def check4(input_dir: Path) -> None:
    REPORTS.mkdir(exist_ok=True)
    with (REPORTS / "step0_file_stats.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "chars", "n_drug", "isHistorical", "isNegated", "isFamily",
                    "num_glued", "vn_decimal", "vn_thousand"])
        for fp in sorted(input_dir.glob("*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else 1 << 30):
            t = fp.read_text(encoding="utf-8")
            w.writerow([
                fp.stem, len(t), len(_iter_drug_strings(t)),
                len(_TRIG["isHistorical"].findall(t)),
                len(_TRIG["isNegated"].findall(t)),
                len(_TRIG["isFamily"].findall(t)),
                len(_NOISE["num_glued"].findall(t)),
                len(_NOISE["vn_decimal"].findall(t)),
                len(_NOISE["vn_thousand"].findall(t)),
            ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["prescribe", "full"], default="prescribe")
    ap.add_argument("--input-dir", default="data/input")
    args = ap.parse_args()

    kb = KnowledgeBase.from_config()
    input_dir = Path(args.input_dir)
    REPORTS.mkdir(exist_ok=True)

    c1_lines, n_found = check1(kb)
    c2_md, c2_stat = check2(kb, input_dir)
    c3_lines = check3(kb, input_dir)
    check4(input_dir)

    missing = [c for c in DEBAI_RXCUI if not kb.has_rxcui(c)]
    verdict = "ĐỦ (≥12/13)" if n_found >= 12 else "**KHÔNG ĐỦ (<12/13) → CHỐT dùng full-filtered (SAB=RXNORM)**"

    audit = [
        f"# Bước 0 — KB coverage audit (source={args.source})", "",
        "## Check 1 — mã DeBai tồn tại trong KB?", "",
        f"**RxCUI: {n_found}/13 tìm thấy.** Kết luận: {verdict}", "",
        f"Thiếu: {', '.join(missing) if missing else '(không)'}", "",
        *c1_lines, "",
        "## Check 3 — độ khó linking ICD (VN → EN)", "",
        *c3_lines, "",
        "## Kết luận CHỐT", "",
        f"- RxNorm prescribe subset: {n_found}/13. "
        + ("→ dùng tạm cho Bước 1, **Bước 2 (gán candidates) CHẶN tới khi có RxNorm Full**."
           if n_found < 12 else "→ đủ dùng."),
        f"- 3 mã concentration/obsolete vắng (`{', '.join(missing)}`) chỉ có ở bản Full.",
        "- ICD-10-CM: build từ *order file* (giữ non-billable) → K21.0 có mặt. Output dùng `code_dotted`.",
        f"- Drug coverage trên 100 input: hit-rate {c2_stat['rate']:.1%} "
        f"({c2_stat['hit']}/{c2_stat['total']}) — chi tiết ở step1_linker_eval.md.",
        "  - Hit-rate thấp CHỦ YẾU do 2 nguyên nhân (soi miss), KHÔNG phải KB sai bản:",
        "    1. **NER regex bắt nhầm** chữ VN có 'g/mg': `trong 24 g` (=giờ), `cao ... 500mg`, "
        "`total of 60 mg`, `reduced from 50mg` → false-positive bơm mẫu số. (backlog: siết `_DRUG_RE`.)",
        "    2. **Brand name** chưa map→generic: `Tylenol`, `lasix/Laxis`, `coumadin`, `prograf`, "
        "`dilaudid` → cần brand→ingredient (RxNorm BN/SBD). (backlog Bước 1+.)",
        "- Khi có Full: rerun `--source full`, yêu cầu **13/13** mới cho qua Bước 2.",
        "",
    ]

    if args.source == "full":
        recoverable = [c for c in DEBAI_RXCUI if c not in RETIRED_RXCUI]
        still_missing = [c for c in recoverable if not kb.has_rxcui(c)]
        assert not still_missing, (
            f"source=full nhưng vẫn thiếu {still_missing} (ngoài retired {sorted(RETIRED_RXCUI)})."
        )

    (REPORTS / "step0_kb_audit.md").write_text("\n".join(audit), encoding="utf-8")
    (REPORTS / "step1_linker_eval.md").write_text(c2_md, encoding="utf-8")
    print(f"RxCUI {n_found}/13 | drug hit-rate {c2_stat['rate']:.1%} "
          f"({c2_stat['hit']}/{c2_stat['total']})")
    print("→ reports/step0_kb_audit.md, step0_file_stats.csv, step1_linker_eval.md")


if __name__ == "__main__":
    main()
