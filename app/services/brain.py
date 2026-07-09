"""Brand Brain embedding and search service."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select

from ..db import init_db, session_scope
from ..models import Asset, AssetVersion, BrainDocument, BrainEmbedding, BrandProfileVersion, FeedbackEvent
from ..paths import brand_context_dir
from ..settings import get_settings
from .openai_client import get_openai_client

LOCAL_EMBED_MODEL = "local-hash-256"
LOCAL_EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class BrainSearchResult:
    document: BrainDocument
    score: float


@dataclass(frozen=True)
class MemoryContext:
    block: str
    document_ids: list[int]
    profile_version_no: int | None


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


def build_memory_context(query: str, k: int = 5) -> MemoryContext:
    """Build the auditable BRAND MEMORY prompt block for generation."""
    with session_scope() as session:
        profile = session.execute(
            select(BrandProfileVersion).order_by(BrandProfileVersion.version_no.desc())
        ).scalars().first()
        profile_text = profile.profile_md if profile else ""
        profile_version_no = profile.version_no if profile else None

    results = search(query, k=max(k * 3, k)) if query.strip() else []
    ranked = sorted(results, key=lambda item: (-_memory_rank_score(item), item.document.id))[:k]
    if not profile_text and not ranked:
        return MemoryContext(block="", document_ids=[], profile_version_no=None)

    lines = ["BRAND MEMORY"]
    if profile_text and profile_version_no is not None:
        lines.extend([f"Current brand profile v{profile_version_no}:", profile_text.strip()])
    if ranked:
        lines.append("Similar evidence:")
        for item in ranked:
            meta = _read_meta(item.document)
            lines.append(
                "- "
                + f"doc#{item.document.id} kind={item.document.kind}"
                + (f" ref={item.document.ref_id}" if item.document.ref_id else "")
                + f" score={item.score:.3f}"
                + _winner_label(meta)
                + f": {_snippet(item.document.text)}"
            )
    return MemoryContext(
        block="\n".join(lines).strip(),
        document_ids=[item.document.id for item in ranked],
        profile_version_no=profile_version_no,
    )


def index_asset_version(asset_version_id: int) -> dict[str, int]:
    with session_scope() as session:
        version = session.get(AssetVersion, asset_version_id)
        if version is None:
            return {"documents": 0, "embeddings": 0}
        asset = session.get(Asset, version.asset_id)
        text = _asset_version_text(asset, version)
        meta = {
            "asset_id": version.asset_id,
            "version_no": version.version_no,
            "asset_version_id": version.id,
            "asset_type": asset.type if asset else "",
            "is_selected": version.is_selected,
        }
        document = _upsert_document(
            session,
            kind="asset_version",
            ref_id=f"{version.asset_id}:{version.version_no}",
            text=text,
            meta=meta,
        )
        embedding_created = _ensure_embedding(session, document)
        return {"documents": 1, "embeddings": int(embedding_created)}


def index_feedback_event(feedback_id: str) -> dict[str, int]:
    with session_scope() as session:
        event = session.get(FeedbackEvent, feedback_id)
        if event is None:
            return {"documents": 0, "embeddings": 0}
        text = "\n".join(
            [
                f"Feedback target: {event.output_path}",
                f"Rating: {event.rating if event.rating is not None else 'unknown'}",
                f"Comment: {event.comment}",
                f"Improvement request: {event.improvement_request}",
                f"Category: {event.category}",
            ]
        ).strip()
        document = _upsert_document(
            session,
            kind="feedback",
            ref_id=event.id,
            text=text,
            meta={"feedback_id": event.id, "rating": event.rating, "category": event.category},
        )
        embedding_created = _ensure_embedding(session, document)
        return {"documents": 1, "embeddings": int(embedding_created)}


def upsert_metric_insight(session, ref_id: str, text: str, meta: dict[str, Any]) -> BrainDocument:
    document = _upsert_document(session, "metric_insight", ref_id, text, meta)
    _ensure_embedding(session, document)
    return document


def run_backfill() -> dict[str, int]:
    init_db()
    counts = {"documents": 0, "embeddings": 0, "asset_versions": 0, "feedback": 0, "products": 0, "context_files": 0}
    counts = _backfill_asset_versions(counts)
    counts = _backfill_feedback(counts)
    counts = _backfill_products(counts)
    counts = _backfill_context_files(counts)
    return counts


def _backfill_asset_versions(counts: dict[str, int]) -> dict[str, int]:
    with session_scope() as session:
        version_ids = session.scalars(select(AssetVersion.id).order_by(AssetVersion.id)).all()
    for version_id in version_ids:
        result = index_asset_version(version_id)
        counts["documents"] += result["documents"]
        counts["embeddings"] += result["embeddings"]
        counts["asset_versions"] += int(result["documents"] > 0)
    return counts


def _backfill_feedback(counts: dict[str, int]) -> dict[str, int]:
    with session_scope() as session:
        feedback_ids = session.scalars(select(FeedbackEvent.id).order_by(FeedbackEvent.id)).all()
    for feedback_id in feedback_ids:
        result = index_feedback_event(feedback_id)
        counts["documents"] += result["documents"]
        counts["embeddings"] += result["embeddings"]
        counts["feedback"] += int(result["documents"] > 0)
    return counts


def _backfill_products(counts: dict[str, int]) -> dict[str, int]:
    from .shopify import ShopifyService

    preview = ShopifyService().product_preview(limit=80)
    products = preview.get("products", [])
    with session_scope() as session:
        for product in products:
            if not isinstance(product, dict):
                continue
            ref_id = str(product.get("handle") or product.get("id") or "").strip()
            if not ref_id:
                continue
            text = "\n".join(
                [
                    f"Product: {product.get('title', '')}",
                    f"Handle: {product.get('handle', '')}",
                    f"Type: {product.get('product_type', '')}",
                    f"Tags: {product.get('tags', '')}",
                    f"Description: {product.get('description_excerpt', '')}",
                ]
            )
            document = _upsert_document(session, "product", ref_id, text, product)
            counts["documents"] += 1
            counts["embeddings"] += int(_ensure_embedding(session, document))
            counts["products"] += 1
    return counts


def _backfill_context_files(counts: dict[str, int]) -> dict[str, int]:
    directory = brand_context_dir()
    if not directory.exists():
        return counts
    with session_scope() as session:
        for path in sorted(directory.glob("*.md")):
            document = _upsert_document(
                session,
                "context_file",
                path.name,
                path.read_text(encoding="utf-8"),
                {"path": str(path.relative_to(Path.cwd())) if path.is_relative_to(Path.cwd()) else str(path)},
            )
            counts["documents"] += 1
            counts["embeddings"] += int(_ensure_embedding(session, document))
            counts["context_files"] += 1
    return counts


def _upsert_document(session, kind: str, ref_id: str | None, text: str, meta: dict[str, Any]) -> BrainDocument:
    document = None
    if ref_id is not None:
        document = session.execute(
            select(BrainDocument).where(BrainDocument.kind == kind, BrainDocument.ref_id == ref_id)
        ).scalar_one_or_none()
    if document is None:
        document = BrainDocument(kind=kind, ref_id=ref_id, text=text, meta_json=json.dumps(meta, ensure_ascii=False))
        session.add(document)
        session.flush()
        return document
    next_meta = json.dumps(meta, ensure_ascii=False)
    if document.text != text or document.meta_json != next_meta:
        document.text = text
        document.meta_json = next_meta
        if document.embedding is not None:
            session.delete(document.embedding)
            session.flush()
    return document


def _ensure_embedding(session, document: BrainDocument) -> bool:
    if document.embedding is not None:
        return False
    vector = embed_texts([document.text])[0]
    session.add(
        BrainEmbedding(
            document_id=document.id,
            model=embedding_model_label(),
            dim=vector.size,
            vector=vector_to_blob(vector),
        )
    )
    return True


def _asset_version_text(asset: Asset | None, version: AssetVersion) -> str:
    return "\n".join(
        [
            f"Asset: {asset.title if asset else version.asset_id}",
            f"Type: {asset.type if asset else ''}",
            f"Version: {version.version_no}",
            f"Selected: {version.is_selected}",
            "Prompt:",
            version.prompt_snapshot or "",
            "Content:",
            version.content_text or version.file_path or "",
        ]
    ).strip()


def _memory_rank_score(item: BrainSearchResult) -> float:
    meta = _read_meta(item.document)
    boost = 0.0
    if item.document.kind == "asset_version" and bool(meta.get("is_selected")):
        boost += 0.2
    if item.document.kind == "feedback":
        try:
            rating = float(meta.get("rating"))
        except (TypeError, ValueError):
            rating = 0.0
        if rating >= 4:
            boost += 0.2
    return item.score + boost


def _winner_label(meta: dict[str, Any]) -> str:
    labels = []
    if bool(meta.get("is_selected")):
        labels.append("selected")
    try:
        rating = float(meta.get("rating"))
    except (TypeError, ValueError):
        rating = 0.0
    if rating >= 4:
        labels.append(f"positive_feedback={rating:g}")
    return f" ({', '.join(labels)})" if labels else ""


def _read_meta(document: BrainDocument) -> dict[str, Any]:
    try:
        parsed = json.loads(document.meta_json or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _snippet(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


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


async def handle_brain_index(payload: dict[str, Any]) -> dict[str, int]:
    if payload.get("asset_version_id") is not None:
        return index_asset_version(int(payload["asset_version_id"]))
    if payload.get("feedback_id") is not None:
        return index_feedback_event(str(payload["feedback_id"]))
    if payload.get("backfill"):
        return run_backfill()
    return {"documents": 0, "embeddings": 0}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args != ["backfill"]:
        print("Usage: python -m app.services.brain backfill", file=sys.stderr)
        return 2
    print(json.dumps(run_backfill(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
