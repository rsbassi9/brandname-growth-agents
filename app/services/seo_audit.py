"""Read-only Shopify SEO audit service (P10-1).

Score weights:
- title length 50-60 chars: 25 points
- meta description present and 140-160 chars: 25 points
- every returned product image has alt text: 25 points
- target keyword appears in title or description: 15 points
- product title is unique in the audited catalog: 10 points
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SeoAudit
from .shopify import ShopifyService


@dataclass(frozen=True)
class SeoAuditResult:
    product_handle: str
    score: int
    issues: list[str]


def audit_products(products: list[dict]) -> list[SeoAuditResult]:
    title_counts: dict[str, int] = {}
    for product in products:
        title = str(product.get("title") or "").strip().lower()
        if title:
            title_counts[title] = title_counts.get(title, 0) + 1
    return [audit_product(product, title_counts) for product in products]


def audit_product(product: dict, title_counts: dict[str, int] | None = None) -> SeoAuditResult:
    issues: list[str] = []
    score = 100
    title = str(product.get("title") or "").strip()
    handle = str(product.get("handle") or product.get("id") or title or "unknown").strip()
    description = str(product.get("meta_description") or product.get("description_excerpt") or "").strip()
    keyword = _target_keyword(product)

    if not 50 <= len(title) <= 60:
        score -= 25
        issues.append("title length should be 50-60 characters")

    if not description:
        score -= 25
        issues.append("meta description is missing")
    elif not 140 <= len(description) <= 160:
        score -= 25
        issues.append("meta description should be 140-160 characters")

    if not _all_images_have_alt(product):
        score -= 25
        issues.append("one or more product images are missing alt text")

    haystack = f"{title} {description}".lower()
    if keyword and keyword.lower() not in haystack:
        score -= 15
        issues.append(f"target keyword '{keyword}' is missing from title/description")

    normalized_title = title.lower()
    if normalized_title and (title_counts or {}).get(normalized_title, 0) > 1:
        score -= 10
        issues.append("duplicate product title in catalog")

    return SeoAuditResult(product_handle=handle, score=max(score, 0), issues=issues)


def audit_shopify_catalog(session: Session, limit: int = 80) -> list[SeoAudit]:
    preview = ShopifyService().product_preview(limit=limit)
    products = [product for product in preview.get("products", []) if isinstance(product, dict)]
    return persist_audits(session, audit_products(products))


def persist_audits(session: Session, audits: list[SeoAuditResult]) -> list[SeoAudit]:
    rows: list[SeoAudit] = []
    for result in audits:
        row = SeoAudit(
            product_handle=result.product_handle,
            score=result.score,
            issues_json=json.dumps(result.issues, ensure_ascii=False),
            audited_at=datetime.utcnow(),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def latest_audits(session: Session, limit: int = 100) -> list[SeoAudit]:
    return session.execute(select(SeoAudit).order_by(SeoAudit.audited_at.desc(), SeoAudit.id.desc()).limit(limit)).scalars().all()


def _target_keyword(product: dict) -> str:
    product_type = str(product.get("product_type") or "").strip()
    if product_type:
        return product_type
    tags = str(product.get("tags") or "").strip()
    if tags:
        return tags.split(",")[0].strip()
    title = str(product.get("title") or "").strip()
    return title.split(" ")[0] if title else ""


def _all_images_have_alt(product: dict) -> bool:
    images = product.get("images")
    if isinstance(images, list):
        return all(str(image.get("alt") or "").strip() for image in images if isinstance(image, dict))
    image_count = int(product.get("image_count") or 0)
    if image_count == 0:
        return True
    return bool(str(product.get("image_alt_text") or "").strip())
