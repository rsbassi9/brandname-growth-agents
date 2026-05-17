from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .settings import BRAND_CONTEXT_DIR


PRODUCT_CATALOG_PATH = BRAND_CONTEXT_DIR / "website_product_catalog.json"


def fetch_website_summary(url: str) -> str:
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "brandname-growth-agents/0.1"})
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Website fetch unavailable: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = description_tag.get("content", "").strip() if description_tag else "No meta description found"
    headings = [heading.get_text(" ", strip=True) for heading in soup.find_all(["h1", "h2"])][:12]

    return "\n".join(
        [
            f"URL: {url}",
            f"Title: {title}",
            f"Meta description: {description}",
            "Headings:",
            *[f"- {heading}" for heading in headings],
        ]
    )


def fetch_product_catalog(url: str, force: bool = False) -> list[dict]:
    if PRODUCT_CATALOG_PATH.exists() and not force:
        try:
            return json.loads(PRODUCT_CATALOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    products = _fetch_shopify_products(url)
    if not products:
        products = _fetch_visible_product_links(url)

    PRODUCT_CATALOG_PATH.write_text(json.dumps(products, indent=2), encoding="utf-8")
    return products


def product_catalog_summary(url: str, drive_assets: list[dict] | None = None) -> str:
    products = fetch_product_catalog(url)
    if not products:
        return "Website product catalog unavailable. Use Drive product folder names and product images as the source of truth."

    matches = match_products_to_assets(products, drive_assets or [])
    lines = [
        "Website product catalog context:",
        "Use these product descriptions to understand the garment, but use Drive Product files as the visual source of truth.",
        "",
    ]
    for product in products[:40]:
        product_matches = matches.get(product["title"], [])
        match_text = ", ".join(product_matches[:8]) if product_matches else "No exact Drive product asset match yet"
        description = product.get("description", "")
        lines.extend(
            [
                f"### {product['title']}",
                f"- URL: {product.get('url', '')}",
                f"- Matched Drive product assets/folders: {match_text}",
                f"- Description: {description or 'No description found.'}",
            ]
        )
        variants = product.get("variants") or []
        if variants:
            lines.append(f"- Variants: {', '.join(variants[:12])}")
        lines.append("")
    return "\n".join(lines).strip()


def match_products_to_assets(products: list[dict], assets: list[dict]) -> dict[str, list[str]]:
    product_assets = [asset for asset in assets if asset.get("creativeBucket") == "Store Products"]
    matches: dict[str, list[str]] = {}
    for product in products:
        product_tokens = _tokens(product.get("title", ""))
        if not product_tokens:
            continue
        matched = []
        for asset in product_assets:
            haystack = " ".join(
                [
                    asset.get("name", ""),
                    asset.get("folderPath", ""),
                ]
            )
            asset_tokens = _tokens(haystack)
            if _token_score(product_tokens, asset_tokens) >= 0.55:
                matched.append(asset.get("name", ""))
        matches[product.get("title", "")] = sorted(set(matched))
    return matches


def _fetch_shopify_products(url: str) -> list[dict]:
    products: list[dict] = []
    base = url.rstrip("/") + "/"
    for endpoint in ("products.json", "collections/all/products.json"):
        page = 1
        while page <= 4:
            api_url = urljoin(base, f"{endpoint}?limit=250&page={page}")
            try:
                response = requests.get(api_url, timeout=20, headers={"User-Agent": "brandname-growth-agents/0.1"})
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError):
                break
            batch = payload.get("products") or []
            if not batch:
                break
            products.extend(_normalize_shopify_product(item, base) for item in batch)
            if len(batch) < 250:
                break
            page += 1
        if products:
            break
    return _dedupe_products(products)


def _normalize_shopify_product(item: dict, base_url: str) -> dict:
    title = item.get("title", "").strip()
    description = _clean_html(item.get("body_html", ""))
    handle = item.get("handle", "")
    variants = [
        variant.get("title", "").strip()
        for variant in item.get("variants", [])
        if variant.get("title") and variant.get("title") != "Default Title"
    ]
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    return {
        "title": title,
        "handle": handle,
        "url": urljoin(base_url, f"products/{handle}") if handle else base_url,
        "description": description,
        "product_type": item.get("product_type", ""),
        "vendor": item.get("vendor", ""),
        "tags": tags,
        "variants": variants,
    }


def _fetch_visible_product_links(url: str) -> list[dict]:
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "brandname-growth-agents/0.1"})
        response.raise_for_status()
    except requests.RequestException:
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    products = []
    seen = set()
    for link in soup.select("a[href*='/products/']"):
        href = link.get("href", "")
        full_url = urljoin(url, href)
        title = link.get_text(" ", strip=True)
        if not title or full_url in seen:
            continue
        seen.add(full_url)
        products.append({"title": title, "handle": Path(href).name, "url": full_url, "description": "", "variants": [], "tags": []})
    return products[:80]


def _dedupe_products(products: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for product in products:
        key = product.get("handle") or product.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(product)
    return deduped


def _clean_html(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.split(r"\b(Size Chart|gid://shopify/Product)\b", text, maxsplit=1)[0].strip()
    return text[:900]


def _tokens(value: str) -> set[str]:
    value = value.lower().replace("t-shirt", "tshirt").replace("t shirt", "tshirt")
    ignored = {"the", "and", "or", "a", "an", "for", "with", "mockups", "copy", "final", "product", "products"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value)
        if len(token) > 2 and token not in ignored
    }


def _token_score(product_tokens: set[str], asset_tokens: set[str]) -> float:
    if not product_tokens:
        return 0.0
    if _garment_conflict(product_tokens, asset_tokens):
        return 0.0
    overlap = product_tokens & asset_tokens
    return len(overlap) / len(product_tokens)


def _garment_conflict(product_tokens: set[str], asset_tokens: set[str]) -> bool:
    groups = [
        {"shorts", "pants", "sweatpants", "joggers"},
        {"shirt", "tshirt", "tee", "top", "tank"},
        {"hoodie", "sweatshirt", "zip", "jacket"},
        {"hat", "cap", "beanie"},
    ]
    product_group = next((group for group in groups if product_tokens & group), None)
    asset_group = next((group for group in groups if asset_tokens & group), None)
    return bool(product_group and asset_group and product_group is not asset_group)
