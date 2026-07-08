from __future__ import annotations

import json
from pathlib import Path

from tests._helpers import wait_for_job


def test_index_local_source_assets_idempotent(client, app_env: Path) -> None:
    shoot = app_env / "shoot"
    (shoot / "product").mkdir(parents=True)
    (shoot / "product" / "front.jpg").write_bytes(b"jpg")
    (shoot / "notes.txt").write_text("not an image", encoding="utf-8")

    payload = {"origin": "local", "path": str(shoot), "tags": ["drop-one"], "limit": 10}
    first = client.post("/api/v1/source-assets/index", json=payload)
    second = client.post("/api/v1/source-assets/index", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["total"] == 1
    assert second.json()["total"] == 1

    listing = client.get("/api/v1/source-assets").json()
    assert listing["total"] == 1
    source = listing["items"][0]
    assert source["origin"] == "local"
    assert source["path"].endswith("front.jpg")
    assert set(json.loads(source["tags_json"])) == {"drop-one", "product"}


def test_generate_with_source_asset_references(client, app_env: Path) -> None:
    shoot = app_env / "shoot"
    shoot.mkdir()
    reference = shoot / "front.png"
    reference.write_bytes(b"png")
    source = client.post(
        "/api/v1/source-assets/index",
        json={"origin": "local", "path": str(shoot), "tags": ["front-design"]},
    ).json()["items"][0]

    response = client.post(
        "/api/v1/generate",
        json={
            "type": "image_concept",
            "brief": "Create a grounded product prompt",
            "params": {"source_asset_ids": [source["id"]]},
        },
    )
    assert response.status_code == 200, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]

    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    version = detail["versions"][0]
    params = json.loads(version["params_json"])
    assert params["source_asset_ids"] == [source["id"]]
    assert params["reference_paths"] == [source["path"]]
    assert "Reference source assets" in version["prompt_snapshot"]
    assert source["path"] in version["content_text"]


def test_generate_rejects_more_than_four_source_assets(client) -> None:
    response = client.post(
        "/api/v1/generate",
        json={"type": "copy", "brief": "Too many refs", "params": {"source_asset_ids": [1, 2, 3, 4, 5]}},
    )
    assert response.status_code == 422
