from __future__ import annotations

import json


def test_seo_audit_scores_required_checks_and_duplicates() -> None:
    from app.services.seo_audit import audit_products

    products = [
        {
            "title": "Short tee",
            "handle": "short-tee",
            "product_type": "T Shirt",
            "meta_description": "",
            "images": [{"alt": ""}],
        },
        {
            "title": "Short tee",
            "handle": "short-tee-two",
            "product_type": "T Shirt",
            "meta_description": "A concise product page for a quiet garment.",
            "images": [{"alt": "front product photo"}],
        },
    ]

    audits = audit_products(products)

    assert audits[0].score == 0
    assert "duplicate product title in catalog" in audits[0].issues
    assert "meta description is missing" in audits[0].issues
    assert "one or more product images are missing alt text" in audits[0].issues
    assert audits[1].product_handle == "short-tee-two"
    assert "duplicate product title in catalog" in audits[1].issues


def test_seo_audit_persists_and_lists_rows(client) -> None:
    from app.db import session_scope
    from app.services.seo_audit import SeoAuditResult, persist_audits

    with session_scope() as session:
        persist_audits(session, [SeoAuditResult(product_handle="canvas-tee", score=75, issues=["meta description should be 140-160 characters"])])

    response = client.get("/api/v1/seo/audits")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload[0]["product_handle"] == "canvas-tee"
    assert payload[0]["score"] == 75
    assert json.loads(payload[0]["issues_json"]) == ["meta description should be 140-160 characters"]


def test_seo_audit_endpoint_enqueues_read_only_job(client) -> None:
    from app.db import session_scope
    from app.models import Job

    response = client.post("/api/v1/seo/audit")

    assert response.status_code == 200, response.text
    with session_scope() as session:
        job = session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.kind == "seo_audit"
