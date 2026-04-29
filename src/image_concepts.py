from __future__ import annotations

import base64
from datetime import datetime
import json
from pathlib import Path

from openai import OpenAI, OpenAIError
from PIL import Image, ImageOps

from .settings import (
    IMAGE_CONCEPT_COUNT,
    IMAGE_CONCEPT_MODEL,
    IMAGE_CONCEPT_QUALITY,
    IMAGE_CONCEPT_SIZE,
    OUTPUTS_DIR,
    ROOT_DIR,
)
from .visual_renderer import _slug


def generate_image_concepts(plan: dict, asset_paths: list[Path]) -> dict[str, str]:
    concepts = plan.get("image_concepts", [])[:IMAGE_CONCEPT_COUNT]
    if not concepts:
        return {}

    stamp = datetime.now().strftime("%Y-%m-%d")
    title = _slug(plan.get("title", "image-concepts"))
    output_dir = OUTPUTS_DIR / "image_concepts" / f"{stamp}-{title}"
    output_dir.mkdir(parents=True, exist_ok=True)

    reference_paths = _prepare_references(asset_paths[:3])
    generated_paths: list[Path] = []
    briefs: list[dict] = []

    for index, concept in enumerate(concepts, start=1):
        prompt = _build_prompt(concept, plan)
        image_data = _generate_image(prompt, reference_paths)
        image_path = output_dir / f"concept-{index:02}-{_slug(concept.get('name', 'image'))}.png"
        image_path.write_bytes(base64.b64decode(image_data))
        generated_paths.append(image_path)
        briefs.append({**concept, "output_path": str(image_path), "final_prompt": prompt})

    brief_path = output_dir / "image-briefs.json"
    brief_path.write_text(json.dumps(briefs, indent=2), encoding="utf-8")

    markdown = [
        f"# Image Concepts: {plan.get('title', 'Visual Concepts')}",
        "",
        "Generated with OpenAI Images for review. Typography should be applied later by the renderer.",
        "",
    ]
    for item in briefs:
        markdown.extend(
            [
                f"## {item.get('name', 'Concept')}",
                f"Brief: {item.get('brief', '')}",
                f"Source asset hint: {item.get('source_asset_hint', '')}",
                f"Output: {item.get('output_path', '')}",
                "",
            ]
        )
    markdown_path = output_dir / "image-briefs.md"
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")

    return {
        "image_concept_brief": str(markdown_path),
        "image_concepts": ", ".join(str(path) for path in generated_paths),
    }


def _build_prompt(concept: dict, plan: dict) -> str:
    return "\n".join(
        [
            "Create one premium editorial source image for Brand Name Design.",
            "The image will be used inside an Instagram carousel, but must contain no readable text.",
            "",
            "Brand aesthetic:",
            "- technical archive label, optical scan, reconstruction protocol",
            "- bone/off-white, near-black, muted grey-brown, deep oxidized red accent",
            "- premium, minimal, mysterious, system-like",
            "- physical oil painting to digital reconstruction to wearable fragment",
            "- no generic fashion ad, no neon cyberpunk, no glossy gradients, no bokeh, no fake typography",
            "",
            f"Carousel title: {plan.get('title', '')}",
            f"Concept name: {concept.get('name', '')}",
            f"Creative brief: {concept.get('brief', '')}",
            f"Source asset hint: {concept.get('source_asset_hint', '')}",
            f"Image prompt: {concept.get('prompt', '')}",
            "",
            "Use the provided reference images as source material when available. Preserve their art/product DNA, but create a stronger designed image direction.",
        ]
    )


def _generate_image(prompt: str, reference_paths: list[Path]) -> str:
    client = OpenAI()

    if reference_paths:
        content = [{"type": "input_text", "text": prompt}]
        for path in reference_paths:
            content.append({"type": "input_image", "image_url": _data_url(path)})
        try:
            response = client.responses.create(
                model="gpt-5.4-mini",
                input=[{"role": "user", "content": content}],
                tools=[{"type": "image_generation"}],
            )
            image_data = [output.result for output in response.output if output.type == "image_generation_call"]
            if image_data:
                return image_data[0]
        except OpenAIError:
            pass

    response = client.images.generate(
        model=IMAGE_CONCEPT_MODEL,
        prompt=prompt,
        size=IMAGE_CONCEPT_SIZE,
        quality=IMAGE_CONCEPT_QUALITY,
        n=1,
    )
    return response.data[0].b64_json


def _prepare_references(paths: list[Path]) -> list[Path]:
    reference_dir = ROOT_DIR / ".cache" / "image_references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[Path] = []

    for index, path in enumerate(paths, start=1):
        try:
            with Image.open(path) as image:
                converted = image.convert("RGB")
                converted.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                canvas = ImageOps.contain(converted, (1200, 1200))
                out = reference_dir / f"reference-{index:02}.jpg"
                canvas.save(out, "JPEG", quality=86)
                prepared.append(out)
        except Exception:
            continue

    return prepared


def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"
