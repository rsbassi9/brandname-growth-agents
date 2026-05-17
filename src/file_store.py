from datetime import datetime
from pathlib import Path

from .settings import OUTPUTS_DIR


OUTPUT_FOLDERS = [
    "asset_inventory",
    "content_ideas",
    "content_drafts",
    "content_candidates",
    "content_variations",
    "seo",
    "analytics",
    "daily_reports",
    "ad_concepts",
    "visual_content",
    "image_concepts",
]


def ensure_output_dirs() -> None:
    for folder in OUTPUT_FOLDERS:
        (OUTPUTS_DIR / folder).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def save_markdown(folder: str, title: str, content: str) -> Path:
    ensure_output_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d")
    safe_title = title.lower().replace(" ", "-").replace("_", "-")
    path = OUTPUTS_DIR / folder / f"{stamp}-{safe_title}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path
