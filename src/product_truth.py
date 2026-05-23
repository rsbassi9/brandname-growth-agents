from __future__ import annotations

import json
import re
import csv
from pathlib import Path
from typing import Iterable

from .settings import MEMORY_DIR, ROOT_DIR


PRODUCT_TRUTH_PATH = MEMORY_DIR / "product_truth.json"
REFERENCE_ROLE_PATH = ROOT_DIR / "brand_context" / "product_reference_roles.csv"
REFERENCE_ROLES = {"front_design", "back_design", "blank_fit_model", "material_detail", "folded_surface", "texture_backdrop", "unknown"}


def load_product_truth() -> dict:
    if not PRODUCT_TRUTH_PATH.exists():
        return {"profiles": {}, "updated_at": ""}
    try:
        data = json.loads(PRODUCT_TRUTH_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"profiles": {}, "updated_at": ""}
    return data if isinstance(data, dict) else {"profiles": {}, "updated_at": ""}


def save_product_truth(data: dict) -> None:
    PRODUCT_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRODUCT_TRUTH_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_product_truth(raw_assets: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {}
    for asset in raw_assets:
        if asset.get("creativeBucket") != "Store Products":
            continue
        key = product_key_from_asset(asset)
        if not key:
            continue
        groups.setdefault(key, []).append(asset)

    profiles = {}
    for key, assets in sorted(groups.items()):
        profiles[key] = profile_for_product(key, assets)
    return {"profiles": profiles}


def product_key_from_asset(asset: dict | None) -> str:
    if not asset:
        return ""
    folder = str(asset.get("folderPath", "")).replace("\\", "/")
    parts = [part for part in folder.split("/") if part]
    if "Products" in parts:
        index = parts.index("Products")
        if len(parts) > index + 1:
            return normalize_product_key(parts[index + 1])
    return ""


def normalize_product_key(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", str(value).lower())).strip()
    return re.sub(r"(?<=\D)\d+$", "", cleaned).strip()


def profile_for_product(key: str, assets: list[dict]) -> dict:
    overrides = load_reference_role_overrides()
    sorted_assets = sorted(assets, key=lambda asset: _reference_rank(asset.get("name", "")))
    role_map = {asset.get("name", ""): _reference_role(asset, key, overrides) for asset in sorted_assets if asset.get("name")}
    reference_files = {
        "front": _file_names(sorted_assets, "front", role_map),
        "back": _file_names(sorted_assets, "back", role_map),
        "detail": _file_names(sorted_assets, "detail", role_map),
        "folded_texture": _file_names(sorted_assets, "folded_texture", role_map),
        "hero": [asset.get("name", "") for asset in sorted_assets[:6] if asset.get("name")],
    }
    role_files = {role: [name for name, mapped_role in role_map.items() if mapped_role == role] for role in sorted(REFERENCE_ROLES)}
    garment_type = _garment_type(key)
    placement = _placement_requirements(key, reference_files, role_files)
    return {
        "product_key": key,
        "display_name": titleize(key),
        "garment_type": garment_type,
        "reference_files": reference_files,
        "reference_roles": role_files,
        "reference_role_notes": _reference_role_notes(role_files),
        "front_graphic_policy": _graphic_policy(role_files, "front"),
        "back_graphic_policy": _graphic_policy(role_files, "back"),
        "preferred_generation_refs": {
            "design_sources": role_files.get("front_design", [])[:4] + role_files.get("back_design", [])[:2],
            "fit_sources": role_files.get("blank_fit_model", [])[:4],
            "material_sources": (role_files.get("material_detail", []) + role_files.get("folded_surface", []) + role_files.get("texture_backdrop", []))[:6],
        },
        "front_requirements": placement["front"],
        "back_requirements": placement["back"],
        "detail_requirements": placement["detail"],
        "silhouette": _silhouette(key, garment_type),
        "fabric_wash": _fabric_wash(key),
        "must_never_omit": placement["must_never_omit"],
        "must_not_invent": [
            "readable fake text",
            "new brand names",
            "new garment graphics not shown in the product folder",
            "moving back graphics onto the front",
            "removing visible front marks/logos when front references show them",
        ],
    }


def product_truth_for_keys(keys: Iterable[str], truth: dict | None = None) -> list[dict]:
    data = truth or load_product_truth()
    profiles = data.get("profiles", {})
    found = []
    for key in keys:
        normalized = normalize_product_key(key)
        profile = profiles.get(normalized)
        if profile:
            found.append(profile)
    return found


def product_truth_requirements(keys: Iterable[str], truth: dict | None = None) -> str:
    profiles = product_truth_for_keys(keys, truth)
    if not profiles:
        return "No product truth profile found. Use selected source files conservatively and do not invent branding or garment graphics."
    lines = []
    for profile in profiles:
        lines.extend(
            [
                f"Product: {profile.get('display_name')}",
                f"Garment type: {profile.get('garment_type')}",
                f"Silhouette: {profile.get('silhouette')}",
                f"Fabric/wash: {profile.get('fabric_wash')}",
                f"Front graphic policy: {profile.get('front_graphic_policy', '')}",
                f"Back graphic policy: {profile.get('back_graphic_policy', '')}",
                f"Design sources: {', '.join(profile.get('preferred_generation_refs', {}).get('design_sources', [])[:6])}",
                f"Fit/model sources: {', '.join(profile.get('preferred_generation_refs', {}).get('fit_sources', [])[:6])}",
                f"Material/detail sources: {', '.join(profile.get('preferred_generation_refs', {}).get('material_sources', [])[:6])}",
                "Use blank_fit_model references only for pose, fit, silhouette, drape, crop, neckline, sleeve shape, and fabric behavior. Do not treat blank model shots as the final product design.",
                "Use front_design/back_design references as the source of truth for actual sellable product graphics, logos, artwork, and placement.",
                f"Front requirements: {'; '.join(profile.get('front_requirements', []))}",
                f"Back requirements: {'; '.join(profile.get('back_requirements', []))}",
                f"Detail requirements: {'; '.join(profile.get('detail_requirements', []))}",
                f"Must never omit: {'; '.join(profile.get('must_never_omit', []))}",
                f"Must not invent: {'; '.join(profile.get('must_not_invent', []))}",
                f"Front refs: {', '.join(profile.get('reference_files', {}).get('front', [])[:4])}",
                f"Back refs: {', '.join(profile.get('reference_files', {}).get('back', [])[:4])}",
                f"Detail refs: {', '.join(profile.get('reference_files', {}).get('detail', [])[:4])}",
            ]
        )
    return "\n".join(lines)


def titleize(value: str) -> str:
    return re.sub(r"[-_]+", " ", value).strip().title()


def load_reference_role_overrides() -> dict[tuple[str, str], str]:
    if not REFERENCE_ROLE_PATH.exists():
        return {}
    overrides: dict[tuple[str, str], str] = {}
    try:
        with REFERENCE_ROLE_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                product_key = normalize_product_key(row.get("product_key", ""))
                file_name = str(row.get("file_name", "")).strip()
                role = str(row.get("role", "")).strip().lower()
                if product_key and file_name and role in REFERENCE_ROLES:
                    overrides[(product_key, file_name.lower())] = role
    except OSError:
        return {}
    return overrides


def _file_names(assets: list[dict], role: str, role_map: dict[str, str]) -> list[str]:
    aliases = {
        "front": {"front_design"},
        "back": {"back_design"},
        "detail": {"material_detail"},
        "folded_texture": {"folded_surface", "texture_backdrop"},
    }.get(role, {role})
    names = [asset.get("name", "") for asset in assets if role_map.get(asset.get("name", "")) in aliases and asset.get("name")]
    if role == "detail":
        names.extend(asset.get("name", "") for asset in assets if role_map.get(asset.get("name", "")) == "unknown" and asset.get("name"))
    return list(dict.fromkeys(names))[:8]


def _reference_role(asset: dict, product_key: str, overrides: dict[tuple[str, str], str]) -> str:
    name = asset.get("name", "")
    override = overrides.get((normalize_product_key(product_key), name.lower()))
    if override:
        return override
    return _asset_role(name)


def _asset_role(name: str) -> str:
    lower = name.lower()
    if any(term in lower for term in ("fold", "flat", "texture", "fabric", "hem", "tag", "close", "detail")):
        return "folded_surface" if any(term in lower for term in ("fold", "texture", "fabric")) else "material_detail"
    number = _mockup_number(name)
    if number == 1 or "front design" in lower or "front_graphic" in lower:
        return "front_design"
    if number == 2 or "back design" in lower or "back_graphic" in lower:
        return "back_design"
    if number in {3, 4, 5}:
        return "material_detail"
    if number in {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17}:
        return "blank_fit_model"
    if "front" in lower:
        return "front_design"
    if "back" in lower:
        return "back_design"
    if any(term in lower for term in ("mockups-3", "mockups-4", "mockups-5")):
        return "material_detail"
    return "unknown"


def _reference_rank(name: str) -> tuple[int, int, str]:
    role_order = {"front_design": 0, "back_design": 1, "blank_fit_model": 2, "material_detail": 3, "folded_surface": 4, "texture_backdrop": 5, "unknown": 6}
    return (role_order.get(_asset_role(name), 9), _mockup_number(name), name.lower())


def _mockup_number(name: str) -> int:
    match = re.search(r"mockups-(\d+)", name.lower())
    return int(match.group(1)) if match else 999


def _garment_type(key: str) -> str:
    lower = key.lower()
    if "hoodie" in lower:
        return "hoodie"
    if "short" in lower:
        return "shorts"
    if "tank" in lower:
        return "tank top"
    if "t shirt" in lower or "tee" in lower:
        return "t-shirt"
    return "garment"


def _silhouette(key: str, garment_type: str) -> str:
    lower = key.lower()
    descriptors = []
    if "boxy" in lower:
        descriptors.append("boxy fit")
    if "wide neck" in lower:
        descriptors.append("wide neck")
    if "bodycon" in lower:
        descriptors.append("close body fit")
    if "drop shoulder" in lower:
        descriptors.append("drop shoulder")
    if "frayed" in lower:
        descriptors.append("frayed hem")
    if "grommet" in lower or "eyelet" in lower:
        descriptors.append("grommet/eyelet detail")
    return ", ".join([garment_type, *descriptors])


def _fabric_wash(key: str) -> str:
    lower = key.lower()
    if "mineral wash" in lower:
        return "mineral wash"
    if "vintage washed" in lower or "vintage wash" in lower:
        return "vintage wash"
    if "french terry" in lower:
        return "french terry"
    if "waffle" in lower:
        return "waffle knit"
    if "heavyweight" in lower:
        return "heavyweight cotton"
    return "match product references"


def _placement_requirements(key: str, reference_files: dict, role_files: dict) -> dict:
    front = [
        "For front-facing renders, use front_design references as the source of truth for actual sellable product artwork, logo, graphic placement, and product color.",
        "Use blank_fit_model references only for fit/silhouette/material behavior. Do not let blank model shots erase actual product artwork.",
    ]
    back = [
        "For back-facing renders, use back_design references as the source of truth for actual sellable product artwork and placement.",
        "Do not move back artwork onto the front of the garment.",
    ]
    detail = [
        "Preserve visible trims, tags, hems, grommets, neck shape, sleeve/arm opening, fabric texture, and wash.",
    ]
    must_never_omit = [
        "side-specific branding/graphic placement",
        "garment silhouette",
        "fabric color/wash",
    ]
    lower = key.lower()
    if "grommet" in lower or "eyelet" in lower:
        must_never_omit.append("grommet/eyelet detail")
    if "frayed" in lower:
        must_never_omit.append("frayed hem")
    return {"front": front, "back": back, "detail": detail, "must_never_omit": must_never_omit}


def _graphic_policy(role_files: dict, side: str) -> str:
    if side == "front":
        return "use_front_design" if role_files.get("front_design") else "fit_reference_only_no_invented_front_graphic"
    return "use_back_design" if role_files.get("back_design") else "fit_reference_only_no_invented_back_graphic"


def _reference_role_notes(role_files: dict) -> list[str]:
    notes = []
    if role_files.get("front_design") or role_files.get("back_design"):
        notes.append("Designed product references define the final sellable graphics/logos/artwork.")
    if role_files.get("blank_fit_model"):
        notes.append("Blank model references define fit, drape, crop, neckline, sleeves, and material behavior only.")
    if role_files.get("material_detail") or role_files.get("folded_surface") or role_files.get("texture_backdrop"):
        notes.append("Detail and surface references define texture, construction, hems, fabric weight, and feed backdrops.")
    if role_files.get("unknown"):
        notes.append("Unknown references may need manual tagging in brand_context/product_reference_roles.csv.")
    return notes
