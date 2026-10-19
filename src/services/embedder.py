import hashlib
import logging
import math
import re

logger = logging.getLogger(__name__)

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder:
    DIM = 256

    def __init__(self, backend: str) -> None:
        self._default = None
        self.backend = "hash"
        if backend == "default":
            try:
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

                fn = DefaultEmbeddingFunction()
                fn(["probe"])
                self._default = fn
                self.backend = "default"
            except Exception:
                logger.warning("default embedding model unavailable, falling back to hash embeddings", exc_info=True)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._default is not None:
            return [[float(x) for x in vec] for vec in self._default(texts)]
        return [self._hash(text) for text in texts]

    def _hash(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        tokens = TOKEN.findall(text.lower())
        for token in tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]:
            digest = hashlib.md5(token.encode()).digest()
            vec[int.from_bytes(digest[:4], "big") % self.DIM] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
