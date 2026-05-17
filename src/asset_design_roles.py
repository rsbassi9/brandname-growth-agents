from __future__ import annotations

from pathlib import Path


TEXT_BACKDROP_TERMS = (
    "fold",
    "folded",
    "mockup",
    "flat",
    "texture",
    "cloth",
    "canvas",
    "fabric",
    "detail",
    "hem",
    "label",
    "tag",
    "default",
)

DESIGN_SURFACE_TERMS = (
    "adrift",
    "painting",
    "canvas",
    "design",
    "background",
    "brush",
    "stroke",
    "oilpaint",
    "pixelated",
)

PRODUCT_HERO_TERMS = (
    "front",
    "back",
    "mockup",
    "product",
    "tee",
    "shirt",
    "tank",
    "hoodie",
    "shorts",
)


def enrich_asset_design_roles(item: dict) -> dict:
    name = item.get("name", "")
    stem = Path(name).stem.lower()
    folder = item.get("folderPath", "").lower().replace("\\", "/")
    bucket = item.get("creativeBucket", "")
    roles: set[str] = set()
    notes: list[str] = []
    score = 0

    if bucket == "Store Products":
        roles.add("hero_product")
        score += 2
        notes.append("store product reference")
        if any(term in stem for term in TEXT_BACKDROP_TERMS):
            roles.update({"text_backdrop", "texture_backdrop", "feed_breaker"})
            score += 5
            notes.append("product mockup/detail can become a quiet text or pacing surface")
        if any(term in stem for term in PRODUCT_HERO_TERMS):
            roles.add("product_clarity")
            score += 2

    if bucket in {"Design Assets", "Process / Studio"} or any(term in stem for term in DESIGN_SURFACE_TERMS):
        roles.update({"design_system", "process_proof"})
        score += 2
        if any(term in stem for term in DESIGN_SURFACE_TERMS):
            roles.update({"canvas_surface", "text_backdrop", "transition_slide"})
            score += 4
            notes.append("source/design surface can carry explanatory text")

    if bucket in {"Shoot Photos", "Photoshoot / Campaign"} or stem.startswith("jrr"):
        roles.update({"on_body", "campaign_anchor"})
        score += 3
        notes.append("body/campaign anchor")

    if bucket == "Video":
        roles.update({"motion", "reel_source"})
        score += 1

    if "products/" in folder and len(folder.split("/")) > 2:
        roles.add("same_product_folder_reference")
        score += 1

    if not roles:
        roles.add("supporting_asset")

    manual_roles = item.get("manualTag", {}).get("roles", "")
    for role in str(manual_roles).replace(",", ";").split(";"):
        role = role.strip()
        if role:
            roles.add(role)
            score += 3

    item["designRoles"] = sorted(roles)
    item["designSurfaceScore"] = score
    item["designUseNotes"] = "; ".join(notes) if notes else "supporting visual asset"
    return item


def asset_design_context(raw_assets: list[dict], limit: int = 18) -> str:
    enriched = [enrich_asset_design_roles(dict(asset)) for asset in raw_assets]
    surface_assets = sorted(
        [asset for asset in enriched if {"text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker"} & set(asset.get("designRoles", []))],
        key=lambda asset: (-int(asset.get("designSurfaceScore", 0)), asset.get("name", "").lower()),
    )[:limit]
    campaign_assets = sorted(
        [asset for asset in enriched if {"campaign_anchor", "on_body"} & set(asset.get("designRoles", []))],
        key=lambda asset: asset.get("name", "").lower(),
    )[:8]

    lines = [
        "Asset design role memory:",
        "- Treat some product/detail/source files as design surfaces, not only literal product references.",
        "- Use folded cloth, canvas, quiet mockups, hems, labels, and texture crops as text backdrops, feed breakers, or carousel transition slides.",
    ]
    if surface_assets:
        lines.append("- Strong text/backdrop/feed-breaker candidates:")
        for asset in surface_assets:
            lines.append(f"  - {asset.get('name')}: {', '.join(asset.get('designRoles', []))} ({asset.get('designUseNotes')})")
    if campaign_assets:
        lines.append("- Campaign/body anchors:")
        for asset in campaign_assets:
            lines.append(f"  - {asset.get('name')}: {', '.join(asset.get('designRoles', []))}")
    return "\n".join(lines)
