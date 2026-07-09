"""Performance CSV import service (P8-2)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PostMetric, PublishedPost

CHANNELS = {"instagram", "tiktok", "facebook", "other"}

HEADER_ALIASES: dict[str, set[str]] = {
    "posted_at": {"publish time", "post date", "date", "post time", "posted date", "create time"},
    "external_ref": {"permalink", "post url", "video link", "video url"},
    "title_or_caption": {"caption", "post caption", "description", "title", "video title", "text"},
    "post_type": {"post type", "type", "media type", "content type"},
    "views": {"views", "plays", "impressions"},
    "reach": {"reach", "accounts reached"},
    "likes": {"likes", "like count"},
    "comments": {"comments", "comment count"},
    "shares": {"shares", "share count"},
    "saves": {"saved", "saves", "favorites"},
    "clicks": {"clicks", "link clicks", "website clicks"},
    "follows_from_post": {"follows from post", "new followers", "follows"},
}

METRIC_FIELDS = ("views", "reach", "likes", "comments", "shares", "saves", "clicks", "follows_from_post")


@dataclass
class ImportResult:
    status: str = "imported"
    detected_columns: list[str] = field(default_factory=list)
    posts_upserted: int = 0
    metrics_inserted: int = 0
    warnings: list[str] = field(default_factory=list)
    posts: list[PublishedPost] = field(default_factory=list)
    metrics: list[PostMetric] = field(default_factory=list)


class PerformanceImportError(ValueError):
    def __init__(self, message: str, detected_columns: list[str]) -> None:
        super().__init__(message)
        self.detected_columns = detected_columns


def parse_import_request_body(content_type: str, body: bytes) -> tuple[str, str]:
    if "multipart/form-data" in content_type.lower():
        return _parse_multipart(content_type, body)
    payload = json.loads(body.decode("utf-8"))
    return str(payload.get("channel", "other")), str(payload.get("csv_text", ""))


def import_performance_csv(session: Session, channel: str, csv_text: str) -> ImportResult:
    normalized_channel = channel.lower().strip()
    if normalized_channel not in CHANNELS:
        raise PerformanceImportError("Unsupported performance channel", [])

    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    detected_columns = list(reader.fieldnames or [])
    mapping = _detect_columns(detected_columns)
    if not detected_columns or "posted_at" not in mapping or not {"external_ref", "title_or_caption"} & set(mapping):
        raise PerformanceImportError("Could not auto-detect required performance columns", detected_columns)
    if not any(field in mapping for field in METRIC_FIELDS):
        raise PerformanceImportError("At least one engagement metric column is required", detected_columns)

    result = ImportResult(detected_columns=detected_columns)
    for index, row in enumerate(reader, start=2):
        normalized_row = {_normalize_header(key): value for key, value in row.items() if key is not None}
        imported = _import_row(session, normalized_channel, mapping, normalized_row, detected_columns, index, result)
        if imported is None:
            continue
        post, metric, metric_created = imported
        result.posts.append(post)
        result.posts_upserted += 1
        if metric_created:
            result.metrics.append(metric)
            result.metrics_inserted += 1
    return result


def _import_row(
    session: Session,
    channel: str,
    mapping: dict[str, str],
    row: dict[str, str],
    detected_columns: list[str],
    row_number: int,
    result: ImportResult,
) -> tuple[PublishedPost, PostMetric, bool] | None:
    posted_at = _parse_datetime(_value(row, mapping, "posted_at"))
    external_ref = _value(row, mapping, "external_ref")
    title_or_caption = _value(row, mapping, "title_or_caption")
    if posted_at is None or (not external_ref and not title_or_caption):
        result.warnings.append(f"row {row_number}: skipped missing posted_at or post identity")
        return None

    metric_values = {field: _parse_number(_value(row, mapping, field), row_number, field, result) for field in METRIC_FIELDS}
    if all(metric_values[field] is None for field in METRIC_FIELDS):
        result.warnings.append(f"row {row_number}: skipped missing engagement metrics")
        return None

    permalink = external_ref if external_ref and external_ref.startswith(("http://", "https://")) else None
    natural_ref = external_ref or _fallback_ref(channel, posted_at, title_or_caption)
    post = _upsert_post(
        session,
        channel=channel,
        external_ref=natural_ref,
        permalink=permalink,
        published_at=posted_at,
        title_or_caption=title_or_caption,
        post_type=_value(row, mapping, "post_type"),
        meta=_unknown_columns(row, mapping, detected_columns),
    )
    metric = session.execute(
        select(PostMetric).where(PostMetric.published_post_id == post.id, PostMetric.captured_at == posted_at)
    ).scalar_one_or_none()
    if metric is not None:
        return post, metric, False

    metric = PostMetric(
        published_post_id=post.id,
        captured_at=posted_at,
        impressions=metric_values["views"],
        reach=metric_values["reach"],
        likes=metric_values["likes"],
        comments=metric_values["comments"],
        shares=metric_values["shares"],
        saves=metric_values["saves"],
        clicks=metric_values["clicks"],
        follows_from_post=metric_values["follows_from_post"],
        meta_json=json.dumps(_unknown_columns(row, mapping, detected_columns), ensure_ascii=False),
    )
    session.add(metric)
    session.flush()
    return post, metric, True


def _upsert_post(
    session: Session,
    *,
    channel: str,
    external_ref: str,
    permalink: str | None,
    published_at: datetime,
    title_or_caption: str,
    post_type: str,
    meta: dict[str, str],
) -> PublishedPost:
    post = session.execute(
        select(PublishedPost).where(PublishedPost.channel == channel, PublishedPost.external_ref == external_ref)
    ).scalar_one_or_none()
    if post is None:
        post = PublishedPost(channel=channel, external_ref=external_ref)
        session.add(post)
        session.flush()
    post.permalink = permalink or post.permalink
    post.published_at = published_at
    post.title_or_caption = title_or_caption
    post.post_type = post_type
    post.meta_json = json.dumps(meta, ensure_ascii=False)
    return post


def _detect_columns(columns: list[str]) -> dict[str, str]:
    normalized = {_normalize_header(column): column for column in columns}
    mapping: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            key = _normalize_header(alias)
            if key in normalized:
                mapping[canonical] = key
                break
    return mapping


def _value(row: dict[str, str], mapping: dict[str, str], canonical: str) -> str:
    key = mapping.get(canonical)
    return str(row.get(key, "")).strip() if key else ""


def _unknown_columns(row: dict[str, str], mapping: dict[str, str], detected_columns: list[str]) -> dict[str, str]:
    used = set(mapping.values())
    return {
        column: str(row.get(_normalize_header(column), "")).strip()
        for column in detected_columns
        if _normalize_header(column) not in used
    }


def _parse_number(value: str, row_number: int, field: str, result: ImportResult) -> int | None:
    raw = value.strip().replace(",", "")
    if not raw:
        return None
    multiplier = 1
    if raw[-1:].lower() == "k":
        multiplier = 1_000
        raw = raw[:-1]
    elif raw[-1:].lower() == "m":
        multiplier = 1_000_000
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        result.warnings.append(f"row {row_number}: {field} value '{value}' could not be parsed")
        return None


def _parse_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _fallback_ref(channel: str, posted_at: datetime, title_or_caption: str) -> str:
    digest = hashlib.sha1(f"{channel}|{posted_at.isoformat()}|{title_or_caption}".encode("utf-8")).hexdigest()[:12]
    return f"{channel}:{posted_at.date().isoformat()}:{digest}"


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_]+", " ", value.strip().lower())


def _parse_multipart(content_type: str, body: bytes) -> tuple[str, str]:
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    channel = "other"
    csv_text = ""
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        content = part.get_payload(decode=True) or b""
        if name == "channel":
            channel = content.decode("utf-8").strip()
        elif name in {"file", "csv", "csv_file"}:
            csv_text = content.decode("utf-8-sig")
    return channel, csv_text
