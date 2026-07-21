"""Baseline v2 — GLiNER (NER) + ConText (assertion) + cascade (linking) → output JSON.

1 file text -> list[Concept]. Ghép 3 module, cắt candidates đúng số nộp
(THUỐC=1, CHẨN_ĐOÁN=2 — xem docs/problem-and-findings.md §5).

Chạy: python -m src.pipeline.baseline_v2 --input data/input --out runs/baseline_v2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.assertion.context_rules import detect as detect_assertions
from src.linking import link
from src.ner.gliner_extractor import extract as ner_extract
from src.schema import (
    TYPES_WITH_ASSERTIONS,
    TYPES_WITH_CANDIDATES,
    Concept,
    ConceptType,
)
from src.utils.io import read_document, write_concepts_file

_CAND_K = {ConceptType.THUOC: 1, ConceptType.CHAN_DOAN: 2}


def process_document(text: str, ner_threshold: float = 0.2) -> list[Concept]:
    concepts = ner_extract(text, threshold=ner_threshold)
    for c in concepts:
        if c.type in TYPES_WITH_ASSERTIONS:
            c.assertions = detect_assertions(text, c.position[0], c.position[1])
        if c.type in TYPES_WITH_CANDIDATES:
            k = _CAND_K.get(c.type, 1)
            cands = link(c.text, c.type.value, top_k=max(k, 5))
            c.candidates = [x.code for x in cands[:k]]
    return concepts


def _sample_key(p: Path):
    return (int(p.stem), "") if p.stem.isdigit() else (1 << 30, p.stem)


def main() -> None:
    # Fix Windows console encoding (cp1252 không hỗ trợ tiếng Việt)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description="Baseline v2 pipeline runner.")
    ap.add_argument("--input", default="data/input")
    ap.add_argument("--out", default="runs/baseline_v2")
    ap.add_argument("--threshold", type=float, default=0.2)
    ap.add_argument("--limit", type=int, default=0, help="Chỉ chạy N file đầu (0 = tất cả).")
    args = ap.parse_args()

    out_dir = Path(args.out) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(args.input).glob("*.txt"), key=_sample_key)
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"Không thấy *.txt trong {args.input}")

    per_type: dict[str, int] = {}
    total = 0
    for i, fp in enumerate(files, 1):
        text = read_document(fp)
        concepts = process_document(text, ner_threshold=args.threshold)
        for c in concepts:  # kiểm bất biến offset
            s, e = c.position
            assert text[s:e] == c.text, f"offset lệch {fp.name}: {c.text!r}"
            per_type[c.type.value] = per_type.get(c.type.value, 0) + 1
        total += len(concepts)
        write_concepts_file(concepts, out_dir / f"{fp.stem}.json")
        if i % 10 == 0 or i == len(files):
            print(f"  {i}/{len(files)} files...")

    print(f"\nĐã ghi {len(files)} file -> {out_dir}")
    print(f"Tổng concept: {total}")
    for t, n in sorted(per_type.items(), key=lambda kv: -kv[1]):
        print(f"  {t:22s} {n}")


if __name__ == "__main__":
    main()
