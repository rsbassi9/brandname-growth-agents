from __future__ import annotations

import asyncio
from dataclasses import asdict
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .learning import FeedbackEntry, append_feedback, load_feedback
from .orchestrator import run_daily_workflow
from .settings import OUTPUTS_DIR, ROOT_DIR


STATIC_DIR = ROOT_DIR / "dashboard" / "static"

app = FastAPI(title="Brand Name Growth Agents")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class FeedbackRequest(BaseModel):
    output_path: str
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    improvement_request: str = ""
    category: str = "general"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/outputs")
def outputs() -> dict:
    return {"outputs": _collect_outputs()}


@app.get("/api/feedback")
def feedback() -> dict:
    return {"feedback": load_feedback()}


@app.post("/api/feedback")
def save_feedback(payload: FeedbackRequest) -> dict:
    entry = FeedbackEntry(**payload.model_dump())
    return {"feedback": append_feedback(entry)}


@app.post("/api/run")
def run_agents() -> dict:
    paths = asyncio.run(run_daily_workflow())
    return {"paths": paths}


@app.get("/api/file")
def read_file(path: str) -> dict:
    resolved = _safe_output_path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Output not found")

    if resolved.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return {"path": str(resolved), "kind": "image", "url": f"/media?path={resolved}"}

    return {"path": str(resolved), "kind": "text", "content": resolved.read_text(encoding="utf-8")}


@app.get("/media")
def media(path: str) -> FileResponse:
    resolved = _safe_output_path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=media_type)


def _collect_outputs() -> list[dict]:
    if not OUTPUTS_DIR.exists():
        return []

    files: list[Path] = []
    for path in OUTPUTS_DIR.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            files.append(path)

    results = []
    for path in sorted(files, key=lambda item: item.stat().st_mtime, reverse=True):
        rel = path.relative_to(ROOT_DIR)
        category = path.relative_to(OUTPUTS_DIR).parts[0]
        results.append(
            {
                "path": str(path),
                "relative_path": str(rel),
                "name": path.name,
                "category": category,
                "modified_at": path.stat().st_mtime,
                "kind": "image" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else "text",
            }
        )
    return results


def _safe_output_path(path: str) -> Path:
    resolved = Path(path).resolve()
    output_root = OUTPUTS_DIR.resolve()
    if resolved == output_root or output_root in resolved.parents:
        return resolved
    raise HTTPException(status_code=400, detail="Path must be inside outputs")
