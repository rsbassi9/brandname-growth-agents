from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from PIL import Image, ImageStat

from .settings import MEMORY_DIR, OUTPUTS_DIR


VISUAL_METADATA_PATH = MEMORY_DIR / "visual_metadata.json"


def load_visual_metadata() -> dict[str, dict]:
    if not VISUAL_METADATA_PATH.exists():
        return {}
    try:
        data = json.loads(VISUAL_METADATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_visual_metadata(metadata: dict[str, dict]) -> None:
    VISUAL_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    VISUAL_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def metadata_for_output(path: str | Path) -> dict:
    resolved = Path(path)
    if not resolved.exists() or resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return {}
    key = str(resolved)
    metadata = load_visual_metadata()
    cached = metadata.get(key)
    mtime = resolved.stat().st_mtime
    if cached and cached.get("mtime") == mtime:
        return cached
    analyzed = analyze_image(resolved)
    analyzed["mtime"] = mtime
    metadata[key] = analyzed
    save_visual_metadata(metadata)
    return analyzed


def warm_output_visual_metadata(limit: int = 200) -> dict[str, dict]:
    metadata = load_visual_metadata()
    if not OUTPUTS_DIR.exists():
        return metadata
    paths = sorted(
        [path for path in OUTPUTS_DIR.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )[:limit]
    changed = False
    for path in paths:
        key = str(path)
        mtime = path.stat().st_mtime
        if metadata.get(key, {}).get("mtime") == mtime:
            continue
        analyzed = analyze_image(path)
        analyzed["mtime"] = mtime
        metadata[key] = analyzed
        changed = True
    if changed:
        save_visual_metadata(metadata)
    return metadata


def analyze_image(path: Path) -> dict:
    with Image.open(path) as image:
        image = image.convert("RGB")
        thumbnail = image.copy()
        thumbnail.thumbnail((96, 96))
        stat = ImageStat.Stat(thumbnail)
        avg = tuple(int(value) for value in stat.mean[:3])
        brightness_value = sum(avg) / 3
        extrema = stat.extrema
        contrast_value = mean((high - low for low, high in extrema))
        palette = _palette(avg)
        brightness = _brightness(brightness_value)
        density = _density(contrast_value)
        image_type = _image_type(palette, density, brightness)
        return {
            "dominant_rgb": avg,
            "palette": palette,
            "brightness": brightness,
            "brightness_value": round(brightness_value, 2),
            "contrast_value": round(contrast_value, 2),
            "density": density,
            "image_type": image_type,
        }


def _palette(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    brightness = sum(rgb) / 3
    if brightness < 70:
        return "black/dark"
    if brightness > 205:
        return "light/neutral"
    if red > green + 25 and red > blue + 25:
        return "red/orange"
    if green > red + 15 and green > blue + 10:
        return "green/olive"
    if blue > red + 20 and blue > green + 15:
        return "blue"
    if abs(red - green) < 18 and abs(green - blue) < 18:
        return "grey/washed"
    return "mixed"


def _brightness(value: float) -> str:
    if value < 85:
        return "dark"
    if value > 185:
        return "bright"
    return "mid"


def _density(contrast: float) -> str:
    if contrast > 175:
        return "dense"
    if contrast < 75:
        return "minimal"
    return "medium"


def _image_type(palette: str, density: str, brightness: str) -> str:
    if density == "dense" and palette in {"black/dark", "mixed", "red/orange"}:
        return "graphic-heavy"
    if density == "minimal" and brightness in {"bright", "mid"}:
        return "photo/product-light"
    if palette == "black/dark":
        return "dark-anchor"
    return "photo/mixed"
