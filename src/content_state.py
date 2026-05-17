from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .settings import ROOT_DIR


CONTENT_STATE_PATH = ROOT_DIR / "memory" / "content_state.json"
CONTENT_STATE_EVENTS_PATH = ROOT_DIR / "memory" / "content_state_events.jsonl"

LIFECYCLE_STATES = [
    "Draft",
    "Needs Review",
    "Approved",
    "Rejected",
    "Scheduled",
    "Posted",
    "Measured",
    "Learned",
    "Applied",
]


def item_key(item_type: str, item_id: str) -> str:
    return f"{item_type}:{item_id}"


def load_content_state() -> dict[str, dict[str, Any]]:
    if not CONTENT_STATE_PATH.exists():
        return {}
    try:
        data = json.loads(CONTENT_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_content_state(state: dict[str, dict[str, Any]]) -> None:
    CONTENT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_content_state(item_type: str, item_id: str) -> dict[str, Any]:
    return load_content_state().get(item_key(item_type, item_id), {})


def update_content_state(
    item_type: str,
    item_id: str,
    status: str | None = None,
    notes: str = "",
    title: str = "",
    metadata: dict[str, Any] | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    state = load_content_state()
    key = item_key(item_type, item_id)
    before = dict(state.get(key, {}))
    entry = dict(before)
    entry.update(
        {
            "item_type": item_type,
            "item_id": item_id,
            "title": title or entry.get("title", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    if status:
        entry["status"] = status
    if notes:
        entry["notes"] = notes
    if metadata:
        existing_metadata = entry.get("metadata", {})
        entry["metadata"] = {**existing_metadata, **metadata}
    state[key] = entry
    save_content_state(state)
    _append_state_event(key, before, entry, source)
    return entry


def content_state_summary(limit: int = 80) -> str:
    state = load_content_state()
    if not state:
        return "No content lifecycle state has been recorded yet."
    lines = ["Content lifecycle memory:"]
    for entry in sorted(state.values(), key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]:
        title = entry.get("title") or entry.get("item_id", "")
        lines.append(
            f"- {entry.get('item_type', 'item')}:{entry.get('item_id', '')} | "
            f"{entry.get('status', 'Draft')} | {title}"
            f"{' | ' + entry.get('notes', '') if entry.get('notes') else ''}"
        )
    return "\n".join(lines)


def _append_state_event(key: str, before: dict[str, Any], after: dict[str, Any], source: str) -> None:
    event = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "key": key,
        "before_status": before.get("status"),
        "after_status": after.get("status"),
        "before": before,
        "after": after,
    }
    CONTENT_STATE_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONTENT_STATE_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")

