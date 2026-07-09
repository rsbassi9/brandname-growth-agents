"""Brand Brain embedding and search service."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select

from ..db import session_scope
from ..models import BrainDocument, BrainEmbedding
from ..settings import get_settings
from .openai_client import get_openai_client

LOCAL_EMBED_MODEL = "local-hash-256"
LOCAL_EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class BrainSearchResult:
    document: BrainDocument
    score: float


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Embed texts. Local-only mode is deterministic and makes zero network calls."""
    settings = get_settings()
    if settings.local_only_agent_runs:
        return [_hash_vector(text) for text in texts]

    client = get_openai_client()
    response = client.embeddings.create(model=settings.embed_model, input=texts)
    vectors: list[np.ndarray] = []
    for item in response.data:
        vector = np.array(item.embedding, dtype="<f4")
        vectors.append(_normalize(vector))
    return vectors


def embedding_model_label() -> str:
    settings = get_settings()
    return LOCAL_EMBED_MODEL if settings.local_only_agent_runs else settings.embed_model


def vector_to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype="<f4").tobytes()


def blob_to_vector(blob: bytes, dim: int) -> np.ndarray:
    vector = np.frombuffer(blob, dtype="<f4")
    if vector.size != dim:
        raise ValueError(f"Embedding dimension mismatch: expected {dim}, got {vector.size}")
    return vector


def search(query: str, k: int = 5, kinds: list[str] | None = None) -> list[BrainSearchResult]:
    query_vector = embed_texts([query])[0]
    with session_scope() as session:
        statement = select(BrainDocument, BrainEmbedding).join(BrainEmbedding)
        if kinds:
            statement = statement.where(BrainDocument.kind.in_(kinds))
        rows = session.execute(statement).all()
        scored = [
            BrainSearchResult(document=document, score=_cosine(query_vector, blob_to_vector(embedding.vector, embedding.dim)))
            for document, embedding in rows
        ]
        scored.sort(key=lambda item: (-item.score, item.document.id))
        for item in scored[:k]:
            session.expunge(item.document)
        return scored[:k]


def _hash_vector(text: str) -> np.ndarray:
    vector = np.zeros(LOCAL_EMBED_DIM, dtype="<f4")
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % LOCAL_EMBED_DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    return _normalize(vector)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return vector.astype("<f4", copy=False)
    return (vector / norm).astype("<f4", copy=False)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    if left.size != right.size:
        return 0.0
    return float(np.dot(_normalize(left), _normalize(right)))
