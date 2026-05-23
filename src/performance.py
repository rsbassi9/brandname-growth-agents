from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any

from .settings import MEMORY_DIR


PERFORMANCE_PATH = MEMORY_DIR / "performance_records.json"

METRIC_FIELDS = ["reach", "saves", "shares", "follows", "profile_visits", "clicks", "orders"]


def load_performance_records() -> list[dict[str, Any]]:
    if not PERFORMANCE_PATH.exists():
        return []
    try:
        data = json.loads(PERFORMANCE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def save_performance_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    records = load_performance_records()
    record_id = record.get("id") or record.get("post_id") or f"performance-{datetime.now().isoformat(timespec='seconds')}"
    normalized = _normalize_record({**record, "id": record_id})
    records = [item for item in records if item.get("id") != record_id and item.get("post_id") != normalized.get("post_id")]
    records.append(normalized)
    records.sort(key=lambda item: item.get("posted_date") or "", reverse=True)
    PERFORMANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERFORMANCE_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def performance_summary(records: list[dict[str, Any]] | None = None, limit: int = 8) -> dict[str, Any]:
    records = records if records is not None else load_performance_records()
    if not records:
        return {
            "headline": "No posted performance records yet.",
            "top_posts": [],
            "format_mix": {},
            "product_mix": {},
            "learning_notes": ["Add posted date, URL, and first metrics once posts go live."],
        }
    scored = sorted(records, key=lambda item: _performance_score(item), reverse=True)
    format_mix: dict[str, int] = {}
    product_mix: dict[str, int] = {}
    for record in records:
        format_mix[record.get("format", "Post")] = format_mix.get(record.get("format", "Post"), 0) + 1
        product = record.get("product_family") or "Unmapped"
        product_mix[product] = product_mix.get(product, 0) + 1
    top_posts = [
        {
            "id": item.get("id"),
            "hook": item.get("hook", ""),
            "format": item.get("format", ""),
            "posted_date": item.get("posted_date", ""),
            "score": _performance_score(item),
            "metrics": item.get("metrics", {}),
            "assets": item.get("assets", []),
        }
        for item in scored[:limit]
    ]
    return {
        "headline": f"{len(records)} posted record{'s' if len(records) != 1 else ''} tracked. Best score: {_performance_score(scored[0])}.",
        "top_posts": top_posts,
        "format_mix": format_mix,
        "product_mix": product_mix,
        "learning_notes": _learning_notes(scored),
    }


def performance_context_for_agents(limit: int = 8) -> str:
    summary = performance_summary(limit=limit)
    lines = ["Performance memory:", f"- {summary['headline']}"]
    for note in summary.get("learning_notes", [])[:5]:
        lines.append(f"- {note}")
    for post in summary.get("top_posts", [])[:limit]:
        lines.append(f"- Top post: {post.get('hook') or post.get('id')} | {post.get('format')} | score {post.get('score')}")
    return "\n".join(lines)


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record.get("metrics", {})
    record["metrics"] = {field: _int(metrics.get(field, 0)) for field in METRIC_FIELDS}
    record["posted_date"] = record.get("posted_date") or date.today().isoformat()
    record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    record["score"] = _performance_score(record)
    return record


def _performance_score(record: dict[str, Any]) -> int:
    metrics = record.get("metrics", {})
    return (
        _int(metrics.get("reach", 0))
        + _int(metrics.get("saves", 0)) * 8
        + _int(metrics.get("shares", 0)) * 10
        + _int(metrics.get("follows", 0)) * 18
        + _int(metrics.get("profile_visits", 0)) * 4
        + _int(metrics.get("clicks", 0)) * 12
        + _int(metrics.get("orders", 0)) * 80
    )


def _learning_notes(records: list[dict[str, Any]]) -> list[str]:
    notes = []
    if records:
        best = records[0]
        notes.append(f"Highest signal so far: {best.get('hook') or best.get('id')} with score {_performance_score(best)}.")
    high_save = [item for item in records if _int(item.get("metrics", {}).get("saves", 0)) >= 5]
    if high_save:
        notes.append("Saved posts should influence future carousel/storytelling choices.")
    high_click = [item for item in records if _int(item.get("metrics", {}).get("clicks", 0)) >= 3 or _int(item.get("metrics", {}).get("orders", 0)) > 0]
    if high_click:
        notes.append("Click/order posts should influence product rotation and SEO/Ads priority.")
    return notes or ["Add more posted records before drawing creative conclusions."]


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
