"""Performance CSV import service (P8-2)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.parser import BytesParser
from email.policy import default
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CalendarItem, PostMetric, PublishedPost
from .brain import upsert_metric_insight

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


@dataclass(frozen=True)
class BestTimeSlot:
    channel: str
    weekday: int
    hour: int
    sample_size: int
    mean_engagement_rate: float


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
    _auto_link_imported_posts(session, result.posts)
    _write_metric_insights(session, result.posts)
    return result


def best_times(session: Session, channel: str | None = None) -> list[BestTimeSlot]:
    query = select(PublishedPost)
    if channel:
        query = query.where(PublishedPost.channel == channel)
    posts = session.execute(query.order_by(PublishedPost.id)).scalars().unique().all()
    buckets: dict[tuple[str, int, int], list[float]] = {}
    for post in posts:
        if post.published_at is None:
            continue
        metric = _latest_metric(post)
        if metric is None or metric.engagement_rate is None:
            continue
        key = (post.channel, post.published_at.weekday(), post.published_at.hour)
        buckets.setdefault(key, []).append(metric.engagement_rate)

    slots = [
        BestTimeSlot(
            channel=key[0],
            weekday=key[1],
            hour=key[2],
            sample_size=len(values),
            mean_engagement_rate=sum(values) / len(values),
        )
        for key, values in buckets.items()
        if len(values) >= 3
    ]
    slots.sort(key=lambda slot: (-slot.mean_engagement_rate, slot.channel, slot.weekday, slot.hour))
    return slots


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


def link_published_post(session: Session, post_id: int, calendar_item_id: str | None, asset_id: int | None) -> PublishedPost:
    post = session.get(PublishedPost, post_id)
    if post is None:
        raise ValueError("Published post not found")
    if calendar_item_id is not None:
        item = session.get(CalendarItem, calendar_item_id)
        if item is None:
            raise ValueError("Calendar item not found")
        post.calendar_item_id = item.id
        post.asset_id = asset_id if asset_id is not None else item.asset_id
    elif asset_id is not None:
        post.asset_id = asset_id
    return post


def unlink_published_post(session: Session, post_id: int) -> PublishedPost:
    post = session.get(PublishedPost, post_id)
    if post is None:
        raise ValueError("Published post not found")
    post.calendar_item_id = None
    post.asset_id = None
    return post


def _auto_link_imported_posts(session: Session, posts: list[PublishedPost]) -> None:
    seen: set[int] = set()
    for post in posts:
        if post.id in seen or post.calendar_item_id is not None or post.published_at is None:
            continue
        seen.add(post.id)
        candidates = _calendar_candidates(session, post.channel, post.published_at)
        if len(candidates) == 1:
            post.calendar_item_id = candidates[0].id
            post.asset_id = candidates[0].asset_id


def _calendar_candidates(session: Session, channel: str, published_at: datetime) -> list[CalendarItem]:
    target = published_at.date()
    lower = (target - timedelta(days=1)).isoformat()
    upper = (target + timedelta(days=1)).isoformat()
    rows = session.execute(
        select(CalendarItem).where(CalendarItem.date >= lower, CalendarItem.date <= upper)
    ).scalars().all()
    return [row for row in rows if _calendar_channel(row) == channel]


def _calendar_channel(item: CalendarItem) -> str:
    try:
        data = json.loads(item.data_json or "{}")
    except json.JSONDecodeError:
        return ""
    channel = data.get("channel") or data.get("platform")
    if isinstance(channel, str):
        return channel.lower().strip()
    channels = data.get("channels")
    if isinstance(channels, list) and len(channels) == 1:
        return str(channels[0]).lower().strip()
    return ""


def _write_metric_insights(session: Session, posts: list[PublishedPost]) -> None:
    unique_posts = {post.id: post for post in posts}.values()
    scored: list[tuple[PublishedPost, PostMetric]] = []
    for post in unique_posts:
        latest = _latest_metric(post)
        if latest is not None and latest.engagement_rate is not None:
            scored.append((post, latest))
    if not scored:
        return
    scored.sort(key=lambda item: (item[1].engagement_rate or 0, item[0].id))
    count = max(1, len(scored) // 4)
    selected = [*scored[:count], *scored[-count:]]
    for post, metric in selected:
        percent = (metric.engagement_rate or 0) * 100
        hook = _first_line(post.title_or_caption or post.external_ref or "untitled")
        post_type = post.post_type or "post"
        text = f"{post_type} with hook '{hook}' achieved {percent:.2f}% on {post.channel}"
        upsert_metric_insight(
            session,
            ref_id=f"post_metric:{post.id}:{metric.id}",
            text=text,
            meta={
                "published_post_id": post.id,
                "post_metric_id": metric.id,
                "channel": post.channel,
                "engagement_rate": metric.engagement_rate,
            },
        )


def _latest_metric(post: PublishedPost) -> PostMetric | None:
    metrics = list(post.metrics)
    if not metrics:
        return None
    return sorted(metrics, key=lambda metric: metric.captured_at)[-1]


def _first_line(value: str) -> str:
    line = value.strip().splitlines()[0] if value.strip() else "untitled"
    return line[:120]


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
