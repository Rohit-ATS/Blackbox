"""Embeddings.

Default is a deterministic local hashed-lexical embedder: 384 dims, L2
normalized, zero dependencies, zero network calls. It is reproducible across
machines, which matters more for a live demo than semantic nuance -- the
symptom strings we match on ("connection pool exhausted", "p99 latency")
are short and lexically overlapping, which is exactly where this works.

If `sentence-transformers` is installed, BLACKBOX_EMBEDDER=minilm switches to
all-MiniLM-L6-v2 (also 384 dims, so the vector indexes do not change).
"""
from __future__ import annotations

import hashlib
import math
import os
import re

from .config import EMBED_DIM

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "is", "was", "and", "for", "at", "it", "we"}

_model = None


def _tokens(text: str) -> list[str]:
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
    grams = list(words)
    grams += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    for w in words:
        if len(w) > 4:
            grams += [w[i:i + 4] for i in range(len(w) - 3)]
    return grams


def _bucket(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big") % EMBED_DIM


def _lexical(text: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    for tok in _tokens(text):
        vec[_bucket(tok)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


def _minilm(text: str) -> list[float]:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model.encode(text, normalize_embeddings=True).tolist()


def embed(text: str) -> list[float]:
    if os.getenv("BLACKBOX_EMBEDDER", "lexical") == "minilm":
        try:
            return _minilm(text)
        except Exception:
            pass
    return _lexical(text or "")


def backend_name() -> str:
    return "all-MiniLM-L6-v2" if os.getenv("BLACKBOX_EMBEDDER") == "minilm" else "hashed-lexical-384"
