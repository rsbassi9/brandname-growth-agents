"""Source photo ingestion for P4-4.

Indexes source images into `source_assets` without making generation calls.
Drive and Shopify integrations reuse the ported read-only services and stay
mockable in tests.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import init_db, session_scope
from ..models import SourceAsset

IMAGE_SUFFIXES = {".avif", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".webp"}


def list_source_assets(session: Session, origin: str | None = None, q: str | None = None) -> tuple[list[SourceAsset], int]:
    query = select(SourceAsset)
    if origin:
        query = query.where(SourceAsset.origin == origin)
    if q:
        query = query.where(SourceAsset.path.ilike(f"%{q}%"))
    total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = session.execute(query.order_by(SourceAsset.created_at.desc(), SourceAsset.id.desc())).scalars().all()
    return rows, total


def index_local_folder(session: Session, folder: str, tags: list[str] | None = None, limit: int = 100) -> list[SourceAsset]:
    root = Path(folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Local source folder does not exist: {folder}")
    indexed: list[SourceAsset] = []
    for path in sorted(root.rglob("*")):
        if len(indexed) >= limit:
            break
        if not path.is_file() or not _is_image_path(path):
            continue
        relative_tags = [part for part in path.relative_to(root).parts[:-1] if part]
        indexed.append(
            upsert_source_asset(
                session,
                origin="local",
                path=str(path),
                tags=[*(tags or []), *relative_tags],
                product_handle=None,
            )
        )
    return indexed


def index_drive_sources(session: Session, tags: list[str] | None = None, limit: int = 100) -> list[SourceAsset]:
    from .drive import GoogleDriveService

    service = GoogleDriveService()
    rows: list[SourceAsset] = []
    for item in service.list_raw_assets()[:limit]:
        mime = str(item.get("mimeType", ""))
        if not mime.startswith("image/"):
            continue
        path = str(item.get("webViewLink") or item.get("webContentLink") or f"drive://{item.get('id', '')}")
        item_tags = [
            str(value)
            for value in [
                item.get("creativeBucket"),
                item.get("category"),
                item.get("folderPath"),
                item.get("name"),
            ]
            if value
        ]
        rows.append(upsert_source_asset(session, "drive", path, [*(tags or []), *item_tags], None))
    return rows


def index_shopify_sources(session: Session, tags: list[str] | None = None, limit: int = 100) -> list[SourceAsset]:
    from .shopify import ShopifyService

    service = ShopifyService()
    rows: list[SourceAsset] = []
    for item in service.product_image_sources(limit=limit):
        path = str(item.get("src") or item.get("url") or "")
        if not path:
            continue
        item_tags = [
            str(value)
            for value in [
                item.get("product_title"),
                item.get("product_type"),
                item.get("alt"),
            ]
            if value
        ]
        rows.append(
            upsert_source_asset(
                session,
                "shopify",
                path,
                [*(tags or []), *item_tags],
                str(item.get("product_handle") or "") or None,
            )
        )
    return rows


def upsert_source_asset(
    session: Session,
    origin: str,
    path: str,
    tags: list[str] | None,
    product_handle: str | None,
) -> SourceAsset:
    row = session.execute(
        select(SourceAsset).where(SourceAsset.origin == origin, SourceAsset.path == path)
    ).scalar_one_or_none()
    clean_tags = sorted({tag.strip() for tag in tags or [] if tag and tag.strip()})
    if row is None:
        row = SourceAsset(
            origin=origin,
            path=path,
            tags_json=json.dumps(clean_tags, ensure_ascii=False),
            product_handle=product_handle,
        )
        session.add(row)
        session.flush()
    else:
        existing = set(_json_list(row.tags_json))
        row.tags_json = json.dumps(sorted(existing.union(clean_tags)), ensure_ascii=False)
        if product_handle:
            row.product_handle = product_handle
    return row


def resolve_reference_context(session: Session, source_asset_ids: list[int] | None) -> dict[str, Any]:
    ids = [int(value) for value in source_asset_ids or []][:4]
    if not ids:
        return {"source_asset_ids": [], "reference_paths": [], "source_asset_context": []}
    rows = session.execute(select(SourceAsset).where(SourceAsset.id.in_(ids))).scalars().all()
    by_id = {row.id: row for row in rows}
    ordered = [by_id[source_id] for source_id in ids if source_id in by_id]
    return {
        "source_asset_ids": [row.id for row in ordered],
        "reference_paths": [row.path for row in ordered],
        "source_asset_context": [
            {
                "id": row.id,
                "origin": row.origin,
                "path": row.path,
                "tags": _json_list(row.tags_json),
                "product_handle": row.product_handle,
            }
            for row in ordered
        ],
    }


def index_sources(origin: str, path: str = "", tags: list[str] | None = None, limit: int = 100) -> list[SourceAsset]:
    init_db()
    with session_scope() as session:
        if origin == "local":
            return index_local_folder(session, path, tags, limit)
        if origin == "drive":
            return index_drive_sources(session, tags, limit)
        if origin == "shopify":
            return index_shopify_sources(session, tags, limit)
        raise ValueError(f"Unsupported source asset origin: {origin}")


def _is_image_path(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    return path.suffix.lower() in IMAGE_SUFFIXES or bool(mime and mime.startswith("image/"))


def _json_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Index source photos for reference-grounded generation.")
    parser.add_argument("origin", choices=["local", "drive", "shopify"])
    parser.add_argument("--path", default="", help="Local folder path when origin=local.")
    parser.add_argument("--tag", action="append", default=[], help="Additional tag to store on every indexed source.")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    rows = index_sources(args.origin, path=args.path, tags=args.tag, limit=args.limit)
    print(json.dumps({"indexed": len(rows), "ids": [row.id for row in rows]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
