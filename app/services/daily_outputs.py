"""Validate daily artifacts and retain exact bytes for each review version.

The legacy orchestrator joins image paths with comma-space. Decode that format
only for its two known image-group keys; ordinary filenames are not split.
Nothing here approves or publishes an artifact.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..paths import outputs_dir

IMAGE_GROUPS = {"visual_slides": "carousel", "image_concepts": "image_concept"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class DailyOutput:
    key: str
    source: Path
    raw: bytes
    sha256: str
    asset_type: str
    text: str | None

    def snapshot(self) -> Path:
        directory = outputs_dir() / "daily_snapshots"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / f"{self.sha256}{self.source.suffix.lower()}"
        fd, temporary = tempfile.mkstemp(prefix=".draft-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(self.raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return path


def validate_outputs(paths: dict[str, str]) -> list[DailyOutput]:
    """Validate the whole batch before registering any successful output."""
    if not isinstance(paths, dict) or not paths:
        raise ValueError("Daily workflow returned no output files")
    root = outputs_dir().resolve()
    result = []
    for key, value in paths.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            raise ValueError("Daily output must have a nonempty key and file path")
        group = key in IMAGE_GROUPS
        for index, filename in enumerate(value.split(", ") if group else [value], start=1):
            path = Path(filename).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError(f"Missing or out-of-scope daily output: {key}")
            raw = path.read_bytes()
            if not raw:
                raise ValueError(f"Empty daily output: {key}")
            suffix = path.suffix.lower()
            if suffix in IMAGE_SUFFIXES:
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
                text = None
                asset_type = IMAGE_GROUPS.get(key, "image_concept")
            elif not group and suffix in {".md", ".txt", ".json"}:
                text = raw.decode("utf-8")
                if not text.strip():
                    raise ValueError(f"Blank daily output: {key}")
                asset_type = "copy"
            else:
                raise ValueError(f"Unsupported daily output format: {key}")
            result.append(DailyOutput(
                key=f"{key}:{index:02}" if group else key, source=path, raw=raw,
                sha256=hashlib.sha256(raw).hexdigest(), asset_type=asset_type, text=text,
            ))
    return result
