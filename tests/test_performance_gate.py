from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "perf_import"


def test_p8_gate_import_visibility_best_times_and_brain_insights(client) -> None:
    from app.db import session_scope
    from app.models import BrainDocument

    csv_text = (FIXTURES / "p8_gate_instagram_ranked.csv").read_text()

    imported = client.post("/api/v1/performance/import", json={"channel": "instagram", "csv_text": csv_text})
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["posts_upserted"] == 6
    assert payload["metrics_inserted"] == 6
    assert payload["posts"][0]["title_or_caption"] == "Proof-first atelier reel"
    assert payload["metrics"][0]["engagement_rate"] == 0.3

    posts = client.get("/api/v1/performance/posts?channel=instagram")
    assert posts.status_code == 200, posts.text
    visible_titles = {item["title_or_caption"] for item in posts.json()["items"]}
    assert {"Proof-first atelier reel", "Material detail"}.issubset(visible_titles)

    best_times = client.get("/api/v1/performance/best-times?channel=instagram")
    assert best_times.status_code == 200, best_times.text
    slots = best_times.json()
    assert slots[0]["channel"] == "instagram"
    assert slots[0]["weekday"] == 0
    assert slots[0]["hour"] == 10
    assert slots[0]["sample_size"] == 3
    assert slots[0]["mean_engagement_rate"] == pytest.approx(0.2)
    assert slots[1]["hour"] == 9
    assert slots[1]["mean_engagement_rate"] == pytest.approx(0.08)

    with session_scope() as session:
        insights = session.query(BrainDocument).filter_by(kind="metric_insight").all()
        assert insights
        assert any("achieved" in insight.text and "instagram" in insight.text for insight in insights)
