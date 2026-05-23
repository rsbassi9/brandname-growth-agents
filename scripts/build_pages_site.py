from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT_DIR / "pages"
OUTPUTS_DIR = ROOT_DIR / "outputs"
SITE_DIR = ROOT_DIR / "site"
MEDIA_DIR = SITE_DIR / "media"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_SUFFIXES = {".md", ".txt", ".json"}


def main() -> None:
    rebuild_site_dir()
    copy_shell_files()
    data = collect_dashboard_data()
    (SITE_DIR / "data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Built GitHub Pages dashboard with {len(data['days'])} days at {SITE_DIR}")


def rebuild_site_dir() -> None:
    resolved_site = SITE_DIR.resolve()
    resolved_root = ROOT_DIR.resolve()
    if resolved_site == resolved_root or resolved_root not in resolved_site.parents:
        raise RuntimeError(f"Refusing to rebuild unsafe site directory: {resolved_site}")

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True)
    MEDIA_DIR.mkdir(parents=True)


def copy_shell_files() -> None:
    for filename in ["index.html", "styles.css", "app.js"]:
        shutil.copy2(PAGES_DIR / filename, SITE_DIR / filename)


def collect_dashboard_data() -> dict:
    days: dict[str, dict] = {}
    if not OUTPUTS_DIR.exists():
        return {"days": []}

    for path in sorted(OUTPUTS_DIR.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue

        day = day_from_path(path)
        if not day:
            continue

        entry = days.setdefault(day, {"date": day, "reports": [], "images": []})
        relative = path.relative_to(ROOT_DIR).as_posix()
        category = path.relative_to(OUTPUTS_DIR).parts[0]

        if path.suffix.lower() in IMAGE_SUFFIXES:
            public_path = copy_media(path)
            entry["images"].append(
                {
                    "name": path.name,
                    "category": category,
                    "relativePath": relative,
                    "publicPath": public_path,
                }
            )
        elif path.suffix.lower() in TEXT_SUFFIXES:
            entry["reports"].append(
                {
                    "name": path.name,
                    "category": category,
                    "relativePath": relative,
                    "content": read_preview(path),
                }
            )

    ordered_days = sorted(days.values(), key=lambda item: item["date"], reverse=True)
    for day in ordered_days:
        day["reports"].sort(key=lambda item: (item["category"], item["name"]))
        day["images"].sort(key=lambda item: (item["category"], item["name"]))
    return {"days": ordered_days}


def day_from_path(path: Path) -> str | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.as_posix())
    return match.group(1) if match else None


def copy_media(path: Path) -> str:
    destination = MEDIA_DIR / path.relative_to(OUTPUTS_DIR)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination.relative_to(SITE_DIR).as_posix()


def read_preview(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) > 16_000:
        return text[:16_000].rstrip() + "\n\n[Preview truncated for public dashboard.]"
    return text


if __name__ == "__main__":
    main()
