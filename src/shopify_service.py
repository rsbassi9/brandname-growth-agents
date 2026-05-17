from __future__ import annotations

import requests
import re

from .settings import SHOPIFY_ADMIN_ACCESS_TOKEN, SHOPIFY_API_VERSION, SHOPIFY_STORE_DOMAIN, SHOPIFY_WRITE_ENABLED


class ShopifyService:
    def __init__(self) -> None:
        self.store_domain = SHOPIFY_STORE_DOMAIN.strip().replace("https://", "").replace("http://", "").strip("/")
        self.token = SHOPIFY_ADMIN_ACCESS_TOKEN.strip()
        self.api_version = SHOPIFY_API_VERSION
        self.enabled = bool(self.store_domain and self.token)
        self.write_enabled = bool(SHOPIFY_WRITE_ENABLED)

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "store_domain": self.store_domain,
            "api_version": self.api_version,
            "mode": "read_only_preview",
            "write_enabled": self.write_enabled,
            "missing": [
                name
                for name, value in {
                    "SHOPIFY_STORE_DOMAIN": self.store_domain,
                    "SHOPIFY_ADMIN_ACCESS_TOKEN": self.token,
                }.items()
                if not value
            ],
        }

    def product_preview(self, limit: int = 20) -> dict:
        if not self.enabled:
            return {"status": self.status(), "products": []}
        url = f"https://{self.store_domain}/admin/api/{self.api_version}/products.json"
        try:
            response = requests.get(
                url,
                headers={"X-Shopify-Access-Token": self.token},
                params={
                    "limit": limit,
                    "fields": (
                        "id,title,handle,body_html,product_type,tags,vendor,variants,image,images,"
                        "metafields_global_title_tag,metafields_global_description_tag"
                    ),
                },
                timeout=6,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = self.status()
            status["error"] = str(exc)
            return {"status": status, "products": []}

        products = []
        for item in response.json().get("products", []):
            images = item.get("images", [])
            products.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "handle": item.get("handle", ""),
                    "product_type": item.get("product_type", ""),
                    "tags": item.get("tags", ""),
                    "description_excerpt": _strip_html(item.get("body_html", ""))[:240],
                    "meta_title": item.get("metafields_global_title_tag", "") or "",
                    "meta_description": item.get("metafields_global_description_tag", "") or "",
                    "image_alt_text": "; ".join(filter(None, [image.get("alt") for image in images]))[:240],
                    "image_count": len(item.get("images", [])),
                    "variant_count": len(item.get("variants", [])),
                }
            )
        return {"status": self.status(), "products": products}

    def preview_for_items(self, items: list[dict]) -> dict:
        preview = self.product_preview(limit=80) if self.enabled else {"status": self.status(), "products": []}
        products = preview.get("products", [])
        for item in items:
            item["shopify_preview"] = self._preview_for_item(item, products, preview.get("status", self.status()))
        return {"status": preview.get("status", self.status()), "products": products}

    def _preview_for_item(self, item: dict, products: list[dict], status: dict) -> dict:
        if not self.enabled:
            return {
                "connected": False,
                "resource_type": item.get("action_type", "seo_action"),
                "current_value": "",
                "message": "Shopify preview is not connected yet. Add SHOPIFY_STORE_DOMAIN and SHOPIFY_ADMIN_ACCESS_TOKEN to .env.",
            }

        product = _best_product_match(f"{item.get('title', '')} {item.get('detail', '')}", products)
        if not product:
            return {
                "connected": True,
                "resource_type": item.get("action_type", "seo_action"),
                "current_value": "",
                "message": status.get("error") or "No matching Shopify product found in the read-only preview sample.",
            }

        action_type = item.get("action_type", "seo_action")
        field_map = {
            "product_title": "title",
            "meta_title": "meta_title",
            "meta_description": "meta_description",
            "product_description": "description_excerpt",
            "image_alt_text": "image_alt_text",
        }
        field = field_map.get(action_type, "description_excerpt")
        current_value = product.get(field, "") or ""
        return {
            "connected": True,
            "resource_type": action_type,
            "matched_product": product.get("title", ""),
            "matched_product_id": product.get("id"),
            "matched_handle": product.get("handle", ""),
            "current_value": current_value,
            "message": status.get("error") or ("Matched product preview." if current_value else "Matched product, but this field is currently empty or not returned by Shopify."),
        }

    def apply_seo_item(self, item: dict) -> dict:
        if not self.enabled:
            return {"applied": False, "blocked": True, "message": "Shopify is not connected.", "item_id": item.get("id")}
        if not self.write_enabled:
            return {
                "applied": False,
                "blocked": True,
                "message": "Write mode is disabled. Set SHOPIFY_WRITE_ENABLED=true only when ready.",
                "item_id": item.get("id"),
            }

        preview = self._preview_for_item(item, self.product_preview(limit=80).get("products", []), self.status())
        product_id = preview.get("matched_product_id")
        if not product_id:
            return {"applied": False, "blocked": True, "message": "No matching product found.", "item_id": item.get("id")}

        action_type = item.get("action_type")
        value = item.get("detail", "")
        update = _product_update_payload(action_type, value)
        if not update:
            return {"applied": False, "blocked": True, "message": f"Unsupported SEO action type: {action_type}", "item_id": item.get("id")}

        url = f"https://{self.store_domain}/admin/api/{self.api_version}/products/{product_id}.json"
        try:
            response = requests.put(
                url,
                headers={"X-Shopify-Access-Token": self.token, "Content-Type": "application/json"},
                json={"product": {"id": product_id, **update}},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"applied": False, "blocked": False, "message": str(exc), "item_id": item.get("id")}
        return {
            "applied": True,
            "blocked": False,
            "message": "Applied approved SEO update.",
            "item_id": item.get("id"),
            "product_id": product_id,
            "before": preview.get("current_value", ""),
            "after": value,
            "rollback_note": "Use Shopify product history or manually restore the before value shown in this log.",
        }


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").replace("&nbsp;", " ").strip()


def _best_product_match(text: str, products: list[dict]) -> dict:
    text_tokens = set(_tokens(text))
    best: tuple[int, dict] = (0, {})
    for product in products:
        haystack = " ".join(
            [
                product.get("title", ""),
                product.get("handle", ""),
                product.get("product_type", ""),
                product.get("tags", ""),
            ]
        )
        score = len(text_tokens.intersection(_tokens(haystack)))
        if product.get("title", "").lower() in text.lower():
            score += 8
        if score > best[0]:
            best = (score, product)
    return best[1] if best[0] >= 2 else {}


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def _product_update_payload(action_type: str, value: str) -> dict:
    if action_type == "product_title":
        return {"title": value}
    if action_type == "product_description":
        return {"body_html": value}
    if action_type == "meta_title":
        return {"metafields_global_title_tag": value}
    if action_type == "meta_description":
        return {"metafields_global_description_tag": value}
    return {}
