import json
from datetime import datetime
from pathlib import Path
from textwrap import wrap
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .settings import MEMORY_DIR, OUTPUTS_DIR, ROOT_DIR


CANVAS = (1080, 1350)
BACKGROUND = (244, 242, 237)
INK = (22, 22, 20)
MUTED = (102, 98, 90)
ACCENT = (126, 34, 38)
TEXT_EDIT_LOG_PATH = MEMORY_DIR / "text_slide_edits.jsonl"

FONT_PATHS = {
    "brand": [
        ROOT_DIR / "fonts" / "SpecialElite-Regular.ttf",
        ROOT_DIR / "fonts" / "SpecialElite-Regular.otf",
        Path("C:/Windows/Fonts/SpecialElite-Regular.ttf"),
    ],
    "display": [
        ROOT_DIR / "fonts" / "SpaceGrotesk-Bold.ttf",
        ROOT_DIR / "fonts" / "SpaceGrotesk-Regular.ttf",
        ROOT_DIR / "fonts" / "SpaceGrotesk-VariableFont_wght.ttf",
    ],
    "mono": [
        ROOT_DIR / "fonts" / "JetBrainsMono-Regular.ttf",
        ROOT_DIR / "fonts" / "JetBrainsMono-Bold.ttf",
        Path("C:/Windows/Fonts/consola.ttf"),
    ],
    "fallback": [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        ROOT_DIR / "fonts" / "Inter.ttf",
    ],
}


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


def render_text_carousel(folder_name: str, slides: list[dict]) -> list[Path]:
    stamp = datetime.now().strftime("%Y-%m-%d")
    output_dir = OUTPUTS_DIR / "visual_content" / f"{stamp}-{_slug(folder_name)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    slides = normalize_text_slides(slides)
    rendered: list[Path] = []
    for index, slide in enumerate(slides):
        image = _render_text_slide(slide, index, len(slides))
        path = output_dir / f"slide-{index + 1:02}.png"
        image.save(path, "PNG")
        rendered.append(path)

    (output_dir / "design-brief.json").write_text(json.dumps({"slides": slides}, indent=2), encoding="utf-8")
    return rendered


def normalize_text_slides(slides: list[dict]) -> list[dict]:
    normalized = []
    for slide in slides:
        if slide.get("blocks"):
            normalized.append(slide)
            continue
        palette = slide.get("palette", "dark")
        normalized.append(
            {
                "palette": palette,
                "footer": slide.get("footer", "CANVAS / CAPTURE / RECONSTRUCT / DROP"),
                "blocks": [
                    {
                        "id": "meta",
                        "text": slide.get("eyebrow", ""),
                        "role": "mono",
                        "x": 72,
                        "y": 302,
                        "size": 34,
                        "color": "accent",
                        "uppercase": True,
                        "wrap": 28,
                    },
                    {
                        "id": "headline",
                        "text": slide.get("headline", ""),
                        "role": "display",
                        "x": 72,
                        "y": 390,
                        "size": 92 if len(str(slide.get("headline", ""))) <= 26 else 68,
                        "color": "ink",
                        "uppercase": True,
                        "wrap": 13 if len(str(slide.get("headline", ""))) <= 26 else 17,
                    },
                    {
                        "id": "body",
                        "text": slide.get("body", ""),
                        "role": "brand",
                        "x": 76,
                        "y": 700,
                        "size": 36,
                        "color": "muted",
                        "wrap": 34,
                    },
                ],
            }
        )
    return normalized


def log_text_slide_edit(post_id: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    TEXT_EDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "post_id": post_id,
        "before": before,
        "after": after,
    }
    with TEXT_EDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def text_slide_edit_context(limit: int = 12) -> str:
    if not TEXT_EDIT_LOG_PATH.exists():
        return "No human text-slide edits have been logged yet."
    events: list[dict[str, Any]] = []
    for line in TEXT_EDIT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        return "No human text-slide edits have been logged yet."

    lines = ["Human text-slide edit memory:"]
    for event in events[-limit:]:
        post_id = event.get("post_id", "unknown-post")
        before_slides = event.get("before", {}).get("slides", [])
        after_slides = event.get("after", {}).get("slides", [])
        changes: list[str] = []
        for slide_index, after_slide in enumerate(after_slides):
            before_blocks = {
                block.get("id", str(index)): block
                for index, block in enumerate((before_slides[slide_index] if slide_index < len(before_slides) else {}).get("blocks", []))
            }
            for block_index, after_block in enumerate(after_slide.get("blocks", [])):
                block_id = after_block.get("id", str(block_index))
                before_block = before_blocks.get(block_id, {})
                changed_fields = [
                    field
                    for field in ("text", "role", "x", "y", "size", "wrap", "color")
                    if before_block.get(field) != after_block.get(field)
                ]
                if changed_fields:
                    changes.append(f"slide {slide_index + 1} {block_id}: {', '.join(changed_fields)}")
        if changes:
            lines.append(f"- {post_id}: {'; '.join(changes[:4])}")
    if len(lines) == 1:
        lines.append("- Edits logged, but no block-level differences were detected.")
    return "\n".join(lines)


def font_status() -> dict[str, Any]:
    status = {}
    for role in ("brand", "display", "mono"):
        found = next((str(path) for path in FONT_PATHS[role] if path.exists()), "")
        status[role] = {"found": bool(found), "path": found}
    return status


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


def _render_text_slide(slide: dict, index: int, total: int) -> Image.Image:
    palette = slide.get("palette", "dark")
    if palette == "light":
        bg, ink, muted, accent = BACKGROUND, INK, MUTED, ACCENT
    else:
        bg, ink, muted, accent = (8, 9, 10), (245, 242, 234), (156, 150, 140), (184, 54, 58)

    canvas = Image.new("RGB", CANVAS, bg)
    draw = ImageDraw.Draw(canvas)
    font_meta = _font(26, "mono")

    draw.rectangle((0, 0, CANVAS[0], 14), fill=accent)
    draw.text((72, 64), f"{index + 1:02}/{total:02}", font=font_meta, fill=muted)
    draw.text((72, 116), "[BRAND NAME.] / [4DRFT]", font=font_meta, fill=ink)
    colors = {"ink": ink, "muted": muted, "accent": accent, "bg": bg}
    for block in slide.get("blocks", []):
        text = str(block.get("text", ""))
        if block.get("uppercase"):
            text = text.upper()
        font = _font(int(block.get("size", 34)), block.get("role", "display"))
        color = colors.get(block.get("color", "ink"), ink)
        line_height = int(block.get("line_height", int(block.get("size", 34)) * 1.12))
        y = int(block.get("y", 0))
        for line in _lines(text, int(block.get("wrap", 24)))[: int(block.get("max_lines", 8))]:
            draw.text((int(block.get("x", 72)), y), line, font=font, fill=color)
            y += line_height

    draw.line((72, 1168, 1008, 1168), fill=accent, width=3)
    footer = str(slide.get("footer", "CANVAS / CAPTURE / RECONSTRUCT / DROP")).strip().upper()
    draw.text((72, 1228), footer, font=font_meta, fill=muted)
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


def _font(size: int, role: str = "fallback") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [*FONT_PATHS.get(role, []), *FONT_PATHS["fallback"]]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _lines(text: str, width: int) -> list[str]:
    return wrap(text, width=width) or [""]


def _slug(text: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else "-" for char in text).split("-"))[:80]
