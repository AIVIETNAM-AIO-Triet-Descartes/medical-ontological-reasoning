"""Embedding index (SapBERT biomedical + model đa ngữ cho chẩn đoán VN). Backend FAISS."""

# TODO: build index từ KB; query top-k.


class EmbeddingIndex:
    def build(self, texts: list[str]):
        raise NotImplementedError

    def search(self, query: str, k: int = 5):
        raise NotImplementedError
