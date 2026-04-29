import json
from datetime import datetime
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .settings import OUTPUTS_DIR, ROOT_DIR


CANVAS = (1080, 1350)
BACKGROUND = (244, 242, 237)
INK = (22, 22, 20)
MUTED = (102, 98, 90)
ACCENT = (126, 34, 38)


def extract_json_plan(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]

    return json.loads(text)


def render_carousel(plan: dict, asset_paths: list[Path]) -> list[Path]:
    stamp = datetime.now().strftime("%Y-%m-%d")
    title = _slug(plan.get("title", "visual-carousel"))
    output_dir = OUTPUTS_DIR / "visual_content" / f"{stamp}-{title}"
    output_dir.mkdir(parents=True, exist_ok=True)

    slides = plan.get("slides", [])[:7]
    if not slides:
        slides = [{"slide": 1, "headline": plan.get("title", "Archive fragment"), "subhead": "", "layout": "cover"}]

    rendered: list[Path] = []
    for index, slide in enumerate(slides):
        image = _render_slide(slide, index, len(slides), asset_paths)
        path = output_dir / f"slide-{index + 1:02}.png"
        image.save(path, "PNG")
        rendered.append(path)

    brief_path = output_dir / "design-brief.json"
    brief_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return rendered


def _render_slide(slide: dict, index: int, total: int, asset_paths: list[Path]) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    font_title = _font(76)
    font_sub = _font(38)
    font_meta = _font(24)

    draw.rectangle((0, 0, CANVAS[0], 12), fill=ACCENT)
    draw.text((72, 58), f"{index + 1:02}/{total:02}", font=font_meta, fill=MUTED)
    draw.text((72, 118), "BRAND NAME DESIGN", font=font_meta, fill=INK)

    asset = _load_asset(asset_paths[index % len(asset_paths)]) if asset_paths else _fallback_texture(index)
    layout = slide.get("layout", "cover")

    if layout in {"split", "product"}:
        asset_box = (72, 300, 1008, 880)
        text_top = 940
    else:
        asset_box = (72, 270, 1008, 980)
        text_top = 1040

    canvas.paste(_fit_image(asset, asset_box), asset_box[:2])

    headline = str(slide.get("headline", "Reconstructed fragment")).strip()
    subhead = str(slide.get("subhead", "")).strip()

    y = text_top
    for line in _lines(headline.upper(), 15):
        draw.text((72, y), line, font=font_title, fill=INK)
        y += 86

    y += 12
    for line in _lines(subhead, 34)[:3]:
        draw.text((76, y), line, font=font_sub, fill=MUTED)
        y += 48

    draw.text((72, 1264), "EXTRACTED / RECONSTRUCTED / ARCHIVE", font=font_meta, fill=MUTED)
    return canvas


def _load_asset(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _fit_image(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    width = box[2] - box[0]
    height = box[3] - box[1]
    fitted = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    overlay = Image.new("RGB", fitted.size, (0, 0, 0))
    return Image.blend(fitted, overlay, 0.08)


def _fallback_texture(index: int) -> Image.Image:
    image = Image.new("RGB", (936, 710), (218, 213, 202))
    draw = ImageDraw.Draw(image)
    for step in range(0, 1200, 38):
        color = ACCENT if step % 76 == 0 else (42, 42, 38)
        draw.line((step - 260, 710, step + 80, 0), fill=color, width=6)
    draw.rectangle((24, 24, 912, 686), outline=(28, 28, 25), width=2)
    draw.text((48, 608), f"RAW ASSET PLACEHOLDER {index + 1}", font=_font(28), fill=INK)
    return image


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        ROOT_DIR / "fonts" / "Inter.ttf",
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _lines(text: str, width: int) -> list[str]:
    return wrap(text, width=width) or [""]


def _slug(text: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else "-" for char in text).split("-"))[:80]
