"""Mandatory versioned identity, even before the learned Brand Brain is seeded."""

import hashlib

from ..paths import brand_context_dir


def brand_foundation() -> str:
    sections = [
        "BRAND FOUNDATION (versioned project context)",
        "The subject is the clothing/art brand. Growth Agents is its internal software, "
        "not a product to advertise. Drafts require owner approval; do not publish or spend.",
        "New competitor styles require the owner's explicit approval before use. "
        "Inspiration is abstract direction only, never competitor photos, logos or copied text.",
    ]
    for name in ("brand_brief.md", "visual_system.md"):
        raw = (brand_context_dir() / name).read_bytes()
        text = raw.decode("utf-8").strip()
        if not text:
            raise ValueError(f"Required brand context is empty: {name}")
        sections.append(f"{name} sha256={hashlib.sha256(raw).hexdigest()}\n{text}")
    return "\n\n".join(sections)
