"""Calendar CRUD, feed order persistence, system endpoints (P1-5/P1-6)."""

from __future__ import annotations


def test_health(client) -> None:
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["brand"]


def test_mode_reports_local_only(client) -> None:
    payload = client.get("/api/v1/system/mode").json()
    assert payload["local_only_agent_runs"] is True
    assert payload["image_model"] == "gpt-image-1"
    assert payload["model_default"]


def test_calendar_crud_roundtrip(client) -> None:
    created = client.post(
        "/api/v1/calendar",
        json={"date": "2026-07-10", "status": "draft", "data": {"hook": "A system begins."}},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    item_id = item["id"]
    assert item["data"]["hook"] == "A system begins."

    patched = client.patch(
        f"/api/v1/calendar/{item_id}",
        json={"status": "approved", "slot": "day", "data": {"caption": "New caption"}},
    ).json()
    assert patched["status"] == "approved"
    assert patched["data"]["hook"] == "A system begins."
    assert patched["data"]["caption"] == "New caption"
    assert patched["data"]["slot"] == "day"

    listed = client.get("/api/v1/calendar", params={"month": "2026-07"}).json()
    assert [entry["id"] for entry in listed] == [item_id]

    assert client.delete(f"/api/v1/calendar/{item_id}").status_code == 204
    assert client.get(f"/api/v1/calendar/{item_id}").status_code == 404


def test_calendar_duplicate_id_conflict(client) -> None:
    body = {"id": "post-dup", "date": "2026-07-11", "status": "draft", "data": {}}
    assert client.post("/api/v1/calendar", json=body).status_code == 201
    assert client.post("/api/v1/calendar", json=body).status_code == 409


def test_feed_order_persists(client) -> None:
    for index in range(3):
        client.post(
            "/api/v1/calendar",
            json={"id": f"post-{index}", "date": f"2026-07-0{index + 1}", "status": "draft", "data": {}},
        )
    default_order = [item["id"] for item in client.get("/api/v1/feed").json()]
    assert set(default_order) == {"post-0", "post-1", "post-2"}

    response = client.post("/api/v1/feed/order", json={"item_ids": ["post-2", "post-0", "post-1"]})
    assert response.status_code == 200
    ordered = [item["id"] for item in client.get("/api/v1/feed").json()]
    assert ordered == ["post-2", "post-0", "post-1"]


def test_calendar_guardrails_setting_persists(client) -> None:
    assert client.get("/api/v1/system/calendar-guardrails").json()["max_items_per_day_channel"] == 3

    response = client.put("/api/v1/system/calendar-guardrails", json={"max_items_per_day_channel": 5})

    assert response.status_code == 200, response.text
    assert response.json()["max_items_per_day_channel"] == 5
    assert client.get("/api/v1/system/calendar-guardrails").json()["max_items_per_day_channel"] == 5


def test_strategy_feedback_posts_event(client, app_env) -> None:
    response = client.post(
        "/api/v1/strategy/learn/feedback",
        json={"output_path": "outputs/x.md", "rating": 4, "comment": "good", "improvement_request": "shorter"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["rating"] == 4

    summary = client.get("/api/v1/strategy/learn/summary").json()
    assert "good" in summary["summary"]
    # Also persisted to the legacy jsonl learning store.
    assert (app_env / "memory" / "feedback.jsonl").exists()


def test_strategy_context_read_only(client) -> None:
    docs = client.get("/api/v1/strategy/context").json()
    assert isinstance(docs, list)
    assert client.get("/api/v1/strategy/context/../etc/passwd").status_code == 404
