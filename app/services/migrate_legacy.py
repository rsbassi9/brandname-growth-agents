"""One-shot legacy importer: memory/*.json + outputs/ -> DB.

Idempotent: re-running produces no duplicates. Natural keys:
- calendar_items: legacy string id
- feedback_events: legacy uuid id (or a content hash when missing)
- assets from outputs/: relative file path (assets.source_path, unique)

CLI: python -m app.services.migrate_legacy
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from ..db import init_db, session_scope
from ..models import Asset, AssetVersion, CalendarItem, FeedbackEvent
from ..paths import memory_dir, outputs_dir

logger = logging.getLogger(__name__)

# type inferred from path/extension (P1-1)
_DIR_TYPE_MAP = {
    "visual_content": "carousel",
    "image_concepts": "image_concept",
}
_SKIP_SUFFIXES = {".log", ".tmp", ".ds_store"}


def infer_asset_type(relative_path: Path) -> str:
    parts = [part.lower() for part in relative_path.parts]
    for folder, asset_type in _DIR_TYPE_MAP.items():
        if folder in parts:
            return asset_type
    suffix = relative_path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image_concept"
    if suffix in {".mov", ".mp4", ".m4v"}:
        return "video_script"
    return "copy"


def migrate_calendar(session) -> int:
    path = memory_dir() / "content_calendar.json"
    if not path.exists():
        return 0
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("content_calendar.json is not valid JSON; skipping calendar migration")
        return 0

    imported = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("id") or "").strip()
        if not item_id:
            item_id = "legacy-" + hashlib.sha1(
                json.dumps(raw, sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
        existing = session.get(CalendarItem, item_id)
        if existing is not None:
            continue
        session.add(
            CalendarItem(
                id=item_id,
                date=str(raw.get("date") or raw.get("scheduled_date") or ""),
                status=str(raw.get("status") or ""),
                asset_id=None,
                data_json=json.dumps(raw, ensure_ascii=False),
            )
        )
        imported += 1
    return imported


def migrate_feedback(session) -> int:
    path = memory_dir() / "feedback.jsonl"
    if not path.exists():
        return 0

    imported = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping unreadable feedback line: %.80s", line)
            continue
        event_id = str(raw.get("id") or "").strip() or hashlib.sha1(line.encode("utf-8")).hexdigest()
        if session.get(FeedbackEvent, event_id) is not None:
            continue
        rating = raw.get("rating")
        session.add(
            FeedbackEvent(
                id=event_id,
                created_at=str(raw.get("created_at") or ""),
                output_path=str(raw.get("output_path") or ""),
                rating=int(rating) if isinstance(rating, (int, float)) else None,
                comment=str(raw.get("comment") or ""),
                improvement_request=str(raw.get("improvement_request") or ""),
                category=str(raw.get("category") or "general"),
                data_json=json.dumps(raw, ensure_ascii=False),
            )
        )
        imported += 1
    return imported


def migrate_outputs(session) -> int:
    root = outputs_dir()
    if not root.exists():
        return 0

    imported = 0
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        relative = file_path.relative_to(root)
        source_path = f"outputs/{relative.as_posix()}"
        exists = session.execute(
            select(Asset.id).where(Asset.source_path == source_path)
        ).scalar_one_or_none()
        if exists is not None:
            continue

        asset_type = infer_asset_type(relative)
        created = datetime.fromtimestamp(file_path.stat().st_mtime)
        asset = Asset(
            campaign_id=None,
            type=asset_type,
            title=file_path.stem[:500],
            status="draft",
            source_path=source_path,
            created_at=created,
        )
        session.add(asset)
        session.flush()  # assign asset.id

        content_text: str | None = None
        if file_path.suffix.lower() in {".md", ".txt", ".json"}:
            try:
                content_text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                logger.warning("Could not read %s as text; storing path only", file_path)
        session.add(
            AssetVersion(
                asset_id=asset.id,
                version_no=1,
                prompt_snapshot="",
                params_json=json.dumps({"imported_from": source_path}),
                content_text=content_text,
                file_path=source_path,
                model_used="legacy-import",
                created_at=created,
                is_selected=True,
            )
        )
        imported += 1
    return imported


def run_migration() -> dict[str, int]:
    init_db()
    with session_scope() as session:
        new_calendar = migrate_calendar(session)
        new_feedback = migrate_feedback(session)
        new_assets = migrate_outputs(session)
        counts = {
            "calendar_items_new": new_calendar,
            "feedback_events_new": new_feedback,
            "assets_new": new_assets,
            "calendar_items_total": session.execute(
                select(func.count()).select_from(CalendarItem)
            ).scalar_one(),
            "feedback_events_total": session.execute(
                select(func.count()).select_from(FeedbackEvent)
            ).scalar_one(),
            "assets_total": session.execute(select(func.count()).select_from(Asset)).scalar_one(),
            "asset_versions_total": session.execute(
                select(func.count()).select_from(AssetVersion)
            ).scalar_one(),
        }
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    counts = run_migration()
    for name, value in counts.items():
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
