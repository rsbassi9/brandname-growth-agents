from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "perf_import"


def test_import_instagram_fixture_detects_meta_views_headers(client) -> None:
    response = client.post(
        "/api/v1/performance/import",
        json={"channel": "instagram", "csv_text": (FIXTURES / "mbs_instagram_content_sample.csv").read_text()},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["posts_upserted"] == 2
    assert payload["metrics_inserted"] == 2
    assert "Views" in payload["detected_columns"]
    assert payload["metrics"][0]["impressions"] == 1200
    assert payload["metrics"][0]["engagement_rate"] == 0.2125
    assert json.loads(payload["posts"][0]["meta_json"])["Audience note"] == "warm audience"


def test_import_tiktok_fixture_detects_video_headers(client) -> None:
    response = client.post(
        "/api/v1/performance/import",
        json={"channel": "tiktok", "csv_text": (FIXTURES / "tiktok_studio_content_sample.csv").read_text()},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["posts"][0]["external_ref"] == "https://tiktok.com/@brand/video/1"
    assert payload["posts"][0]["title_or_caption"] == "Canvas proof reel"
    assert payload["metrics"][0]["impressions"] == 3400
    assert payload["metrics"][0]["follows_from_post"] == 12


def test_import_legacy_instagram_impressions_alias(client) -> None:
    response = client.post(
        "/api/v1/performance/import",
        json={"channel": "instagram", "csv_text": (FIXTURES / "mbs_instagram_impressions_legacy.csv").read_text()},
    )

    assert response.status_code == 200, response.text
    metric = response.json()["metrics"][0]
    assert metric["impressions"] == 2500
    assert metric["saves"] == 44


def test_import_is_idempotent_for_same_capture(client) -> None:
    csv_text = (FIXTURES / "mbs_instagram_content_sample.csv").read_text()
    first = client.post("/api/v1/performance/import", json={"channel": "instagram", "csv_text": csv_text}).json()
    second = client.post("/api/v1/performance/import", json={"channel": "instagram", "csv_text": csv_text}).json()

    assert first["metrics_inserted"] == 2
    assert second["posts_upserted"] == 2
    assert second["metrics_inserted"] == 0


def test_unknown_headers_return_detected_columns_for_manual_mapping(client) -> None:
    response = client.post(
        "/api/v1/performance/import",
        json={"channel": "instagram", "csv_text": "Mystery,Another\nx,y\n"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["detected_columns"] == ["Mystery", "Another"]


def test_multipart_csv_import(client) -> None:
    csv_text = (FIXTURES / "tiktok_studio_content_sample.csv").read_text()
    response = client.post(
        "/api/v1/performance/import",
        data={"channel": "tiktok"},
        files={"file": ("tiktok.csv", csv_text, "text/csv")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["metrics_inserted"] == 1
