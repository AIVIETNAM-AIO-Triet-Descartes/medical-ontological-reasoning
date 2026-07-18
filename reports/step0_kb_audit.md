# Bước 0 — KB coverage audit (source=full)

## Check 1 — mã DeBai tồn tại trong KB?

**RxCUI: 12/13 tìm thấy.** Kết luận: ĐỦ (≥12/13)

Thiếu: 360047

| RxCUI | found | tty | str |
|---|:---:|---|---|
| 308135 | ✅ | PSN | amLODIPine besylate 10 MG Oral Tablet |
| 243670 | ✅ | PSN | aspirin 81 MG Oral Tablet |
| 866436 | ✅ | PSN | metoprolol succinate 50 MG 24HR Extended Release Oral Tablet |
| 392085 | ✅ | PSN | guaiFENesin 800 MG Oral Tablet |
| 7597 | ✅ | IN | nystatin |
| 313782 | ✅ | PSN | acetaminophen 325 MG Oral Tablet |
| 904475 | ✅ | PSN | pravastatin sodium 40 MG Oral Tablet |
| 1099279 | ✅ | PSN | docusate sodium 100 MG Oral Tablet |
| 312935 | ✅ | PSN | sennosides 8.6 MG Oral Tablet |
| 197527 | ✅ | PSN | clonazePAM 0.5 MG Oral Tablet |
| 197528 | ✅ | PSN | clonazePAM 1 MG Oral Tablet |
| 360047 | ❌ | — | *(vắng)* |
| 1660761 | ✅ | PSN | capsaicin 0.038 % / menthol 4 % / methyl salicylate 35 % Topical Cream |

| ICD | found | billable | desc |
|---|:---:|:---:|---|
| K21.0 | ✅ | False | Gastro-esophageal reflux disease with esophagitis |
| K21.9 | ✅ | True | Gastro-esophageal reflux disease without esophagitis |

## Check 3 — độ khó linking ICD (VN → EN)

- Cụm nghi chẩn đoán (lexicon, unique): **22**, tổng hit **150**.
- Trong đó dict VN→ICD phủ: **18/22** → phần còn lại CẦN cross-lingual retrieval.
- Top chẩn đoán: tăng huyết áp(28), đái tháo đường(14), rung nhĩ(12), viêm phổi(10), thiếu máu(9), bệnh tim mạch do xơ vữa động mạch(9), nhồi máu cơ tim(8), suy tim(8), tăng lipid máu(8), béo phì(7)

## Kết luận CHỐT

- RxNorm prescribe subset: 12/13. → đủ dùng.
- 3 mã concentration/obsolete vắng (`360047`) chỉ có ở bản Full.
- ICD-10-CM: build từ *order file* (giữ non-billable) → K21.0 có mặt. Output dùng `code_dotted`.
- Drug coverage trên 100 input: hit-rate 57.1% (20/35) — chi tiết ở step1_linker_eval.md.
  - Hit-rate thấp CHỦ YẾU do 2 nguyên nhân (soi miss), KHÔNG phải KB sai bản:
    1. **NER regex bắt nhầm** chữ VN có 'g/mg': `trong 24 g` (=giờ), `cao ... 500mg`, `total of 60 mg`, `reduced from 50mg` → false-positive bơm mẫu số. (backlog: siết `_DRUG_RE`.)
    2. **Brand name** chưa map→generic: `Tylenol`, `lasix/Laxis`, `coumadin`, `prograf`, `dilaudid` → cần brand→ingredient (RxNorm BN/SBD). (backlog Bước 1+.)
- Khi có Full: rerun `--source full`, yêu cầu **13/13** mới cho qua Bước 2.
