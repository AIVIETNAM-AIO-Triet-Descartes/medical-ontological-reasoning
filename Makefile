# Shortcut các bước pipeline. TODO: điền tham số thật khi code.
.PHONY: index infer eval package test

index:      ## Build KB lookup + embedding index từ data/kb
	python scripts/build_kb_index.py

infer:      ## input/*.txt -> output/*.json
	python scripts/run_inference.py

package:    ## output/ -> output.zip
	python scripts/package_output.py

eval:       ## Chấm điểm local (WER + Jaccard)
	python -m src.eval.harness

test:
	pytest -q
