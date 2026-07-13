"""Cascade match chung: exact string -> fuzzy -> embedding retrieval. Trả top-k candidate."""

# TODO: interface Linker(query) -> list[str] mã; cấu hình ngưỡng từ config.


def link(query: str) -> list[str]:
    raise NotImplementedError
