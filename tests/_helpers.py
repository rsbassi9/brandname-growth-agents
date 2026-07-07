"""Shared test helpers."""

from __future__ import annotations

import time


def wait_for_job(client, job_id: str, timeout: float = 15.0) -> dict:
    """Poll GET /api/v1/jobs/{id} until the job reaches a terminal status."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in ("succeeded", "failed"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")
