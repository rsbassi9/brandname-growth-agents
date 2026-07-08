"""Generate -> job -> version happy path, regenerate, select, SSE (P1-6)."""

from __future__ import annotations

from tests._helpers import wait_for_job


def _generate_copy(client, brief: str = "Drop teaser for the reconstructed fragment") -> dict:
    response = client.post(
        "/api/v1/generate",
        json={"type": "copy", "brief": brief, "params": {"tone": "quiet"}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_generate_job_version_happy_path(client) -> None:
    payload = _generate_copy(client)
    job = wait_for_job(client, payload["job_id"])
    assert job["status"] == "succeeded", job["message"]

    detail = client.get(f"/api/v1/assets/{payload['asset_id']}").json()
    assert detail["type"] == "copy"
    assert len(detail["versions"]) == 1
    version = detail["versions"][0]
    assert version["version_no"] == 1
    assert version["is_selected"] is True
    assert version["model_used"] == "local-deterministic"
    assert "Drop teaser" in (version["content_text"] or "")
    assert "Drop teaser" in version["prompt_snapshot"]


def test_regenerate_creates_v2_and_v1_unchanged(client) -> None:
    payload = _generate_copy(client)
    wait_for_job(client, payload["job_id"])
    v1_before = client.get(f"/api/v1/assets/{payload['asset_id']}").json()["versions"][0]

    regen = client.post(f"/api/v1/assets/{payload['asset_id']}/regenerate")
    assert regen.status_code == 200, regen.text
    job = wait_for_job(client, regen.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]

    detail = client.get(f"/api/v1/assets/{payload['asset_id']}").json()
    assert [v["version_no"] for v in detail["versions"]] == [1, 2]
    v1_after = detail["versions"][0]
    # Immutability: version 1 content untouched by the regeneration.
    assert v1_after["content_text"] == v1_before["content_text"]
    assert v1_after["prompt_snapshot"] == v1_before["prompt_snapshot"]
    # Regenerate reuses the original brief.
    assert "Drop teaser" in (detail["versions"][1]["content_text"] or "")


def test_select_version(client) -> None:
    payload = _generate_copy(client)
    wait_for_job(client, payload["job_id"])
    regen = client.post(f"/api/v1/assets/{payload['asset_id']}/regenerate")
    wait_for_job(client, regen.json()["job_id"])

    response = client.post(f"/api/v1/assets/{payload['asset_id']}/versions/2/select")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "selected"
    flags = {v["version_no"]: v["is_selected"] for v in detail["versions"]}
    assert flags == {1: False, 2: True}


def test_select_missing_version_404(client) -> None:
    payload = _generate_copy(client)
    wait_for_job(client, payload["job_id"])
    response = client.post(f"/api/v1/assets/{payload['asset_id']}/versions/99/select")
    assert response.status_code == 404


def test_sse_emits_completion(client) -> None:
    payload = _generate_copy(client)
    events = []
    with client.stream("GET", f"/api/v1/jobs/{payload['job_id']}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if events and events[-1] == "completion":
                break
    assert "completion" in events


def test_generate_carousel_renders_files(client, app_env) -> None:
    response = client.post(
        "/api/v1/generate",
        json={"type": "carousel", "brief": "Canvas to fragment", "params": {"title": "demo-carousel"}},
    )
    assert response.status_code == 200
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    file_path = detail["versions"][0]["file_path"]
    assert file_path and file_path.endswith(".png")
    from pathlib import Path

    assert Path(file_path).exists()


def test_generate_video_script_creates_structured_prompt_pack(client) -> None:
    import json

    response = client.post(
        "/api/v1/generate",
        json={"type": "video_script", "brief": "Reel for the reconstructed fragment", "params": {}},
    )
    assert response.status_code == 200
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    pack = json.loads(detail["versions"][0]["content_text"])
    assert pack["kind"] == "video_prompt_pack"
    assert list(pack["providers"]) == ["muapi.ai", "fal.ai", "Runway", "Kling"]
    assert pack["providers"]["muapi.ai"]["role"] == "primary"
    assert "Higgsfield" not in json.dumps(pack)


def test_create_video_prompt_pack_from_asset(client) -> None:
    source = _generate_copy(client, "Caption source for a reel")
    wait_for_job(client, source["job_id"])

    response = client.post(f"/api/v1/assets/{source['asset_id']}/video-prompt-pack")
    assert response.status_code == 200, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    assert detail["type"] == "video_script"
    assert "muapi.ai" in detail["versions"][0]["content_text"]


def test_create_video_prompt_pack_from_calendar_item(client) -> None:
    create = client.post(
        "/api/v1/calendar",
        json={"date": "2026-07-20", "status": "planned", "data": {"title": "Calendar reel"}},
    )
    assert create.status_code == 201, create.text

    response = client.post(f"/api/v1/calendar/{create.json()['id']}/video-prompt-pack")
    assert response.status_code == 200, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    assert detail["title"].startswith("Video prompt pack")
    assert "Calendar reel" in detail["versions"][0]["content_text"]


def test_generate_unknown_campaign_404(client) -> None:
    response = client.post(
        "/api/v1/generate",
        json={"type": "copy", "brief": "x", "campaign_id": 12345},
    )
    assert response.status_code == 404


def test_image_iterate_job_fails_cleanly_in_local_only(client) -> None:
    """Local-only mode: the paid image path fails loudly, never silently."""
    from app.services.jobs import job_queue

    job_id = job_queue.enqueue(
        "image_iterate",
        {"item": {"id": "post-1"}, "concept_type": "model_shoot", "brief": "b", "direction": ""},
    )
    job = wait_for_job(client, job_id)
    assert job["status"] == "failed"
    assert "GenerationError" in job["message"] or "disabled" in job["message"]
