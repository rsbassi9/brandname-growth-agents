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


def test_generate_injects_auditable_brand_memory(client) -> None:
    import json

    from app.db import session_scope
    from app.models import BrainDocument, BrainEmbedding, BrandProfileVersion
    from app.services.brain import embed_texts, vector_to_blob

    with session_scope() as session:
        profile = BrandProfileVersion(
            version_no=1,
            profile_md="Use source-proof language and avoid invented garments.",
            distilled_from_json="{}",
        )
        selected = BrainDocument(
            kind="asset_version",
            ref_id="seed:1",
            text="Selected caption about canvas fragment reconstruction.",
            meta_json=json.dumps({"is_selected": True}),
        )
        feedback = BrainDocument(
            kind="feedback",
            ref_id="fb_1",
            text="Positive feedback: stronger when the hook mentions source proof.",
            meta_json=json.dumps({"rating": 5}),
        )
        session.add_all([profile, selected, feedback])
        session.flush()
        for document in [selected, feedback]:
            vector = embed_texts([document.text])[0]
            session.add(
                BrainEmbedding(
                    document_id=document.id,
                    model="local-hash-256",
                    dim=vector.size,
                    vector=vector_to_blob(vector),
                )
            )

    payload = _generate_copy(client, "Canvas fragment caption with source proof")
    job = wait_for_job(client, payload["job_id"])
    assert job["status"] == "succeeded", job["message"]

    detail = client.get(f"/api/v1/assets/{payload['asset_id']}").json()
    version = detail["versions"][0]
    params = json.loads(version["params_json"])
    assert params["brand_profile_version_no"] == 1
    assert set(params["memory_document_ids"]) == {1, 2}
    assert "BRAND MEMORY" in version["prompt_snapshot"]
    assert "Current brand profile v1" in version["prompt_snapshot"]
    assert "doc#1" in version["prompt_snapshot"]
    assert "doc#2" in version["prompt_snapshot"]


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


def test_critique_and_iterate_version(client) -> None:
    import json

    payload = _generate_copy(client)
    wait_for_job(client, payload["job_id"])

    critique_response = client.post(f"/api/v1/assets/{payload['asset_id']}/versions/1/critique")
    assert critique_response.status_code == 200, critique_response.text
    critique = critique_response.json()["critique"]
    assert "QA critique" in critique

    detail = client.get(f"/api/v1/assets/{payload['asset_id']}").json()
    stored = json.loads(detail["versions"][0]["params_json"])
    assert stored["critique"] == critique

    iterate_response = client.post(f"/api/v1/assets/{payload['asset_id']}/versions/1/iterate")
    assert iterate_response.status_code == 200, iterate_response.text
    job = wait_for_job(client, iterate_response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{payload['asset_id']}").json()
    assert [version["version_no"] for version in detail["versions"]] == [1, 2]
    assert "Critique to address" in detail["versions"][1]["prompt_snapshot"]
    assert json.loads(detail["versions"][1]["params_json"])["iteration_of"] == 1


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


def test_generate_voiceover_script_only_in_local_mode(client) -> None:
    response = client.post(
        "/api/v1/generate",
        json={"type": "voiceover", "brief": "Voice line for the source painting reel", "params": {}},
    )
    assert response.status_code == 200
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    version = detail["versions"][0]
    assert detail["type"] == "voiceover"
    assert version["file_path"] is None
    assert "TTS not configured" in version["content_text"]


def test_create_ad_brief_from_ads_router(client, app_env) -> None:
    import json

    source_dir = app_env / "shoot"
    source_dir.mkdir()
    (source_dir / "front.jpg").write_bytes(b"jpg")
    source = client.post(
        "/api/v1/source-assets/index",
        json={"origin": "local", "path": str(source_dir), "tags": ["front-design"]},
    ).json()["items"][0]
    creative = _generate_copy(client, "Creative source caption")
    wait_for_job(client, creative["job_id"])

    response = client.post(
        "/api/v1/ads/briefs",
        json={
            "objective": "Sales",
            "audience": "Warm drop audience",
            "placement": "Instagram Feed + Reels",
            "hook": "Source work, now worn",
            "asset_id": creative["asset_id"],
            "source_asset_id": source["id"],
        },
    )
    assert response.status_code == 200, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job["message"]
    detail = client.get(f"/api/v1/assets/{response.json()['asset_id']}").json()
    assert detail["type"] == "ad_brief"
    pack = json.loads(detail["versions"][0]["content_text"])
    assert pack["kind"] == "ad_brief"
    assert len(pack["primary_text"]) == 3
    assert len(pack["headlines"]) == 3
    assert "Meta" not in pack["manual_use"] or "No Meta API integration" in pack["manual_use"]
    params = json.loads(detail["versions"][0]["params_json"])
    assert params["linked_asset_id"] == creative["asset_id"]
    assert params["source_asset_id"] == source["id"]


def test_voiceover_elevenlabs_helper_writes_mp3(app_env, monkeypatch) -> None:
    from app.services.generation import _voiceover_result
    from app.settings import reset_settings_cache

    class Response:
        content = b"mp3-bytes"

        def raise_for_status(self) -> None:
            return None

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setenv("BRAND_TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("BRAND_ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("BRAND_ELEVENLABS_VOICE_ID", "voice-123")
    reset_settings_cache()
    monkeypatch.setattr("app.services.generation.requests.post", fake_post)

    result = _voiceover_result("prompt", "A short voiceover.", "text-model")
    assert calls[0]["url"].endswith("/v1/text-to-speech/voice-123")
    assert calls[0]["headers"]["xi-api-key"] == "test-key"
    assert calls[0]["json"]["text"] == "A short voiceover."
    assert result["file_path"].endswith(".mp3")
    from pathlib import Path

    assert Path(result["file_path"]).read_bytes() == b"mp3-bytes"


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
