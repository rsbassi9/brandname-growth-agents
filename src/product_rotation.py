from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .drive_service import GoogleDriveService
from .settings import OUTPUTS_DIR, ROOT_DIR


CONTENT_PLAN_DIR = OUTPUTS_DIR / "content_plan"


def product_rotation_context(raw_assets: list[dict] | None = None) -> str:
    products = sorted(_product_universe(raw_assets))
    recent = recent_product_keys(raw_assets=raw_assets)
    unused = [product for product in products if product not in recent]
    lines = [
        "Product rotation rule:",
        "- Treat each Store Products subfolder as one product family.",
        "- Before reusing a recently featured product, try to give every other available product family a turn.",
        "- Reusing a product is allowed only when the concept clearly changes its role, format, styling, or story.",
        "- Never let the feed become visually dominated by one garment or colorway.",
    ]
    if products:
        lines.append(f"- Available product families: {', '.join(products)}")
    if recent:
        lines.append(f"- Recently used product families: {', '.join(recent)}")
    if unused:
        lines.append(f"- Prefer next if relevant: {', '.join(unused)}")
    return "\n".join(lines)


def prioritize_candidates_for_rotation(candidates: list[dict], raw_assets: list[dict] | None = None) -> list[dict]:
    products = _product_universe(raw_assets)
    if not products:
        return candidates

    recent = set(recent_product_keys(limit=max(len(products) - 1, 1), raw_assets=raw_assets))
    unused_products = products - recent
    if not unused_products:
        return candidates

    decorated = []
    for index, candidate in enumerate(candidates):
        product_keys = product_keys_for_names(candidate.get("source_files", []), raw_assets=raw_assets)
        repeats_recent_product = bool(product_keys & recent)
        uses_waiting_product = bool(product_keys & unused_products)
        penalty = 0
        if repeats_recent_product and not uses_waiting_product:
            penalty = 2
        elif repeats_recent_product:
            penalty = 1
        decorated.append((penalty, index, candidate))
    return [candidate for _, _, candidate in sorted(decorated, key=lambda item: (item[0], item[1]))]


def product_keys_for_names(names: Iterable[str], raw_assets: list[dict] | None = None) -> set[str]:
    assets = raw_assets if raw_assets is not None else _safe_raw_assets()
    by_name = {asset.get("name"): asset for asset in assets}
    keys = set()
    for name in names:
        asset = by_name.get(str(name))
        key = _product_key_for_asset(asset) if asset else _product_key_from_filename(str(name))
        if key:
            keys.add(key)
    return keys


def recent_product_keys(limit: int | None = None, raw_assets: list[dict] | None = None) -> list[str]:
    assets = raw_assets if raw_assets is not None else _safe_raw_assets()
    ordered: list[str] = []
    for plan in _recent_plans():
        posts = plan.get("posts", [])
        for post in sorted(posts, key=lambda item: item.get("feed_position", 999)):
            keys = post.get("product_keys") or list(product_keys_for_names(post.get("source_files", []), raw_assets=assets))
            for key in keys:
                if key and key not in ordered:
                    ordered.append(key)
                    if limit and len(ordered) >= limit:
                        return ordered
    return ordered


def product_rotation_note(product_keys: Iterable[str], raw_assets: list[dict] | None = None) -> str:
    keys = set(product_keys)
    if not keys:
        return ""
    products = _product_universe(raw_assets)
    recent = set(recent_product_keys(limit=max(len(products) - 1, 1), raw_assets=raw_assets))
    if keys & recent and products - recent:
        return "Uses a recently featured product. Prefer this only if the story, styling, or format is meaningfully different."
    return "Product family is clear for rotation tracking."


def _product_universe(raw_assets: list[dict] | None = None) -> set[str]:
    assets = raw_assets if raw_assets is not None else _safe_raw_assets()
    return {key for asset in assets if (key := _product_key_for_asset(asset))}


def _product_key_for_asset(asset: dict | None) -> str:
    if not asset or asset.get("creativeBucket") != "Store Products":
        return ""
    folder_path = str(asset.get("folderPath", "")).strip("/")
    if not folder_path:
        return ""
    return _clean_key(folder_path.split("/")[-1])


def _product_key_from_filename(name: str) -> str:
    stem = Path(name).stem
    product_signal = re.search(
        r"\b(mockups?|hoodie|t-?shirt|tee|tank|shorts|sweatshirt|sweatpant|pants|cap|hat|jacket)\b",
        stem,
        flags=re.I,
    )
    if not product_signal:
        return ""
    stem = re.sub(r"-?mockups?-?\d*.*$", "", stem, flags=re.I)
    stem = re.sub(r"\b(copy|final|front|back|detail)\b", "", stem, flags=re.I)
    return _clean_key(stem)


def _clean_key(value: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", value).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"(?<=\D)\d+$", "", cleaned).strip()
    return cleaned


def _recent_plans() -> list[dict]:
    if not CONTENT_PLAN_DIR.exists():
        return []
    plans = []
    for path in sorted(CONTENT_PLAN_DIR.glob("*-plan.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:12]:
        try:
            plans.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return plans


def _safe_raw_assets() -> list[dict]:
    try:
        return GoogleDriveService().list_raw_assets()
    except Exception:
        return []
