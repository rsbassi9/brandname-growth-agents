"""Port of src/learning.py feedback loop (P1-3). Signatures preserved.

The jsonl file remains the legacy learning store; feedback posted through the
API is additionally persisted to the feedback_events table by the router.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..paths import memory_dir

logger = logging.getLogger(__name__)


def _feedback_path() -> Path:
    return memory_dir() / "feedback.jsonl"


@dataclass
class FeedbackEntry:
    output_path: str
    rating: int
    comment: str
    improvement_request: str
    category: str


def append_feedback(entry: FeedbackEntry) -> dict:
    memory_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "id": str(uuid4()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_path": entry.output_path,
        "rating": entry.rating,
        "comment": entry.comment.strip(),
        "improvement_request": entry.improvement_request.strip(),
        "category": entry.category.strip() or "general",
    }
    with _feedback_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


def load_feedback(limit: int = 80) -> list[dict]:
    path = _feedback_path()
    if not path.exists():
        return []

    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            # Explicit fallback: skip corrupt lines but record the problem.
            logger.warning("Skipping unreadable feedback line: %.80s", line)
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
