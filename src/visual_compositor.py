from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def composite_product_reference(
    base_image_path: str | Path,
    reference_paths: list[Path],
    concept_type: str = "model_shoot",
    product_truth: list[dict] | None = None,
) -> dict:
    """Create a conservative product-accuracy composite variant.

    This is intentionally a concepting aid, not a final retouching pipeline. It
    blends a crop from the strongest product reference into the likely garment
    area so small front/back branding has a concrete visual fallback when image
    generation omits it.
    """
    base_path = Path(base_image_path)
    if not base_path.exists() or not reference_paths:
        return {}

    reference = _best_reference(reference_paths, concept_type, product_truth or [])
    if not reference:
        return {}

    try:
        base = Image.open(base_path).convert("RGBA")
        patch = _reference_patch(reference)
    except Exception:
        return {}

    if patch.width < 8 or patch.height < 8:
        return {}

    target_box = _target_box(base.size, concept_type)
    overlay = _fit_patch(patch, target_box)
    composed = base.copy()
    composed.alpha_composite(overlay, dest=(target_box[0], target_box[1]))

    output_path = base_path.with_name(f"{base_path.stem}-product-composite.png")
    composed.convert("RGB").save(output_path, "PNG")
    return {
        "image_path": str(output_path),
        "reference_path": str(reference),
        "method": "reference_patch_perspective_blend",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "note": "Concept composite only. Use to judge placement/branding direction; verify against product references before publishing.",
    }


def _best_reference(reference_paths: list[Path], concept_type: str, product_truth: list[dict]) -> Path | None:
    existing = [Path(path) for path in reference_paths if Path(path).exists()]
    if not existing:
        return None
    preferred = _preferred_design_names(product_truth, concept_type)
    for name in preferred:
        match = next((path for path in existing if _loose_name_match(name, path.name)), None)
        if match:
            return match
    terms = ("front", "mockups-9", "mockups-7", "mockups-1") if "model" in concept_type else ("back", "mockups-8", "mockups-6", "mockups-2")

    def score(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        direct = 0 if any(term in name for term in terms) else 1
        detail = 0 if any(term in name for term in ("logo", "graphic", "detail", "mockup")) else 1
        return (direct, detail, name)

    return sorted(existing, key=score)[0]


def _preferred_design_names(product_truth: list[dict], concept_type: str) -> list[str]:
    names: list[str] = []
    for profile in product_truth:
        roles = profile.get("reference_roles", {})
        if "back" in concept_type:
            names.extend(roles.get("back_design", []))
        names.extend(roles.get("front_design", []))
        names.extend(profile.get("preferred_generation_refs", {}).get("design_sources", []))
    return list(dict.fromkeys(name for name in names if name))


def _loose_name_match(expected: str, actual: str) -> bool:
    def clean(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    return clean(expected) in clean(actual)


def _reference_patch(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    image = ImageOps.exif_transpose(image)
    width, height = image.size
    # Product mockups usually place the useful garment/graphic information in
    # the central torso area. This crop avoids bringing the full product-sheet
    # background into the generated photo.
    crop = image.crop((int(width * 0.22), int(height * 0.20), int(width * 0.78), int(height * 0.72)))
    crop = _mask_near_background(crop)
    return crop


def _mask_near_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    corners = [
        rgba.getpixel((0, 0))[:3],
        rgba.getpixel((width - 1, 0))[:3],
        rgba.getpixel((0, height - 1))[:3],
        rgba.getpixel((width - 1, height - 1))[:3],
    ]
    background = tuple(sum(color[index] for color in corners) // len(corners) for index in range(3))
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            distance = abs(red - background[0]) + abs(green - background[1]) + abs(blue - background[2])
            if distance < 42:
                pixels[x, y] = (red, green, blue, 0)
            else:
                pixels[x, y] = (red, green, blue, min(alpha, 188))
    return rgba.filter(ImageFilter.GaussianBlur(0.25))


def _target_box(size: tuple[int, int], concept_type: str) -> tuple[int, int, int, int]:
    width, height = size
    if "back" in concept_type:
        return (int(width * 0.33), int(height * 0.24), int(width * 0.67), int(height * 0.58))
    return (int(width * 0.40), int(height * 0.25), int(width * 0.60), int(height * 0.42))


def _fit_patch(patch: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    target_width = max(12, box[2] - box[0])
    target_height = max(12, box[3] - box[1])
    fitted = ImageOps.contain(patch, (target_width, target_height), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    x = (target_width - fitted.width) // 2
    y = (target_height - fitted.height) // 2
    fitted = ImageEnhance.Contrast(fitted).enhance(0.92)
    fitted = ImageEnhance.Color(fitted).enhance(0.88)
    canvas.alpha_composite(fitted, (x, y))
    return canvas
