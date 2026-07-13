"""Paste-ready SEO fix generation (P10-2)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import SeoAudit
from ..paths import memory_dir
from ..settings import get_settings
from .brain import build_memory_context
from .generation import LOCAL_MODEL_LABEL


def generate_seo_fix(session: Session, audit_id: int) -> dict:
    audit = session.get(SeoAudit, audit_id)
    if audit is None:
        raise ValueError("SEO audit not found")
    issues = _issues(audit)
    memory = build_memory_context(f"seo fix {audit.product_handle} {' '.join(issues)}", k=5)
    product_truth = _product_truth_excerpt(audit.product_handle)
    title = _title_for(audit.product_handle)
    meta = _meta_description_for(audit.product_handle)
    alt = _alt_text_for(audit.product_handle)
    prompt = "\n".join(
        [
            f"SEO fix for product handle: {audit.product_handle}",
            f"Audit score: {audit.score}",
            "Issues:",
            *[f"- {issue}" for issue in issues],
            "",
            memory.block,
            "",
            "Product truth excerpt:",
            product_truth,
        ]
    ).strip()
    content = "\n".join(
        [
            f"# SEO Fix: {audit.product_handle}",
            "",
            "## New title",
            title,
            "",
            "## Meta description",
            meta,
            "",
            "## Image alt text",
            alt,
            "",
            "## Manual use",
            "Copy these fields into Shopify manually after review. Shopify writes remain disabled.",
        ]
    )
    params = {
        "seo_audit_id": audit.id,
        "product_handle": audit.product_handle,
        "issues": issues,
        "memory_document_ids": memory.document_ids,
        "brand_profile_version_no": memory.profile_version_no,
        "product_truth_excerpt": product_truth,
    }
    return {"prompt": prompt, "content_text": content, "file_path": None, "model_used": LOCAL_MODEL_LABEL, "params": params}


def _issues(audit: SeoAudit) -> list[str]:
    try:
        parsed = json.loads(audit.issues_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _title_for(handle: str) -> str:
    base = handle.replace("-", " ").replace("_", " ").title().strip() or f"{get_settings().brand_name} Product"
    title = f"{base} - Artwork-Grounded Streetwear"
    return title[:60]


def _meta_description_for(handle: str) -> str:
    base = handle.replace("-", " ").replace("_", " ").strip() or "product"
    text = (
        f"Shop {base} from {get_settings().brand_name}: artwork-grounded streetwear shaped by source material, product truth, "
        "and quiet reconstruction details for daily wear."
    )
    return text[:160]


def _alt_text_for(handle: str) -> str:
    base = handle.replace("-", " ").replace("_", " ").strip() or f"{get_settings().brand_name} garment"
    return f"{base} product image showing garment artwork, silhouette, and material detail."


def _product_truth_excerpt(handle: str, limit: int = 700) -> str:
    path = memory_dir() / "product_truth.json"
    if not path.exists():
        return "No product_truth.json found; verify against Shopify and source photos before publishing."
    text = path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()
    normalized = handle.replace("-", " ").replace("_", " ").lower()
    index = lowered.find(normalized)
    if index < 0:
        return text[:limit]
    start = max(index - 180, 0)
    return text[start : start + limit]
