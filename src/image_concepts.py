from __future__ import annotations

import base64
from datetime import datetime
import json
from pathlib import Path

from openai import OpenAI, OpenAIError
from PIL import Image, ImageOps

from .settings import (
    AI_IMAGE_GENERATION_ENABLED,
    IMAGE_CONCEPT_COUNT,
    IMAGE_CONCEPT_MODEL,
    IMAGE_CONCEPT_QUALITY,
    IMAGE_CONCEPT_SIZE,
    OUTPUTS_DIR,
    ROOT_DIR,
)
from .product_inventory import product_inventory_summary
from .visual_renderer import _slug


POST_VISUAL_REFERENCE_LIMIT = 10


def generate_image_concepts(plan: dict, asset_paths: list[Path]) -> dict[str, str]:
    if not AI_IMAGE_GENERATION_ENABLED:
        return {}
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


def generate_post_visual_image(
    item: dict,
    concept_type: str,
    brief: str,
    direction: str,
    reference_paths: list[Path],
) -> dict[str, str]:
    if not AI_IMAGE_GENERATION_ENABLED:
        raise RuntimeError("AI image generation is disabled. Set AI_IMAGE_GENERATION_ENABLED=true to render new AI images.")

    stamp = datetime.now().strftime("%Y-%m-%d")
    post_id = _slug(item.get("id", "post"))
    output_dir = OUTPUTS_DIR / "image_concepts" / f"{stamp}-{post_id}-{_slug(concept_type)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = _build_post_prompt(item, concept_type, brief, direction)
    prepared_references = _prepare_references(reference_paths[:POST_VISUAL_REFERENCE_LIMIT])
    image_data = _generate_image(prompt, prepared_references)
    image_path = output_dir / f"{_slug(concept_type)}-render.png"
    image_path.write_bytes(base64.b64decode(image_data))

    metadata = {
        "post_id": item.get("id"),
        "concept_type": concept_type,
        "direction": direction,
        "output_path": str(image_path),
        "final_prompt": prompt,
        "reference_paths": [str(path) for path in prepared_references],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (output_dir / "render-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"image_path": str(image_path), "metadata_path": str(output_dir / "render-metadata.json"), "prompt": prompt, "concept_type": concept_type}


def _build_post_prompt(item: dict, concept_type: str, brief: str, direction: str) -> str:
    normalized_type = concept_type.replace("_iteration", "")
    type_instruction = {
        "model_shoot": (
            "Create a realistic editorial photoshoot image with an AI-generated model wearing the exact referenced garment. "
            "The garment graphic, silhouette, color, and product identity must follow the provided product/campaign references."
        ),
        "process_detail": (
            "Create a premium process/detail image: artist brush, pencil, canvas texture, scanner bed, design file, studio table, "
            "or digital reconstruction detail tied to the referenced source files."
        ),
        "feed_breaker": (
            "Create a premium feed-breaker or text-backdrop image: folded textile, garment texture, canvas surface, quiet product detail, "
            "negative space, restrained color field, or tactile material surface tied to the referenced brand world."
        ),
        "curator_process_reference": (
            "Create a premium curator reference image. If the brief asks for product/body/campaign, make a realistic editorial product reference. "
            "If it asks for process, make a brush, pencil, canvas, scanner, studio, or digital-file detail. If it asks for a feed breaker, make a tactile surface or color/texture composition."
        ),
    }.get(normalized_type, "Create one premium visual concept image tied to the referenced post assets.")

    return "\n".join(
        [
            "Create one premium editorial image for Brand Name Design.",
            type_instruction,
            "Use the provided reference images as the source of truth. Do not invent new garments, graphics, products, colorways, logos, or readable text.",
            "When multiple reference images show the same product, separate their roles: design mockups define the actual sellable artwork/logo/graphic placement; blank model references define fit, drape, crop, neckline, sleeves, and material behavior only; detail references define fabric and construction.",
            "If a blank model reference conflicts with a designed product mockup, keep the model fit but apply the designed product graphic/logo/artwork from the front_design/back_design references. Never output the blank as the final designed product when a design source exists.",
            "Product placement requirements:",
            item.get("product_reference_requirements", "Use the selected product folder references to preserve exact garment side, graphic placement, small logo placement, trims, grommets, tags, hems, and silhouette."),
            "If the selected product has a minimal front logo, chest mark, hem mark, tag, grommet, or other small front-side branding/detail in the references, preserve it visibly on front-facing model shots.",
            "Small garment branding may be approximate and non-readable, but it must be present in the correct location when the product reference shows it.",
            "If a model appears, make the person realistic, fashion-editorial, and natural. Avoid uncanny faces, extra limbs, distorted hands, fake typography, or generic fashion-ad styling.",
            "If this is a process/detail concept, make it tactile and art-directed: pencil marks, brush strokes, canvas grain, screenshots, scanner light, table shadows, paper edges, or studio evidence.",
            "Aesthetic: minimal, premium, art-first streetwear; archival reconstruction; near-black, bone/off-white, muted grey-brown, deep oxidized red accents; concrete, metal, glass, studio, gallery, or city textures.",
            "No readable text. No fake brand names. No neon cyberpunk. No glossy gradients. No sticker collage.",
            "",
            "Approved product constraint:",
            product_inventory_summary(),
            "",
            f"Post id: {item.get('id', '')}",
            f"Format: {item.get('format', '')}",
            f"Pillar: {item.get('pillar', '')}",
            f"Hook: {item.get('hook', '')}",
            f"Caption: {item.get('caption', '')}",
            f"Source files: {', '.join(item.get('selected_assets') or item.get('source_files') or [])}",
            f"Reviewer direction: {direction or 'Make a visually appealing main image that helps tie this post into the curated feed.'}",
            "",
            "Brief to follow:",
            brief[:6000],
        ]
    )


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
            "- fashion campaign energy: product hero, styled body, movement, textile texture, confidence, lifestyle context",
            "- premium streetwear energy: oversized silhouette, graphic garment emphasis, city/studio/gallery setting, concrete/glass/metal textures, attitude, candid motion, product-as-identity",
            "- inspired by big-brand campaign logic without copying any brand: emotional momentum, sport/style crossover, clean premium product desirability",
            "- garment/object must feel desirable before the concept is explained",
            "- models and garments must be based only on approved product inventory or named raw store/campaign assets",
            "- do not invent new apparel, graphics, silhouettes, colorways, logos, or products",
            "- no generic fashion ad, no generic hypebeast poster, no fake graffiti, no museum-only documentation, no neon cyberpunk, no glossy gradients, no bokeh, no fake typography",
            "",
            "Approved product constraint:",
            product_inventory_summary(),
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
            if path.suffix.lower() in {".heic", ".heif"}:
                try:
                    import pillow_heif  # type: ignore

                    pillow_heif.register_heif_opener()
                except ImportError:
                    continue
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
