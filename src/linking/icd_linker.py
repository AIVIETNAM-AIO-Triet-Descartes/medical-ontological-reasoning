"""Linker CHẨN_ĐOÁN -> ICD-10 bản Việt (VN↔VN).

Cascade: exact → fuzzy (siết ~92, chỉ chốt khi rất giống) → embedding (workhorse)
         → re-rank theo ĐỘ CỤ THỂ của ICD-10.

Embedding: bkai-foundation-models/vietnamese-bi-encoder (PhoBERT-base, 768d, Apache 2.0).
⚠️ PhoBERT là word-level → input PHẢI word-segment (pyvi) trước khi encode, cả KB lẫn query.
Vector KB cache ra data/kb/icd10_vn_emb.npy (encode 1 lần).

Độ cụ thể (docs bàn với user): KHÔNG ép xuống leaf mù quáng.
- câu CHUNG (không cue) → ưu tiên leaf ".9 / không xác định".
- câu có CUE cụ thể (típ N, độ N, cấp/mạn, bên trái/phải, biến chứng...) → cho phép leaf cụ thể.
- category 3-ký-tự CÓ mã con → hạ hạng (xuống leaf); category là mã CUỐI → giữ nguyên.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz, process

from src.linking.kb import KnowledgeBase

_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\([^)]*\)")
_LEAD_BENH = re.compile(r"^bệnh\s+")

_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
_EMB_CACHE = Path("data/kb/icd10_vn_emb.npy")
FUZZY_STRICT = 92.0          # ngưỡng fuzzy đủ tin để nạp candidate
_TOPK_EMB = 15               # số ứng viên embedding gom trước khi re-rank
_D = 0.06                    # biên độ nudge specificity (nhỏ, base score vẫn chính)

# tín hiệu độ cụ thể PHÂN BIỆT subtype (KHÔNG gồm 'cấp/mạn tính' — thường là phần
# tên bệnh cố hữu, vd COPD/MI, không phải cue phân biệt).
_CUE = re.compile(
    r"típ\s*\d|type\s*\d|độ\s*\d|giai đoạn\s*\d|bên trái|bên phải|hai bên|"
    r"biến chứng|nguyên phát|thứ phát|thùy", re.I,
)
_UNSPEC = re.compile(r"không xác định|không đặc hiệu|không rõ|không kèm|không phân loại", re.I)


def _norm_dx(s: str) -> str:
    s = s.lower().strip()
    s = _PAREN.sub(" ", s)
    s = _LEAD_BENH.sub("", s)
    return _WS.sub(" ", s).strip()


@dataclass
class Candidate:
    code: str
    score: float
    method: str          # exact | fuzzy | embed
    kb_name: str = "icd_vn"


class IcdLinker:
    def __init__(self, kb: KnowledgeBase, fuzzy_strict: float = FUZZY_STRICT):
        self.kb = kb
        self.fuzzy_strict = fuzzy_strict

    # ── exact / fuzzy indexes ────────────────────────────────────────────────
    @cached_property
    def _norm_to_codes(self) -> dict[str, list[str]]:
        idx: dict[str, list[str]] = {}
        for name, code in zip(self.kb.icd["ten_benh_vn"], self.kb.icd["code_dotted"]):
            key = _norm_dx(str(name))
            if key:
                idx.setdefault(key, []).append(str(code))
        return idx

    @cached_property
    def _keys(self) -> list[str]:
        return list(self._norm_to_codes.keys())

    # ── metadata theo hàng KB (song song với embedding) ──────────────────────
    @cached_property
    def _meta(self):
        codes = [str(c) for c in self.kb.icd["code_dotted"]]
        nodots = [str(c) for c in self.kb.icd["code_nodot"]]
        descs = [str(c) for c in self.kb.icd["desc_norm"]]
        # 3-ký-tự có mã con không
        prefixes = {n[:3] for n in nodots if len(n) > 3}
        has_children = [len(n) == 3 and n in prefixes for n in nodots]
        is_unspec = [bool(_UNSPEC.search(d)) or (len(n) >= 4 and n[-1] == "9")
                     for d, n in zip(descs, nodots)]
        return codes, nodots, descs, has_children, is_unspec

    # ── embedding ────────────────────────────────────────────────────────────
    @cached_property
    def _model(self):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(_MODEL_NAME)

    @staticmethod
    def _seg(s: str) -> str:
        from pyvi import ViTokenizer
        return ViTokenizer.tokenize(s.lower())

    @cached_property
    def _emb(self) -> np.ndarray:
        names = [str(x) for x in self.kb.icd["ten_benh_vn"]]
        if _EMB_CACHE.exists():
            arr = np.load(_EMB_CACHE)
            if arr.shape[0] == len(names):
                return arr
        segged = [self._seg(n) for n in names]
        arr = self._model.encode(segged, normalize_embeddings=True,
                                 batch_size=256, show_progress_bar=False).astype("float32")
        _EMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.save(_EMB_CACHE, arr)
        return arr

    def _embed_candidates(self, query: str, k: int) -> list[tuple[int, float]]:
        q = self._model.encode([self._seg(query)], normalize_embeddings=True)[0].astype("float32")
        sims = self._emb @ q
        idx = np.argpartition(-sims, min(k, len(sims) - 1))[:k]
        return sorted(((int(i), float(sims[i])) for i in idx), key=lambda x: -x[1])

    @cached_property
    def _leaf9(self) -> dict[str, str]:
        """prefix 3-ký-tự -> mã lá '.9' (không xác định) của họ đó, nếu có."""
        codes, nodots, *_ = self._meta
        m: dict[str, str] = {}
        for c, n in zip(codes, nodots):
            if len(n) == 4 and n[-1] == "9":
                m[n[:3]] = c
        return m

    @cached_property
    def _code_to_idx(self) -> dict[str, int]:
        codes = self._meta[0]
        d: dict[str, int] = {}
        for i, c in enumerate(codes):
            d.setdefault(c, i)
        return d

    # ── link ─────────────────────────────────────────────────────────────────
    def link(self, text: str, top_k: int = 5) -> list[Candidate]:
        q = _norm_dx(text)
        if not q:
            return []
        if q in self._norm_to_codes:                       # 1) exact
            return [Candidate(c, 1.0, "exact") for c in self._norm_to_codes[q]][:top_k]

        codes, nodots, descs, has_children, is_unspec = self._meta
        has_cue = bool(_CUE.search(text))
        qtok = set(q.split())

        pool: dict[int, str] = {}                          # row_idx -> method
        cosv: dict[int, float] = {}
        for i, cos in self._embed_candidates(q, _TOPK_EMB):  # 3) embedding (recall)
            pool[i] = "embed"; cosv[i] = cos
        for key, sc, _ in process.extract(q, self._keys, scorer=fuzz.token_sort_ratio,
                                          score_cutoff=self.fuzzy_strict, limit=5):  # 2) fuzzy siết
            for code in self._norm_to_codes[key]:
                i = self._code_to_idx.get(code)
                if i is not None:
                    pool.setdefault(i, "fuzzy")
                    cosv[i] = max(cosv.get(i, 0.0), 0.55)   # sàn cho fuzzy-only

        if not pool:
            return []
        # score = cos + token-overlap (chống drift ngữ nghĩa) + nudge độ cụ thể
        scored: list[tuple[int, float, str]] = []
        for i, method in pool.items():
            dtok = set(descs[i].split())
            overlap = len(qtok & dtok) / max(len(qtok), 1)
            s = cosv[i] + 0.4 * overlap
            if has_children[i]:
                s -= 0.12                                   # category còn con → xuống leaf
            if is_unspec[i] and not has_cue:
                s += 0.08                                   # câu chung → ưu tiên leaf .9
            scored.append((i, s, method))
        scored.sort(key=lambda x: -x[1])

        out: list[Candidate] = []
        seen: set[str] = set()
        for i, s, method in scored:
            c = codes[i]
            # snap category (3-ký-tự còn con) -> leaf '.9' (gold gần như luôn dùng 4-ký-tự)
            if len(nodots[i]) == 3 and has_children[i]:
                c = self._leaf9.get(nodots[i], c)
            if c in seen:
                continue
            seen.add(c)
            out.append(Candidate(c, round(float(s), 4), method))
            if len(out) >= top_k:
                break
        return out
