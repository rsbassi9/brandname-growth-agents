from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from .settings import ROOT_DIR


MEMORY_DIR = ROOT_DIR / "memory"
FEEDBACK_PATH = MEMORY_DIR / "feedback.jsonl"


@dataclass
class FeedbackEntry:
    output_path: str
    rating: int
    comment: str
    improvement_request: str
    category: str


def append_feedback(entry: FeedbackEntry) -> dict:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": str(uuid4()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_path": entry.output_path,
        "rating": entry.rating,
        "comment": entry.comment.strip(),
        "improvement_request": entry.improvement_request.strip(),
        "category": entry.category.strip() or "general",
    }
    with FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


def load_feedback(limit: int = 80) -> list[dict]:
    if not FEEDBACK_PATH.exists():
        return []

    entries: list[dict] = []
    for line in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries[-limit:]


def feedback_summary(limit: int = 20) -> str:
    entries = load_feedback(limit)
    if not entries:
        return "No human feedback has been logged yet."

    lines = ["Recent human feedback to apply in future outputs:"]
    for item in entries:
        lines.append(
            "- "
            f"{item.get('category', 'general')} | rating {item.get('rating', 'n/a')}/5 | "
            f"comment: {item.get('comment', '')} | improvement: {item.get('improvement_request', '')}"
        )
    return "\n".join(lines)
