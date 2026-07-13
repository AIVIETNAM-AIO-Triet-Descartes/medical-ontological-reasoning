"""IO: đọc input/*.txt, đọc/ghi output/*.json, load thành Concept, đóng gói output.zip."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from src.schema import Concept


def read_document(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_concepts_file(path: str | Path) -> list[Concept]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Concept.from_dict(d) for d in data]


def load_concept_dir(dir_path: str | Path) -> dict[str, list[Concept]]:
    """Đọc mọi *.json trong thư mục -> {stem -> list[Concept]}. stem = '1','2',...'100'."""
    out: dict[str, list[Concept]] = {}
    for p in Path(dir_path).glob("*.json"):
        out[p.stem] = load_concepts_file(p)
    return out


def write_concepts_file(concepts: list[Concept], path: str | Path) -> None:
    data = [c.to_dict() for c in concepts]
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def zip_output(output_dir: str | Path, zip_path: str | Path = "output.zip") -> Path:
    """output/1.json..100.json -> output.zip (giữ cấu trúc thư mục output/ như BTC yêu cầu)."""
    output_dir = Path(output_dir)
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(output_dir.glob("*.json")):
            zf.write(p, arcname=f"output/{p.name}")
    return zip_path
