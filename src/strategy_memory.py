from __future__ import annotations

import csv
from datetime import datetime
import io
import json
from pathlib import Path
from collections import Counter
import re

from .settings import MEMORY_DIR


INSTAGRAM_POSTS_PATH = MEMORY_DIR / "instagram_posts.json"
BRAND_TIMELINE_PATH = MEMORY_DIR / "brand_timeline.json"
STRATEGY_ROADMAP_PATH = MEMORY_DIR / "strategy_roadmap.json"
EXTERNAL_PROMPTS_PATH = MEMORY_DIR / "external_creative_prompts.json"


ROADMAP = [
    {
        "phase": "Foundation",
        "items": [
            "Manual Instagram memory/import",
            "Calendar reconciliation/status updates",
            "Brand timeline",
            "Journey/vibe memory",
            "Asset usage memory",
            "Product truth profiles",
        ],
    },
    {
        "phase": "Content Strategy",
        "items": [
            "Post opinion/strategist notes",
            "Why this post exists",
            "Launch phase system",
            "Confidence scores",
            "Creative requests queue",
        ],
    },
    {
        "phase": "External Creative",
        "items": [
            "Creative prompt field for fal.ai/Runway/Kling",
            "Prompt lifecycle tracking",
            "Attach generated external files from Drive",
        ],
    },
    {
        "phase": "SEO",
        "items": [
            "Google Search Console integration",
            "PageSpeed Insights integration",
            "Shopify read-only SEO audit",
            "SEO draft approvals",
        ],
    },
    {
        "phase": "Ads",
        "items": [
            "Ad concept strategy",
            "Ad readiness scoring",
            "Tracking health checklist",
            "Meta Ads read-only reporting later",
        ],
    },
    {
        "phase": "Automation Later",
        "items": [
            "Official Instagram Graph API sync",
            "Weekly strategist review",
            "Approval-gated Shopify/SEO writes",
        ],
    },
    {
        "phase": "UI / UX Workflow",
        "items": [
            "Strategy Hub home",
            "Fewer modes, clearer grouped workflow",
            "Visual status lanes for Draft, Posted, Measured, Learned",
            "Compact insight cards instead of long report walls",
            "Post builder shows strategy, assets, prompt, SEO, and ad use from one screen",
        ],
    },
]


def strategy_hub(calendar_items: list[dict], raw_assets: list[dict]) -> dict:
    posts = load_instagram_posts()
    timeline = load_brand_timeline()
    prompts = load_external_prompts()
    reconciliation = reconcile_instagram_posts(calendar_items, apply=False)
    return {
        "roadmap": load_roadmap(),
        "instagram": instagram_summary(posts, calendar_items),
        "reconciliation": reconciliation,
        "timeline": timeline,
        "asset_usage": asset_usage_summary(calendar_items, posts, raw_assets),
        "external_prompts": prompts,
        "workflow_concept": workflow_concept(),
    }


def load_roadmap() -> list[dict]:
    if not STRATEGY_ROADMAP_PATH.exists():
        save_roadmap(ROADMAP)
    try:
        data = json.loads(STRATEGY_ROADMAP_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = ROADMAP
    return data if isinstance(data, list) else ROADMAP


def save_roadmap(data: list[dict]) -> None:
    STRATEGY_ROADMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_ROADMAP_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_instagram_posts() -> list[dict]:
    return _load_list(INSTAGRAM_POSTS_PATH)


def save_instagram_posts(posts: list[dict]) -> list[dict]:
    normalized = [_normalize_instagram_post(post) for post in posts]
    normalized = sorted(normalized, key=lambda item: item.get("posted_date", ""), reverse=True)
    _save_list(INSTAGRAM_POSTS_PATH, normalized)
    return normalized


def import_instagram_csv(csv_text: str) -> list[dict]:
    existing = load_instagram_posts()
    by_key = {_instagram_key(post): post for post in existing}
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        post = _normalize_instagram_post(row)
        by_key[_instagram_key(post)] = {**by_key.get(_instagram_key(post), {}), **post}
    return save_instagram_posts(list(by_key.values()))


def load_brand_timeline() -> list[dict]:
    items = _load_list(BRAND_TIMELINE_PATH)
    if items:
        return items
    default_items = [
        {
            "date": "",
            "title": "First source painting",
            "type": "origin",
            "notes": "Physical oil painting becomes the source system.",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
        {
            "date": "",
            "title": "First post",
            "type": "content",
            "notes": "The first public sequence establishes source, system, fragment, wear.",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    ]
    _save_list(BRAND_TIMELINE_PATH, default_items)
    return default_items


def add_brand_timeline_item(item: dict) -> list[dict]:
    items = load_brand_timeline()
    items.append(
        {
            "date": str(item.get("date", "")).strip(),
            "title": str(item.get("title", "")).strip() or "Untitled moment",
            "type": str(item.get("type", "")).strip() or "note",
            "notes": str(item.get("notes", "")).strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    items = sorted(items, key=lambda entry: entry.get("date", "") or "9999-99-99")
    _save_list(BRAND_TIMELINE_PATH, items)
    return items


def load_external_prompts() -> list[dict]:
    return _load_list(EXTERNAL_PROMPTS_PATH)


def add_external_prompt(item: dict) -> list[dict]:
    items = load_external_prompts()
    prompt_id = f"prompt-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    items.insert(
        0,
        {
            "id": prompt_id,
            "post_id": str(item.get("post_id", "")).strip(),
            "tool": str(item.get("tool", "")).strip() or "fal.ai",
            "purpose": str(item.get("purpose", "")).strip() or "External creative generation",
            "prompt": str(item.get("prompt", "")).strip(),
            "negative_prompt": str(item.get("negative_prompt", "")).strip(),
            "aspect_ratio": str(item.get("aspect_ratio", "")).strip() or "4:5",
            "duration": str(item.get("duration", "")).strip(),
            "reference_assets": item.get("reference_assets", []),
            "status": str(item.get("status", "")).strip() or "Prompt Draft",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    _save_list(EXTERNAL_PROMPTS_PATH, items)
    return items


def create_external_prompt_for_calendar_item(item: dict, tool: str = "fal.ai") -> dict:
    assets = _calendar_asset_names(item)
    phase = item.get("launch_phase") or item.get("launch_role") or "Brand sequence"
    hook = item.get("hook") or "Untitled Brand Name post"
    format_name = item.get("format") or "Carousel"
    opinion = item.get("strategic_opinion") or {}
    purpose = f"{format_name} support for {phase}"
    asset_text = ", ".join(assets[:8]) if assets else "available Brand Name Design raw assets"
    prompt = "\n".join(
        [
            "Create a premium visual asset for Brand Name Design, an art-translation streetwear brand.",
            f"Post hook: {hook}.",
            f"Strategic job: {opinion.get('job') or 'Make the transformation from physical painting to wearable fragment feel tangible.'}",
            f"Launch phase: {phase}.",
            f"Use these references as soft inspiration, not strict replication: {asset_text}.",
            "Visual language: physical oil painting evidence, digital reconstruction, wearable fragment, quiet studio archive, minimal premium tension.",
            "Composition should feel intentional, mysterious, and editorial, with realistic material detail and space for sparse overlay text.",
            "Avoid generic fashion ecommerce, loud hype styling, smiling catalogue energy, fake logos, malformed garments, unreadable typography, and over-polished AI gloss.",
        ]
    )
    return {
        "post_id": str(item.get("id", "")).strip(),
        "tool": tool or "fal.ai",
        "purpose": purpose,
        "prompt": prompt,
        "negative_prompt": "generic clothing store, fast fashion catalogue, glossy stock photo, fake brand marks, distorted garment, unreadable text, crowded layout",
        "aspect_ratio": "4:5",
        "duration": "5s" if "reel" in format_name.lower() or "video" in format_name.lower() else "",
        "reference_assets": assets,
        "status": "Prompt Draft",
    }


def reconcile_instagram_posts(calendar_items: list[dict], apply: bool = False) -> dict:
    posts = load_instagram_posts()
    matches: list[dict] = []
    used_item_ids: set[str] = set()
    updated_items = [dict(item) for item in calendar_items]
    by_id = {item.get("id", ""): item for item in updated_items}
    for post in posts:
        best = _best_calendar_match(post, updated_items, used_item_ids)
        if not best:
            continue
        item, score, reasons = best
        item_id = item.get("id", "")
        used_item_ids.add(item_id)
        match = {
            "post_key": _instagram_key(post),
            "post": post,
            "calendar_item_id": item_id,
            "calendar_hook": item.get("hook", ""),
            "score": score,
            "reasons": reasons,
            "status": "Measured" if _has_metrics(post) else "Posted",
        }
        matches.append(match)
        if apply and item_id in by_id:
            _apply_instagram_match(by_id[item_id], post, match)
    unmatched_posts = [
        post for post in posts
        if _instagram_key(post) not in {match["post_key"] for match in matches}
    ]
    return {
        "matches": matches,
        "unmatched_posts": unmatched_posts[:24],
        "matched_count": len(matches),
        "unmatched_count": len(unmatched_posts),
        "items": updated_items,
    }


def instagram_summary(posts: list[dict], calendar_items: list[dict]) -> dict:
    posted_count = len(posts)
    format_counts = Counter(post.get("format", "unknown") for post in posts)
    recent_hooks = [post.get("caption", "")[:120] for post in posts[:8] if post.get("caption")]
    posted_urls = {post.get("permalink", "") for post in posts if post.get("permalink")}
    matched = [item for item in calendar_items if item.get("post_url") in posted_urls or item.get("status") in {"Posted", "Measured", "Learned"}]
    return {
        "posted_count": posted_count,
        "matched_calendar_count": len(matched),
        "format_counts": dict(format_counts),
        "recent_hooks": recent_hooks,
        "posts": posts[:60],
        "import_template": "posted_date,permalink,caption,format,likes,comments,saves,reach,assets,notes",
    }


def asset_usage_summary(calendar_items: list[dict], posts: list[dict], raw_assets: list[dict]) -> dict:
    usage = Counter()
    for item in calendar_items:
        for name in item.get("selected_assets") or item.get("source_files") or []:
            if name:
                usage[name] += 1
    for post in posts:
        for name in post.get("assets", []):
            if name:
                usage[name] += 1
    raw_by_name = {asset.get("name", ""): asset for asset in raw_assets}
    most_used = [
        {
            "name": name,
            "count": count,
            "bucket": raw_by_name.get(name, {}).get("creativeBucket", ""),
        }
        for name, count in usage.most_common(24)
    ]
    unused = [
        {
            "name": asset.get("name", ""),
            "bucket": asset.get("creativeBucket", ""),
        }
        for asset in raw_assets
        if asset.get("name") and usage.get(asset.get("name", ""), 0) == 0
    ][:24]
    return {"most_used": most_used, "unused": unused, "tracked_asset_count": len(usage)}


def workflow_concept() -> list[dict]:
    return [
        {
            "lane": "Know",
            "description": "Instagram memory, timeline, performance journal, asset usage, and product truth.",
        },
        {
            "lane": "Plan",
            "description": "Calendar, feed grid, launch phases, SEO opportunities, and ad concepts.",
        },
        {
            "lane": "Build",
            "description": "Post builder, creative prompts, asset swaps, copy, and approval gates.",
        },
        {
            "lane": "Ship Manually",
            "description": "Manual Instagram posting, manual Shopify/SEO approval, manual ad launch.",
        },
        {
            "lane": "Learn",
            "description": "Posted content import, metrics, strategist notes, weekly review, and next actions.",
        },
    ]


def _normalize_instagram_post(post: dict) -> dict:
    assets = post.get("assets", [])
    if isinstance(assets, str):
        assets = [item.strip() for item in assets.split(",") if item.strip()]
    return {
        "posted_date": str(post.get("posted_date", "")).strip(),
        "permalink": str(post.get("permalink", "")).strip(),
        "caption": str(post.get("caption", "")).strip(),
        "format": str(post.get("format", "")).strip() or "Post",
        "likes": _int(post.get("likes")),
        "comments": _int(post.get("comments")),
        "saves": _int(post.get("saves")),
        "reach": _int(post.get("reach")),
        "notes": str(post.get("notes", "")).strip(),
        "assets": assets,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _instagram_key(post: dict) -> str:
    return post.get("permalink") or "|".join([post.get("posted_date", ""), post.get("caption", "")[:80]])


def _best_calendar_match(post: dict, calendar_items: list[dict], used_item_ids: set[str]) -> tuple[dict, int, list[str]] | None:
    scored = []
    for item in calendar_items:
        item_id = item.get("id", "")
        if not item_id or item_id in used_item_ids:
            continue
        score, reasons = _instagram_match_score(post, item)
        if score >= 45:
            scored.append((score, item, reasons))
    if not scored:
        return None
    score, item, reasons = sorted(scored, key=lambda entry: entry[0], reverse=True)[0]
    return item, min(score, 100), reasons


def _instagram_match_score(post: dict, item: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if post.get("permalink") and item.get("post_url") == post.get("permalink"):
        score += 70
        reasons.append("same permalink")
    if _date_distance_days(post.get("posted_date", ""), item.get("scheduled_date", "")) <= 2:
        score += 28
        reasons.append("date within two days")
    caption_tokens = _tokens(post.get("caption", ""))
    item_text = " ".join(
        [
            str(item.get("hook", "")),
            str(item.get("caption", "")),
            str(item.get("pillar", "")),
            str(item.get("launch_role", "")),
        ]
    )
    item_tokens = _tokens(item_text)
    if caption_tokens and item_tokens:
        overlap = len(caption_tokens & item_tokens)
        ratio = overlap / max(1, len(item_tokens))
        if overlap >= 3:
            added = min(32, 12 + int(ratio * 40))
            score += added
            reasons.append(f"{overlap} shared caption terms")
    hook = str(item.get("hook", "")).strip().lower()
    caption = str(post.get("caption", "")).strip().lower()
    if hook and (hook in caption or caption[:80] in hook):
        score += 25
        reasons.append("hook/caption phrase match")
    if str(post.get("format", "")).lower() and str(post.get("format", "")).lower() in str(item.get("format", "")).lower():
        score += 10
        reasons.append("same format")
    return score, reasons


def _apply_instagram_match(item: dict, post: dict, match: dict) -> None:
    item["status"] = match["status"]
    item["post_url"] = post.get("permalink", "")
    item["posted_date"] = post.get("posted_date", "")
    item["instagram_caption"] = post.get("caption", "")
    item["instagram_format"] = post.get("format", "")
    item["instagram_metrics"] = {
        "likes": post.get("likes", 0),
        "comments": post.get("comments", 0),
        "saves": post.get("saves", 0),
        "reach": post.get("reach", 0),
    }
    item["instagram_match_confidence"] = match["score"]
    item["instagram_match_reasons"] = match["reasons"]
    item["calendar_note"] = "Matched to imported Instagram memory. Review the match before treating performance as final."


def _has_metrics(post: dict) -> bool:
    return any(int(post.get(key, 0) or 0) > 0 for key in ["likes", "comments", "saves", "reach"])


def _date_distance_days(left: str, right: str) -> int:
    try:
        left_date = datetime.fromisoformat(str(left)[:10]).date()
        right_date = datetime.fromisoformat(str(right)[:10]).date()
    except ValueError:
        return 999
    return abs((left_date - right_date).days)


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "your", "post", "brand", "name", "design"}
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.lower()) if token not in stop}


def _calendar_asset_names(item: dict) -> list[str]:
    names = []
    for source in [item.get("selected_assets"), item.get("source_files")]:
        if isinstance(source, list):
            names.extend(str(name) for name in source if name)
    for slot in item.get("visual_slots") or []:
        if slot.get("asset_name"):
            names.append(str(slot["asset_name"]))
    return list(dict.fromkeys(names))


def _int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_list(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")
