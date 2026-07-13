"""SEO keyword and content plan generation (P10-3)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Asset, AssetVersion
from ..settings import get_settings
from .brain import build_memory_context
from .generation import LOCAL_MODEL_LABEL
from .shopify import ShopifyService


def generate_seo_plan(session: Session, products: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if products is None:
        preview = ShopifyService().product_preview(limit=80)
        products = [product for product in preview.get("products", []) if isinstance(product, dict)]
    settings = get_settings()
    memory = build_memory_context(_memory_query(products), k=5)
    keyword_map = keyword_map_for_products(products)
    blog_plan = blog_plan_for_products(products, keyword_map)
    prompt = "\n".join(
        [
            f"SEO keyword and content plan for {settings.brand_name}.",
            f"Store URL: {settings.shopify_url}",
            "Build a product/collection keyword map and blog plan with internal links to exact product URLs.",
            "Use only read-only catalog data and approved brand memory; do not write to Shopify.",
            "",
            memory.block,
            "",
            "Catalog sample:",
            *[_product_line(product) for product in products[:40]],
        ]
    ).strip()
    plan = {
        "kind": "seo_plan",
        "version": 1,
        "keyword_map": keyword_map,
        "blog_plan": blog_plan,
        "manual_use": "Review this plan, then copy keywords and outlines into your SEO/content workflow manually. Shopify writes remain disabled.",
    }
    params = {
        "source": "shopify_read_only_preview",
        "product_count": len(products),
        "product_handles": [str(product.get("handle") or "") for product in products if product.get("handle")],
        "memory_document_ids": memory.document_ids,
        "brand_profile_version_no": memory.profile_version_no,
    }
    return {
        "prompt": prompt,
        "content_text": json.dumps(plan, ensure_ascii=False, indent=2),
        "file_path": None,
        "model_used": LOCAL_MODEL_LABEL,
        "params": params,
    }


def keyword_map_for_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    collection_terms: dict[str, set[str]] = defaultdict(set)
    for product in products:
        handle = str(product.get("handle") or product.get("id") or "").strip()
        title = str(product.get("title") or handle or "Untitled product").strip()
        product_type = str(product.get("product_type") or "").strip()
        tags = _tags(product.get("tags"))
        primary = _primary_keyword(title, product_type, tags)
        secondary = _secondary_keywords(title, product_type, tags)
        url = _product_url(handle)
        rows.append(
            {
                "scope": "product",
                "handle": handle,
                "title": title,
                "url": url,
                "primary_keyword": primary,
                "secondary_keywords": secondary,
            }
        )
        if product_type:
            collection_terms[product_type].add(primary)
            collection_terms[product_type].update(secondary[:2])

    for product_type, terms in sorted(collection_terms.items()):
        rows.append(
            {
                "scope": "collection",
                "handle": _slug(product_type),
                "title": product_type,
                "url": _collection_url(product_type),
                "primary_keyword": f"{product_type.lower()} streetwear",
                "secondary_keywords": sorted(terms)[:6],
            }
        )
    return rows


def blog_plan_for_products(products: list[dict[str, Any]], keyword_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_rows = [row for row in keyword_map if row.get("scope") == "product"]
    if not product_rows:
        return [
            {
                "title": "How source artwork becomes a wearable drop",
                "target_keyword": "artwork grounded streetwear",
                "outline": [
                    "Show the source material",
                    "Explain the reconstruction process",
                    "Point readers to the next reviewed product drop",
                ],
                "internal_links": [],
            }
        ]

    posts: list[dict[str, Any]] = []
    for row in product_rows[:6]:
        title = str(row.get("title") or row.get("handle") or "Product")
        posts.append(
            {
                "title": f"How to style {title} without losing the source story",
                "target_keyword": row["primary_keyword"],
                "outline": [
                    "Open with the source artwork or design system",
                    "Describe the silhouette, material, and strongest product details",
                    "Show one outfit context and one close-up proof point",
                    "Close with a manual link to the product page",
                ],
                "internal_links": [{"label": title, "url": row["url"], "handle": row.get("handle", "")}],
            }
        )
    return posts


def latest_keyword_map(session: Session) -> dict[str, str]:
    statement = (
        select(AssetVersion)
        .join(Asset)
        .where(Asset.type == "seo_plan")
        .order_by(AssetVersion.is_selected.desc(), AssetVersion.created_at.desc(), AssetVersion.id.desc())
    )
    version = session.execute(statement).scalars().first()
    if version is None or not version.content_text:
        return {}
    try:
        parsed = json.loads(version.content_text)
    except json.JSONDecodeError:
        return {}
    rows = parsed.get("keyword_map") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        return {}
    mapping: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("scope") != "product":
            continue
        handle = str(row.get("handle") or "").strip()
        keyword = str(row.get("primary_keyword") or "").strip()
        if handle and keyword:
            mapping[handle] = keyword
    return mapping


def _memory_query(products: list[dict[str, Any]]) -> str:
    sample = " ".join(_product_line(product) for product in products[:12])
    return f"seo keyword plan blog content internal links {sample}".strip()


def _product_line(product: dict[str, Any]) -> str:
    return " | ".join(
        [
            str(product.get("title") or ""),
            str(product.get("handle") or ""),
            str(product.get("product_type") or ""),
            str(product.get("tags") or ""),
        ]
    ).strip()


def _primary_keyword(title: str, product_type: str, tags: list[str]) -> str:
    if product_type:
        return f"{product_type.lower()} streetwear"
    if tags:
        return f"{tags[0].lower()} streetwear"
    words = _tokens(title)
    return " ".join(words[:3] + ["streetwear"]).strip()


def _secondary_keywords(title: str, product_type: str, tags: list[str]) -> list[str]:
    candidates = [
        f"{title.lower()} outfit",
        f"{title.lower()} product details",
        "artwork grounded clothing",
        "source material streetwear",
    ]
    if product_type:
        candidates.extend([f"{product_type.lower()} drop", f"{product_type.lower()} outfit"])
    candidates.extend(f"{tag.lower()} clothing" for tag in tags[:4])
    unique: list[str] = []
    for candidate in candidates:
        compact = " ".join(candidate.split())
        if compact and compact not in unique:
            unique.append(compact[:80])
    return unique[:6]


def _product_url(handle: str) -> str:
    base = get_settings().shopify_url.rstrip("/")
    return f"{base}/products/{handle}" if handle else f"{base}/products"


def _collection_url(product_type: str) -> str:
    base = get_settings().shopify_url.rstrip("/")
    return f"{base}/collections/{_slug(product_type)}"


def _tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def _slug(value: str) -> str:
    slug = "-".join(_tokens(value))
    return slug or "products"
