from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Iterable


def visual_fingerprint_for_names(names: Iterable[str], raw_assets: list[dict] | None = None) -> dict:
    assets = raw_assets or []
    by_name = {asset.get("name"): asset for asset in assets}
    fingerprints = [_asset_visual_traits(name, by_name.get(str(name))) for name in names if str(name).strip()]
    if not fingerprints:
        return {
            "visual_family": "unknown",
            "palette": "unknown",
            "brightness": "unknown",
            "density": "unknown",
            "subject": "unknown",
            "warnings": [],
        }

    return {
        "visual_family": _mode(trait["visual_family"] for trait in fingerprints),
        "palette": _mode(trait["palette"] for trait in fingerprints),
        "brightness": _mode(trait["brightness"] for trait in fingerprints),
        "density": _mode(trait["density"] for trait in fingerprints),
        "subject": _mode(trait["subject"] for trait in fingerprints),
        "product_visibility_score": _product_visibility_score(fingerprints),
        "content_weight": _content_weight(fingerprints),
        "warnings": _fingerprint_warnings(fingerprints),
    }


def grid_visual_warnings(items: list[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda item: item.get("feed_position", 999))
    warnings: list[dict] = []
    for row_index in range(0, len(ordered), 3):
        row = ordered[row_index : row_index + 3]
        if len(row) < 2:
            continue
        row_number = row_index // 3 + 1
        for field, label in [
            ("palette", "palette"),
            ("brightness", "brightness"),
            ("visual_family", "visual style"),
            ("density", "density"),
        ]:
            values = [item.get("visual_fingerprint", {}).get(field) for item in row]
            counts = Counter(value for value in values if value and value != "unknown")
            for value, count in counts.items():
                if count >= 2:
                    warnings.append(
                        {
                            "type": f"row_{field}_cluster",
                            "row": row_number,
                            "value": value,
                            "post_ids": [item.get("id") for item in row if item.get("visual_fingerprint", {}).get(field) == value],
                            "severity": "medium" if count == 2 else "high",
                            "suggested_action": "Move one of these posts to another row or swap in a contrasting asset.",
                            "note": f"Row {row_number} has {count} posts with similar {label}: {value}. Consider moving one to create breathing room.",
                        }
                    )

    for index, item in enumerate(ordered[:-1]):
        next_item = ordered[index + 1]
        score, similar_fields = visual_similarity_score(item, next_item)
        if score >= 3:
            warnings.append(
                {
                    "type": "neighbor_similarity",
                    "row": index // 3 + 1,
                    "value": ", ".join(similar_fields),
                    "post_ids": [item.get("id"), next_item.get("id")],
                    "severity": "high" if score >= 4 else "medium",
                    "similarity_score": score,
                    "suggested_action": "Separate these posts or replace one asset with a brighter/body/product/detail contrast.",
                    "note": f"Adjacent posts {index + 1} and {index + 2} read too similarly ({', '.join(similar_fields)}). Separate them if possible.",
                }
            )
    return warnings


def visual_similarity_score(first: dict, second: dict) -> tuple[int, list[str]]:
    first_fp = first.get("visual_fingerprint", {})
    second_fp = second.get("visual_fingerprint", {})
    fields = ("palette", "brightness", "visual_family", "density", "subject")
    similar = [
        field
        for field in fields
        if first_fp.get(field) == second_fp.get(field) and first_fp.get(field) not in {None, "", "unknown"}
    ]
    return len(similar), similar


def _asset_visual_traits(name: str, asset: dict | None) -> dict:
    text = " ".join(
        [
            Path(name).stem.lower(),
            str(asset.get("creativeBucket", "") if asset else "").lower(),
            str(asset.get("folderPath", "") if asset else "").lower(),
        ]
    )
    return {
        "visual_family": _visual_family(text),
        "palette": _palette(text),
        "brightness": _brightness(text),
        "density": _density(text),
        "subject": _subject(text),
    }


def _visual_family(text: str) -> str:
    if "photoshoot" in text or "campaign" in text or "shoot photos" in text or re.search(r"\bjrr\b", text):
        return "campaign photo"
    if "store products" in text or any(word in text for word in ("mockup", "hoodie", "shirt", "tee", "tank", "shorts")):
        return "product"
    if "process" in text or "studio" in text or "heic" in text or re.search(r"\bimg\b", text):
        return "process"
    if any(word in text for word in ("adrift", "4drft", "design", "painting", "pixelated")):
        return "digital/source"
    if ".mov" in text or "video" in text:
        return "motion"
    return "unknown"


def _palette(text: str) -> str:
    if any(word in text for word in ("black", "bw", "b&w", "dark", "charcoal")):
        return "black/dark"
    if any(word in text for word in ("white", "cream", "natural", "beige", "ivory")):
        return "light/neutral"
    if any(word in text for word in ("orange", "red", "rust", "sunset")):
        return "red/orange"
    if any(word in text for word in ("green", "olive", "sage", "khaki")):
        return "green/olive"
    if any(word in text for word in ("blue", "indigo", "navy")):
        return "blue"
    if any(word in text for word in ("grey", "gray", "mineral", "wash")):
        return "grey/washed"
    if any(word in text for word in ("adrift", "4drft", "design", "pixelated")):
        return "black/dark"
    return "unknown"


def _brightness(text: str) -> str:
    if _palette(text) == "black/dark":
        return "dark"
    if _palette(text) == "light/neutral":
        return "bright"
    if _palette(text) in {"grey/washed", "green/olive", "blue"}:
        return "mid"
    return "unknown"


def _density(text: str) -> str:
    if any(word in text for word in ("design", "pixelated", "painting", "4drft", "adrift")):
        return "dense"
    if any(word in text for word in ("mockup", "product", "tee", "tank", "hoodie")):
        return "minimal"
    if "process" in text or "studio" in text:
        return "medium"
    return "unknown"


def _subject(text: str) -> str:
    if "mockup" in text or "store products" in text:
        return "garment"
    if "photoshoot" in text or "campaign" in text or "jrr" in text:
        return "body"
    if "process" in text or "studio" in text:
        return "detail"
    if any(word in text for word in ("painting", "design", "adrift", "4drft")):
        return "source"
    return "unknown"


def _fingerprint_warnings(fingerprints: list[dict]) -> list[str]:
    warnings = []
    palettes = Counter(item["palette"] for item in fingerprints if item["palette"] != "unknown")
    if palettes and palettes.most_common(1)[0][1] >= 3:
        warnings.append(f"Post uses many assets with the same palette: {palettes.most_common(1)[0][0]}.")
    families = Counter(item["visual_family"] for item in fingerprints if item["visual_family"] != "unknown")
    if families and families.most_common(1)[0][1] >= 3:
        warnings.append(f"Post leans heavily on one visual family: {families.most_common(1)[0][0]}.")
    return warnings


def _product_visibility_score(fingerprints: list[dict]) -> int:
    score = 0
    for item in fingerprints:
        if item["subject"] == "garment":
            score += 2
        elif item["subject"] == "body":
            score += 2
        elif item["visual_family"] == "product":
            score += 1
    return min(score, 10)


def _content_weight(fingerprints: list[dict]) -> str:
    families = Counter(item["visual_family"] for item in fingerprints)
    if families.get("digital/source", 0) >= max(2, len(fingerprints) // 2):
        return "graphic-heavy"
    if families.get("campaign photo", 0) or families.get("product", 0):
        return "photo/product-heavy"
    if families.get("process", 0) >= max(2, len(fingerprints) // 2):
        return "process-heavy"
    return "mixed"


def _mode(values: Iterable[str]) -> str:
    counter = Counter(value for value in values if value)
    if not counter:
        return "unknown"
    return counter.most_common(1)[0][0]
