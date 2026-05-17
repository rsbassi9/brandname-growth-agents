from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .settings import PRODUCT_INVENTORY_DIR, ROOT_DIR
from .visual_renderer import _slug


MANIFEST_PATH = PRODUCT_INVENTORY_DIR / "manifest.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def ensure_product_inventory_dir() -> None:
    PRODUCT_INVENTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_product_inventory() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_product_image(source_path: Path, original_name: str, notes: str = "", product_name: str = "") -> dict:
    ensure_product_inventory_dir()
    suffix = source_path.suffix.lower()
    safe_name = _slug(product_name or Path(original_name).stem or "product")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = PRODUCT_INVENTORY_DIR / f"{timestamp}-{safe_name}{suffix}"
    shutil.copy2(source_path, destination)

    item = {
        "filename": destination.name,
        "path": str(destination),
        "relative_path": str(destination.relative_to(ROOT_DIR)),
        "product_name": product_name.strip() or Path(original_name).stem,
        "notes": notes.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    manifest = load_product_inventory()
    manifest.append(item)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return item


def product_inventory_summary() -> str:
    items = load_product_inventory()
    drive_products = _drive_product_summary()
    if not items:
        return drive_products or (
            "No product image inventory has been uploaded yet. If creating image concepts, do not invent garments; "
            "ask for product inventory or use existing raw product/campaign assets only."
        )

    lines = [
        "Approved product image inventory:",
        "Only these uploaded product images may define garments/products in generated concepts.",
    ]
    for item in items:
        note = f" | notes: {item['notes']}" if item.get("notes") else ""
        lines.append(f"- {item['filename']} | product: {item.get('product_name', '')}{note}")
    if drive_products:
        lines.extend(["", drive_products])
    return "\n".join(lines)


def _drive_product_summary() -> str:
    try:
        from .drive_service import GoogleDriveService

        products = [
            item
            for item in GoogleDriveService().list_raw_assets()
            if item.get("creativeBucket") == "Store Products"
        ]
    except Exception:
        return ""

    if not products:
        return ""

    lines = [
        "Approved Drive product inventory:",
        "Use only these Store Products / Products folder files as garment/product references.",
    ]
    product_counts: dict[str, int] = {}
    for item in products:
        product_name = item.get("folderPath", "").split("/")[-1]
        if product_name:
            product_counts[product_name] = product_counts.get(product_name, 0) + 1

    for product_name, count in sorted(product_counts.items()):
        lines.append(f"- {product_name}: {count} product images")
    return "\n".join(lines)
