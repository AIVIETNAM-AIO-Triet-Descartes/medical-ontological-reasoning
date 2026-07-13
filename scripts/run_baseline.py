"""Chạy rule-based NER baseline trên toàn bộ input -> ghi output/first_layer/baseline/*.json.

Dùng: python scripts/run_baseline.py [--input-dir data/input] [--out-dir output/first_layer/baseline]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# cho phép chạy trực tiếp: thêm repo root vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ner.rule_based import extract          # noqa: E402
from src.utils.io import read_document, write_concepts_file  # noqa: E402


def _sample_key(p: Path) -> tuple[int, str]:
    # '1'..'100' sắp theo số; fallback theo tên nếu không phải số.
    return (int(p.stem), "") if p.stem.isdigit() else (1 << 30, p.stem)


def main() -> None:
    ap = argparse.ArgumentParser(description="Rule-based NER baseline runner.")
    ap.add_argument("--input-dir", default="data/input")
    ap.add_argument("--out-dir", default="output/first_layer/baseline")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.txt"), key=_sample_key)
    if not files:
        raise SystemExit(f"Không tìm thấy *.txt trong {input_dir}")

    per_type: dict[str, int] = {}
    total = 0
    for fp in files:
        text = read_document(fp)
        concepts = extract(text)

        # kiểm bất biến offset: input[start:end] == text
        for c in concepts:
            s, e = c.position
            assert text[s:e] == c.text, f"offset lệch ở {fp.name}: {c.text!r}"
            per_type[c.type.value] = per_type.get(c.type.value, 0) + 1
        total += len(concepts)

        write_concepts_file(concepts, out_dir / f"{fp.stem}.json")

    print(f"Đã xử lý {len(files)} file -> {out_dir}")
    print(f"Tổng concept: {total}")
    for t, n in sorted(per_type.items(), key=lambda kv: -kv[1]):
        print(f"  {t:22s} {n}")


if __name__ == "__main__":
    main()
