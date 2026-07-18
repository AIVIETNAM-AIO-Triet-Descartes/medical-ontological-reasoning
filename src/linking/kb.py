"""KnowledgeBase pluggable — load KB parquet, tra cứu exact/normalized.

Source (prescribe/full) chọn qua config/kb.yaml; đổi source KHÔNG phải sửa code
tra cứu. Matcher/linker chỉ phụ thuộc interface này.
"""

from __future__ import annotations

import re
from functools import cached_property
from pathlib import Path

import pandas as pd
import yaml

_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    return _WS.sub(" ", s.strip().lower())


class KnowledgeBase:
    def __init__(self, rxnorm_path: str | Path, icd_path: str | Path):
        self.rxnorm_path = Path(rxnorm_path)
        self.icd_path = Path(icd_path)

    @classmethod
    def from_config(cls, config_path: str | Path = "config/kb.yaml") -> "KnowledgeBase":
        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        # ICD primary = bản Việt (linking VN↔VN). icd10cm giữ làm fallback riêng nếu cần.
        icd = cfg["out"].get("icd10_vn", cfg["out"]["icd10cm"])
        return cls(cfg["out"]["rxnorm"], icd)

    # ── dataframes (lazy) ────────────────────────────────────────────────────
    @cached_property
    def rxnorm(self) -> pd.DataFrame:
        if not self.rxnorm_path.exists():
            raise FileNotFoundError(f"Chưa build KB: {self.rxnorm_path} (chạy build_kb.py)")
        return pd.read_parquet(self.rxnorm_path)

    @cached_property
    def icd(self) -> pd.DataFrame:
        if not self.icd_path.exists():
            raise FileNotFoundError(f"Chưa build KB: {self.icd_path} (chạy build_kb.py)")
        return pd.read_parquet(self.icd_path)

    # ── index exact theo chuỗi chuẩn hoá ─────────────────────────────────────
    @cached_property
    def _rx_index(self) -> dict[str, list[str]]:
        idx: dict[str, list[str]] = {}
        for norm, rxcui in zip(self.rxnorm["str_norm"], self.rxnorm["rxcui"]):
            idx.setdefault(norm, []).append(rxcui)
        return idx

    @cached_property
    def _icd_index(self) -> dict[str, list[str]]:
        idx: dict[str, list[str]] = {}
        for norm, code in zip(self.icd["desc_norm"], self.icd["code_dotted"]):
            idx.setdefault(norm, []).append(code)
        return idx

    # ── lookup ───────────────────────────────────────────────────────────────
    def lookup(self, text: str, kb: str) -> list[str]:
        """Exact-normalized lookup. kb='rxnorm' -> list RxCUI; kb='icd' -> list code_dotted.

        Dedupe giữ thứ tự. Trả [] nếu không khớp.
        """
        norm = normalize(text)
        src = self._rx_index if kb == "rxnorm" else self._icd_index
        seen: dict[str, None] = {}
        for code in src.get(norm, []):
            seen.setdefault(code, None)
        return list(seen)

    def rxcui_info(self, rxcui: str) -> pd.DataFrame:
        return self.rxnorm[self.rxnorm["rxcui"] == str(rxcui)]

    def has_rxcui(self, rxcui: str) -> bool:
        return bool((self.rxnorm["rxcui"] == str(rxcui)).any())

    def has_icd(self, code_dotted: str) -> bool:
        return bool((self.icd["code_dotted"] == code_dotted).any())
