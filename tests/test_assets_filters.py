"""Asset list filters + pagination (P1-6)."""

from __future__ import annotations


def _seed_assets(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset

    init_db()
    with session_scope() as session:
        session.add_all(
            [
                Asset(type="copy", title="Drop teaser caption", status="draft"),
                Asset(type="copy", title="Launch caption", status="selected"),
                Asset(type="image_concept", title="Model shoot concept", status="draft"),
                Asset(type="carousel", title="Canvas carousel", status="archived"),
                Asset(type="video_script", title="Reel script drop", status="draft"),
            ]
        )


def test_filter_by_type(client, app_env) -> None:
    _seed_assets(app_env)
    payload = client.get("/api/v1/assets", params={"type": "copy"}).json()
    assert payload["total"] == 2
    assert all(item["type"] == "copy" for item in payload["items"])


def test_filter_by_status_and_query(client, app_env) -> None:
    _seed_assets(app_env)
    payload = client.get("/api/v1/assets", params={"status": "draft", "q": "concept"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Model shoot concept"


def test_pagination(client, app_env) -> None:
    _seed_assets(app_env)
    first = client.get("/api/v1/assets", params={"limit": 2, "offset": 0}).json()
    second = client.get("/api/v1/assets", params={"limit": 2, "offset": 2}).json()
    assert first["total"] == 5 and second["total"] == 5
    assert len(first["items"]) == 2 and len(second["items"]) == 2
    ids = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
    assert len(ids) == 4


def test_library_summary(client, app_env) -> None:
    _seed_assets(app_env)
    summary = client.get("/api/v1/library/summary").json()
    assert summary["total"] == 5
    assert summary["by_type"]["copy"] == 2
    assert summary["by_status"]["draft"] == 3


def test_asset_404(client) -> None:
    assert client.get("/api/v1/assets/999999").status_code == 404
