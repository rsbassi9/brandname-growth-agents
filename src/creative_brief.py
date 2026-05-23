from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .settings import MEMORY_DIR


CREATIVE_BRIEF_PATH = MEMORY_DIR / "creative_brief.json"

DEFAULT_BRIEF = {
    "current_drop_focus": "",
    "products_to_push": "",
    "products_to_pause": "",
    "tone": "Premium, quiet, archival, art-led, direct.",
    "visual_references": "",
    "avoid_list": "Avoid corny captions, generic streetwear language, overused trend edits, and repetitive product clustering.",
    "seasonal_direction": "",
}


def load_creative_brief() -> dict[str, Any]:
    if not CREATIVE_BRIEF_PATH.exists():
        return {"brief": dict(DEFAULT_BRIEF), "revisions": []}
    try:
        data = json.loads(CREATIVE_BRIEF_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"brief": dict(DEFAULT_BRIEF), "revisions": []}
    brief = {**DEFAULT_BRIEF, **data.get("brief", {})}
    revisions = data.get("revisions", [])
    return {"brief": brief, "revisions": revisions if isinstance(revisions, list) else []}


def save_creative_brief(brief: dict[str, Any], note: str = "") -> dict[str, Any]:
    current = load_creative_brief()
    next_brief = {**DEFAULT_BRIEF, **brief}
    revision = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "brief": next_brief,
    }
    data = {"brief": next_brief, "revisions": [revision, *current.get("revisions", [])][:80]}
    CREATIVE_BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREATIVE_BRIEF_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def creative_brief_context() -> str:
    data = load_creative_brief()
    brief = data.get("brief", {})
    lines = ["Current creative steering brief:"]
    for key, value in brief.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value or 'Not specified'}")
    return "\n".join(lines)
