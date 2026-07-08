"""Generation service (P1: copy, image concept, carousel render, video script).

Two execution paths, selected by LOCAL_ONLY_AGENT_RUNS:
- local-only: deterministic, filesystem/Pillow-only output (no network);
- live: agent/OpenAI calls through the client wrapper (never hit in tests).

Both paths return the same shape, which jobs.py persists as an immutable
asset_versions row: {prompt, content_text, file_path, model_used}.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..settings import get_settings
from .openai_client import resolve_model
from .rendering import render_text_carousel

logger = logging.getLogger(__name__)

AGENT_FOR_TYPE = {
    "copy": "content_creator",
    "image_concept": "visual_designer",
    "carousel": "creative_composer",
    "video_script": "content_creator",
    "voiceover": "content_creator",
}

LOCAL_MODEL_LABEL = "local-deterministic"


def build_prompt(asset_type: str, brief: str, params: dict[str, Any]) -> str:
    settings = get_settings()
    tone = str(params.get("tone", "premium, minimal, mysterious"))
    template = str(params.get("template", "default"))
    return "\n".join(
        [
            f"Brand: {settings.brand_name} (streetwear, {settings.shopify_url})",
            f"Asset type: {asset_type}",
            f"Tone: {tone}",
            f"Template: {template}",
            "Ground every claim in the approved raw photoshoot/product assets; never invent garments.",
            "",
            "Brief:",
            brief.strip(),
        ]
    )


async def generate_content(asset_type: str, brief: str, params: dict[str, Any]) -> dict[str, Any]:
    """Generate one take for an asset. Returns the version payload."""
    settings = get_settings()
    prompt = build_prompt(asset_type, brief, params)
    if settings.local_only_agent_runs:
        return _generate_local(asset_type, brief, params, prompt)
    return await _generate_live(asset_type, brief, params, prompt)


# ---------------------------------------------------------------------------
# Deterministic local-only fallback (no network, safe by construction)
# ---------------------------------------------------------------------------


def _generate_local(asset_type: str, brief: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    settings = get_settings()
    brand = settings.brand_name
    headline = brief.strip().splitlines()[0][:80] if brief.strip() else "Archive fragment"

    if asset_type == "carousel":
        slides = params.get("slides") or [
            {"eyebrow": "SOURCE", "headline": headline, "body": brief.strip()[:180], "palette": "dark"},
            {"eyebrow": "SYSTEM", "headline": "Reconstructed", "body": "Canvas to file to wearable fragment.", "palette": "light"},
        ]
        rendered = render_text_carousel(params.get("title") or headline, slides)
        return {
            "prompt": prompt,
            "content_text": json.dumps({"slides": slides}, ensure_ascii=False),
            "file_path": str(rendered[0]) if rendered else None,
            "model_used": LOCAL_MODEL_LABEL,
        }

    if asset_type == "image_concept":
        # A ready-to-paste external prompt pack (muapi.ai and friends), not an
        # API image call: local-only mode never touches OpenAI.
        content = "\n".join(
            [
                f"# Image concept prompt pack — {headline}",
                "",
                "Paste into your external generator (muapi.ai primary).",
                "",
                prompt,
                "",
                "Constraints: no readable text, no invented garments, premium minimal streetwear, "
                "near-black / bone / muted grey-brown / oxidized red palette.",
            ]
        )
        return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL}

    if asset_type == "video_script":
        content = json.dumps(_video_prompt_pack(headline, brief, params), ensure_ascii=False, indent=2)
        return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL}
        content = "\n".join(
            [
                f"# Video script draft — {headline}",
                "",
                "Hook (0-2s): open on the strongest campaign frame; no explanation.",
                "Beat 1 (2-6s): source painting / process evidence.",
                "Beat 2 (6-10s): reconstruction detail, slow controlled motion.",
                "Beat 3 (10-14s): garment on body, fragment in motion.",
                "Close (14-16s): quiet CTA card. Review-ready draft only; no auto-publishing.",
                "",
                "On-screen text: SOURCE / SYSTEM / FRAGMENT / WEAR",
                "",
                "Brief:",
                brief.strip(),
            ]
        )
        return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL}

    if asset_type == "voiceover":
        content = "\n".join(
            [
                f"# Voiceover script draft — {headline}",
                "",
                "TTS not configured (local-only mode): script-only version.",
                "",
                f"{brand} began with a system: canvas, capture, reconstruct, drop.",
                brief.strip(),
            ]
        )
        return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL}

    # Default: copy.
    content = "\n".join(
        [
            f"Hook: {headline}",
            "",
            f"Caption draft: {brief.strip() or 'Extracted from canvas. Reconstructed for the body.'}",
            "",
            "Alt line: Same system, now worn.",
            "CTA: Review-ready draft only. No auto-publishing.",
        ]
    )
    return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL}


def _video_prompt_pack(headline: str, brief: str, params: dict[str, Any]) -> dict[str, Any]:
    source_note = str(params.get("source_note", "Use approved campaign/product source assets only."))
    hook = f"{headline}. Open with the garment or source fragment already in motion."
    shot_list = [
        {
            "time": "0-2s",
            "shot": "Strongest campaign frame, close crop, no setup.",
            "motion": "Slow push-in with minimal handheld drift.",
        },
        {
            "time": "2-6s",
            "shot": "Source painting or process evidence, texture visible.",
            "motion": "Macro pass across canvas, scan, or reconstruction detail.",
        },
        {
            "time": "6-10s",
            "shot": "Garment detail, print fragment, cotton weight, fold, or silhouette.",
            "motion": "Controlled lateral move, premium product proof.",
        },
        {
            "time": "10-14s",
            "shot": "On-body or product silhouette, fragment in real context.",
            "motion": "Quiet turn or step, no exaggerated posing.",
        },
        {
            "time": "14-16s",
            "shot": "Clean end frame with restrained CTA.",
            "motion": "Hold steady, let the object carry the close.",
        },
    ]
    on_screen_text = ["SOURCE", "SYSTEM", "FRAGMENT", "WEAR"]
    base_prompt = (
        f"{hook}\n"
        f"Brief: {brief.strip() or headline}\n"
        f"{source_note}\n"
        "Premium minimal streetwear reel, grounded in raw photoshoot/product imagery, "
        "near-black ink, bone surface, muted grey-brown neutrals, restrained oxidized red accent, "
        "no invented garments, no readable fake text, no glossy fashion-ad exaggeration."
    )
    return {
        "kind": "video_prompt_pack",
        "version": 1,
        "title": headline,
        "hook": hook,
        "shot_list": shot_list,
        "on_screen_text": on_screen_text,
        "providers": {
            "muapi.ai": {
                "role": "primary",
                "prompt": (
                    f"{base_prompt}\n"
                    "Format for muapi.ai image-to-video or text-to-video: vertical 9:16, 16 seconds, "
                    "cinematic product motion, slow controlled camera, realistic cloth texture."
                ),
                "settings": {"aspect_ratio": "9:16", "duration_seconds": 16, "motion": "low to medium"},
            },
            "fal.ai": {
                "role": "secondary",
                "prompt": (
                    f"{base_prompt}\n"
                    "Format for fal.ai video model: vertical social reel, subtle camera motion, realistic product detail."
                ),
                "settings": {"aspect_ratio": "9:16", "duration_seconds": 8},
            },
            "Runway": {
                "role": "secondary",
                "prompt": (
                    f"{base_prompt}\n"
                    "Format for Runway: use reference image when available, low motion brush, product-first framing."
                ),
                "settings": {"ratio": "9:16", "camera_motion": "slow push and lateral drift"},
            },
            "Kling": {
                "role": "secondary",
                "prompt": (
                    f"{base_prompt}\n"
                    "Format for Kling: keep garment geometry stable, realistic fabric, restrained movement."
                ),
                "settings": {"mode": "standard", "aspect_ratio": "9:16"},
            },
        },
        "manual_use": "Paste one provider prompt into the external generator. Review output before publishing.",
    }


# ---------------------------------------------------------------------------
# Live path (mocked in every test; never called during development)
# ---------------------------------------------------------------------------


async def _generate_live(asset_type: str, brief: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    from .agents import get_agent, run_agent

    premium = bool(params.get("premium"))
    override = params.get("model") or None
    model = resolve_model(premium=premium, override=override)

    if asset_type == "carousel":
        # Text plan comes from the agent; the pixels are still rendered locally
        # with Pillow (render happens in the render_carousel job / P2 flow).
        agent_key = AGENT_FOR_TYPE["carousel"]
    else:
        agent_key = AGENT_FOR_TYPE.get(asset_type, "content_creator")

    agent = get_agent(agent_key, premium=premium)
    text = await run_agent(agent, prompt)
    return {"prompt": prompt, "content_text": text, "file_path": None, "model_used": model}
