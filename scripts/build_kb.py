"""Parse KB thô (RxNorm RRF + ICD-10-CM order file) -> parquet chuẩn hoá.

Idempotent, chạy lại được. Nguồn cấu hình trong config/kb.yaml.

    python scripts/build_kb.py --source prescribe
    python scripts/build_kb.py --source full       # cần đã tải RxNorm Full

RxNorm: chỉ giữ SAB=='RXNORM' (license — lớp public domain, nộp được BTC),
LAT=='ENG', SUPPRESS!='Y'. Giữ MỌI TTY (gold đề bài dùng IN/SY/SCD lẫn lộn).

ICD-10-CM: parse từ ORDER file (fixed-width) để giữ CẢ mã non-billable
(vd K21.0 đã split thành K21.00/K21.01 nhưng vẫn tồn tại ở order file).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.strip().lower())


def _dot_icd(code_nodot: str) -> str:
    """CMS lưu không dấu chấm (K210); đề bài dùng có chấm (K21.0)."""
    return code_nodot if len(code_nodot) <= 3 else f"{code_nodot[:3]}.{code_nodot[3:]}"


# ── RxNorm ────────────────────────────────────────────────────────────────────
# RXNCONSO.RRF pipe-delim: RXCUI(0) LAT(1) ... SAB(11) TTY(12) CODE(13) STR(14) ... SUPPRESS(16)
def build_rxnorm(rrf_path: Path, keep_sab: str, out_path: Path) -> int:
    rows: list[tuple[str, str, str, str, str]] = []
    with rrf_path.open(encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 17:
                continue
            # KHÔNG lọc theo SUPPRESS: bản full cần giữ mã obsolete/suppressed (đề dùng
            # RxNorm bản cũ). Giữ cột `suppress` để linker HẠ THỨ HẠNG (không loại bỏ) —
            # docs/problem-and-findings.md §6.1. Đọc RRF bằng split thủ công -> không dính
            # vấn đề quoting của csv (RRF không quote; 2 dòng STR chứa dấu " vẫn nguyên).
            if p[1] != "ENG" or p[11] != keep_sab:
                continue
            rxcui, tty, s, suppress = p[0], p[12], p[14], p[16]
            rows.append((rxcui, tty, s, _norm(s), suppress))
    df = pd.DataFrame(rows, columns=["rxcui", "tty", "str", "str_norm", "suppress"])
    df = df.drop_duplicates()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(df)


# ── ICD-10 bản Việt (xlsx Thông tư BYT) ───────────────────────────────────────
# Cột (0-idx): [1]STT CHƯƠNG [4]TÊN CHƯƠNG [16]TÊN NHÓM 3 KÝ TỰ [17]MÃ BỆNH(dotted)
#              [18]MÃ KHÔNG DẤU [19]DISEASE NAME EN [21]TÊN BỆNH(VN)
# Header ở dòng xlsx thứ 3; data từ dòng 5. Mọi dòng data đều có MÃ BỆNH.
def build_icd10_vn(xlsx_path: Path, sheet: str, out_path: Path) -> int:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows: list[tuple] = []
    for r in ws.iter_rows(min_row=5, values_only=True):
        if len(r) < 22:
            continue
        code_dotted = (r[17] or "").strip() if isinstance(r[17], str) else (str(r[17]).strip() if r[17] is not None else "")
        if not code_dotted:
            continue
        code_nodot = (str(r[18]).strip() if r[18] is not None else code_dotted.replace(".", ""))
        ten_vn = (str(r[21]).strip() if r[21] is not None else "")
        desc_en = (str(r[19]).strip() if r[19] is not None else "")
        ten_nhom3 = (str(r[16]).strip() if r[16] is not None else "")
        chuong = (str(r[1]).strip() if r[1] is not None else "")
        ten_chuong = (str(r[4]).strip() if r[4] is not None else "")
        rows.append((code_nodot, code_dotted, ten_vn, _norm(ten_vn),
                     desc_en, ten_nhom3, chuong, ten_chuong))
    wb.close()
    df = pd.DataFrame(rows, columns=[
        "code_nodot", "code_dotted", "ten_benh_vn", "desc_norm",
        "desc_en", "ten_nhom3", "chuong", "ten_chuong",
    ])
    df = df.drop_duplicates(subset=["code_dotted"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(df)


# ── ICD-10-CM (order file, fixed-width) ───────────────────────────────────────
# cols (0-idx): order[0:5] code[6:13] billable[14] short[16:76] long[77:]
def build_icd10(order_path: Path, out_path: Path) -> int:
    rows: list[tuple[str, str, str, str, bool]] = []
    with order_path.open(encoding="utf-8") as f:
        for line in f:
            if len(line) < 16:
                continue
            code_nodot = line[6:13].strip()
            if not code_nodot:
                continue
            billable = line[14] == "1"
            long_desc = line[77:].rstrip("\n").strip() if len(line) > 77 else line[16:76].strip()
            rows.append(
                (code_nodot, _dot_icd(code_nodot), long_desc, _norm(long_desc), billable)
            )
    df = pd.DataFrame(
        rows, columns=["code_nodot", "code_dotted", "desc", "desc_norm", "is_billable"]
    )
    df = df.drop_duplicates(subset=["code_nodot"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(df)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build KB parquet từ RRF + ICD (VN xlsx / CMS).")
    ap.add_argument("--source", choices=["prescribe", "full"], default="full",
                    help="Nguồn RxNorm (mặc định full = release mới nhất).")
    ap.add_argument("--config", default="config/kb.yaml")
    ap.add_argument("--skip-cms", action="store_true",
                    help="Bỏ build ICD-10-CM (EN fallback), chỉ build ICD VN.")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    keep_sab = cfg.get("rxnorm_keep_sab", "RXNORM")

    # 1) RxNorm
    rrf = Path(cfg["sources"][args.source]["rxnorm_rrf"])
    if not rrf.exists():
        raise SystemExit(f"Không thấy RxNorm RRF cho source='{args.source}': {rrf}")
    n_rx = build_rxnorm(rrf, keep_sab, Path(cfg["out"]["rxnorm"]))
    print(f"[rxnorm:{args.source}] SAB={keep_sab} -> {cfg['out']['rxnorm']}  rows={n_rx}")

    # 2) ICD-10 bản Việt (PRIMARY)
    xlsx = Path(cfg["icd10_vn_xlsx"])
    if not xlsx.exists():
        raise SystemExit(f"Không thấy ICD-10 VN xlsx: {xlsx}")
    n_vn = build_icd10_vn(xlsx, cfg["icd10_vn_sheet"], Path(cfg["out"]["icd10_vn"]))
    print(f"[icd10_vn] xlsx -> {cfg['out']['icd10_vn']}  rows={n_vn}")

    # 3) ICD-10-CM EN (fallback, tuỳ chọn)
    if not args.skip_cms:
        order = Path(cfg["icd10_order"])
        if order.exists():
            n_icd = build_icd10(order, Path(cfg["out"]["icd10cm"]))
            print(f"[icd10cm:fallback] order file -> {cfg['out']['icd10cm']}  rows={n_icd}")


if __name__ == "__main__":
    main()
