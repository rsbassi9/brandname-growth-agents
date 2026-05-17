from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .settings import ROOT_DIR


CAMPAIGN_MEMORY_PATH = ROOT_DIR / "memory" / "campaign_memory.json"


DEFAULT_CAMPAIGN_MEMORY = {
    "campaign_focus": "[4DRFT] launch recovery",
    "active_narrative": "Explain one painting -> seven designs -> wearable fragments.",
    "feed_objective": "Make the next 9-12 posts feel like the launch campaign that should have happened.",
    "product_priorities": [],
    "visual_needs": [],
    "calendar_commitments": [],
    "shoot_gaps": [],
    "channel_implications": [],
    "avoid_list": [
        "Avoid random isolated product posts before the drop story is clear.",
        "Avoid corny drop captions.",
        "Avoid too many black/source-heavy posts in one row.",
    ],
    "summary": "Current priority is relaunch clarity: context first, then product clarity, body proof, process proof, and CTA.",
}


def load_campaign_memory() -> dict[str, Any]:
    if not CAMPAIGN_MEMORY_PATH.exists():
        return {"memory": dict(DEFAULT_CAMPAIGN_MEMORY), "revisions": []}
    try:
        data = json.loads(CAMPAIGN_MEMORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"memory": dict(DEFAULT_CAMPAIGN_MEMORY), "revisions": []}
    return {
        "memory": {**DEFAULT_CAMPAIGN_MEMORY, **data.get("memory", {})},
        "revisions": data.get("revisions", []) if isinstance(data.get("revisions", []), list) else [],
    }


def save_campaign_memory(memory: dict[str, Any], source: str = "manual") -> dict[str, Any]:
    current = load_campaign_memory()
    next_memory = {**DEFAULT_CAMPAIGN_MEMORY, **memory}
    revision = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "memory": next_memory,
    }
    data = {"memory": next_memory, "revisions": [revision, *current.get("revisions", [])][:80]}
    CAMPAIGN_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAMPAIGN_MEMORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def campaign_memory_context() -> str:
    memory = load_campaign_memory().get("memory", {})
    lines = ["Campaign operating memory:"]
    for key, value in memory.items():
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            lines.append(f"- {label}: {', '.join(str(item) for item in value) if value else 'Not specified'}")
        else:
            lines.append(f"- {label}: {value or 'Not specified'}")
    return "\n".join(lines)
