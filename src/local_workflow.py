from __future__ import annotations

from collections import Counter
from datetime import date
import re

from .drive_service import GoogleDriveService
from .file_store import save_markdown
from .settings import OUTPUTS_DIR


BRAND_WORDS = "Extracted, Reconstructed, Fragment, Archive, Drift, System, Canvas"


def run_local_daily_workflow() -> dict[str, str]:
    cycle = _next_cycle()
    drive = GoogleDriveService()
    inventory = drive.get_asset_inventory()
    assets = inventory.files or drive.list_raw_assets()
    buckets = _bucket_assets(assets)

    paths = {
        "asset_inventory": str(save_markdown("asset_inventory", f"local-cycle-{cycle}-asset-inventory", _asset_inventory_markdown(inventory.summary, buckets, cycle))),
    }
    candidates = _candidate_specs(buckets, cycle)
    ideas = _ideas_markdown(candidates, cycle)
    candidate_markdown = _candidates_markdown(candidates, cycle)
    drafts = _drafts_markdown(candidates, cycle)
    seo = _seo_markdown(candidates, cycle)
    analytics = _analytics_markdown(candidates, cycle)
    ads = _ads_markdown(candidates, cycle)

    paths["ideas"] = str(save_markdown("content_ideas", f"local-cycle-{cycle}-content-ideas", ideas))
    paths["content_candidates"] = str(save_markdown("content_candidates", f"local-cycle-{cycle}-content-candidates", candidate_markdown))
    paths["drafts"] = str(save_markdown("content_drafts", f"local-cycle-{cycle}-content-drafts", drafts))
    paths["seo"] = str(save_markdown("seo", f"local-cycle-{cycle}-seo-recommendations", seo))
    paths["analytics"] = str(save_markdown("analytics", f"local-cycle-{cycle}-analytics-notes", analytics))
    paths["ad_concepts"] = str(save_markdown("ad_concepts", f"local-cycle-{cycle}-ad-concepts", ads))
    paths["report"] = str(save_markdown("daily_reports", f"local-cycle-{cycle}-daily-growth-report", _report_markdown(paths, candidates, cycle)))
    return paths


def _next_cycle() -> int:
    today = date.today().isoformat()
    folder = OUTPUTS_DIR / "content_candidates"
    if not folder.exists():
        return 1
    cycles = []
    for path in folder.glob(f"{today}-local-cycle-*-content-candidates.md"):
        match = re.search(r"local-cycle-(\d+)-content-candidates", path.name)
        if match:
            cycles.append(int(match.group(1)))
    return max(cycles, default=0) + 1


def _bucket_assets(assets: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for asset in assets:
        bucket = asset.get("creativeBucket") or "Other"
        buckets.setdefault(bucket, []).append(asset)
    for bucket, items in buckets.items():
        reverse_numbers = bucket in {"Photoshoot / Campaign", "Shoot Photos"}
        items.sort(key=lambda asset: ((_last_number(asset.get("name", "")) * (-1 if reverse_numbers else 1)), asset.get("name", "").lower()))
    return buckets


def _names(buckets: dict[str, list[dict]], bucket: str, limit: int = 4, offset: int = 0) -> list[str]:
    items = buckets.get(bucket, [])
    if not items:
        return []
    rotated = items[offset % len(items) :] + items[: offset % len(items)]
    names = []
    seen = set()
    for item in rotated:
        name = item.get("name", "")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _last_number(value: str) -> int:
    matches = re.findall(r"\d+", value)
    return int(matches[-1]) if matches else 0


def _candidate_specs(buckets: dict[str, list[dict]], cycle: int) -> list[dict]:
    offset = max(0, cycle - 1)
    first_post = _names(buckets, "First Post Inspiration", 7)
    campaign = _names(buckets, "Photoshoot / Campaign", 4, offset * 3) or _names(buckets, "Shoot Photos", 4, offset * 3)
    products_a = _names(buckets, "Store Products", 4, offset * 4)
    products_b = _names(buckets, "Store Products", 4, offset * 4 + 4)
    process = _names(buckets, "Process / Studio", 4, offset * 2)
    design = _names(buckets, "Design Assets", 3, offset)
    video = _names(buckets, "Video", 2, offset)

    return [
        {
            "title": "First Post System Cue",
            "format": "Carousel",
            "pillar": "Drop Context",
            "hook": "[4DRFT] begins with a system.",
            "caption": "A first sequence from the human-built reference folder: source, reconstruction, object, atmosphere.",
            "source_files": first_post or campaign or design,
            "on_screen": ["SOURCE", "SYSTEM", "FRAGMENT", "WEAR"],
            "structure": "Use the First Post folder as soft pacing inspiration. Keep it quiet, sequential, and premium.",
            "why": "This converts the feedback loop into a clear intro without turning inspiration into hard rules.",
            "priority": "High",
        },
        {
            "title": "Photoshoot Body Proof",
            "format": "Reel",
            "pillar": "Campaign Proof",
            "hook": "See the fragment on body.",
            "caption": "The object leaves the archive. Same system, now worn.",
            "source_files": campaign,
            "on_screen": ["ON BODY", "FRAGMENT IN MOTION", "NO EXPLANATION NEEDED"],
            "structure": "Cut between strongest campaign frames. Keep motion slow and controlled.",
            "why": "The new photoshoot assets should carry desirability before the concept is explained.",
            "priority": "High",
        },
        {
            "title": "Product As Object",
            "format": "Solo Image Post",
            "pillar": "Product Clarity",
            "hook": "The garment is the object.",
            "caption": "Pure product clarity: cotton, weight, silhouette, fragment.",
            "source_files": products_a,
            "on_screen": ["OBJECT", "350 GSM", "RECONSTRUCTED"],
            "structure": "One product-forward frame, minimal caption, no generic clothing-store language.",
            "why": "It gives shoppers enough product truth without flattening the brand voice.",
            "priority": "High",
        },
        {
            "title": "Source To Reconstruction",
            "format": "Carousel",
            "pillar": "Transformation",
            "hook": "A physical painting. Reconstructed.",
            "caption": "Canvas to file to wearable fragment. The source remains visible in the system.",
            "source_files": design + process[:2],
            "on_screen": ["CANVAS", "SCAN", "RECONSTRUCT", "FRAGMENT"],
            "structure": "Start with source art, move into process, end with product context.",
            "why": "Transformation content is the strongest differentiator for Brand Name Design.",
            "priority": "High",
        },
        {
            "title": "Studio Evidence",
            "format": "Carousel",
            "pillar": "Process",
            "hook": "The system is built, not styled.",
            "caption": "Paint, reconstruction, fragments, decisions. The process is the proof.",
            "source_files": process + design[:1],
            "on_screen": ["ARCHIVE", "DRIFT", "SYSTEM"],
            "structure": "Use process images as evidence, not decoration.",
            "why": "Process makes the premium/mysterious tone credible.",
            "priority": "Medium",
        },
        {
            "title": "Second Product Fragment",
            "format": "Carousel",
            "pillar": "Product Rotation",
            "hook": "Another fragment from the same source.",
            "caption": "Different garment. Same origin system.",
            "source_files": products_b or products_a,
            "on_screen": ["FRAGMENT", "ARCHIVE", "WEAR"],
            "structure": "Rotate product families so the feed does not over-index one garment.",
            "why": "Keeps the drop feeling larger than one item.",
            "priority": "Medium",
        },
        {
            "title": "Motion Or CTA Anchor",
            "format": "Reel" if video else "Solo Image Post",
            "pillar": "Drop CTA",
            "hook": "[4DRFT] is live.",
            "caption": "Extracted from canvas. Reconstructed for the body. Review-ready draft only.",
            "source_files": video + campaign[:2] if video else campaign[:1] + products_a[:2],
            "on_screen": ["[4DRFT]", "LIVE", "REVIEW DRAFT"],
            "structure": "Use as a restrained close to the cycle. No auto-publishing.",
            "why": "Gives the calendar a direct action point while staying review-only.",
            "priority": "Medium",
        },
    ]


def _asset_inventory_markdown(summary: str, buckets: dict[str, list[dict]], cycle: int) -> str:
    lines = [
        f"# Local Asset Inventory - Cycle {cycle}",
        "",
        "Approval status: Draft for review",
        "",
        "Run mode: Local only. No OpenAI text or image calls.",
        "",
        summary,
        "",
        "## Bucket Focus",
    ]
    for bucket, items in sorted(buckets.items()):
        lines.append(f"- {bucket}: {len(items)} assets")
    return "\n".join(lines)


def _ideas_markdown(candidates: list[dict], cycle: int) -> str:
    lines = [f"# Local Content Ideas - Cycle {cycle}", "", "Approval status: Draft for review", "", f"Brand vocabulary: {BRAND_WORDS}", ""]
    for index, item in enumerate(candidates, start=1):
        lines.extend([f"### {index}. {item['title']}", f"- Core idea: {item['hook']}", f"- Asset basis: {', '.join(item['source_files'])}", ""])
    return "\n".join(lines)


def _candidates_markdown(candidates: list[dict], cycle: int) -> str:
    lines = [f"# Local Content Candidates - Cycle {cycle}", "", "Approval status: Draft for review", "", "Run mode: Local only. No AI-generated text/images.", ""]
    for index, item in enumerate(candidates, start=1):
        lines.extend(
            [
                f"### {index}. {item['title']}",
                f"- Format: {item['format']}",
                f"- Content pillar: {item['pillar']}",
                f"- Hook: {item['hook']}",
                f"- Caption: {item['caption']}",
                f"- Source files: {', '.join(item['source_files'])}",
                f"- Asset roles: {item['structure']}",
                f"- On-screen text: {', '.join(item['on_screen'])}",
                f"- Story structure: {item['structure']}",
                f"- Edit notes: Minimal, intentional, mysterious, premium. Avoid generic clothing-store phrasing.",
                f"- Why this should work: {item['why']}",
                f"- Posting priority: {item['priority']}",
                "",
            ]
        )
    return "\n".join(lines)


def _drafts_markdown(candidates: list[dict], cycle: int) -> str:
    lines = [f"# Local Drafts - Cycle {cycle}", "", "Approval status: Draft for review", ""]
    for item in candidates[:4]:
        lines.extend([f"## {item['title']}", f"Hook: {item['hook']}", f"Caption draft: {item['caption']}", f"Asset notes: {', '.join(item['source_files'])}", ""])
    return "\n".join(lines)


def _seo_markdown(candidates: list[dict], cycle: int) -> str:
    product_names = Counter(name.split("-mockups", 1)[0] for item in candidates for name in item["source_files"] if "mockups" in name.lower())
    lines = [f"# Local SEO Notes - Cycle {cycle}", "", "Approval status: Draft for review", "", "## Product Language", "- Use art-translation language before clothing basics.", "- Mention cotton/weight only after the concept and object framing.", ""]
    for name, _ in product_names.most_common(4):
        lines.append(f"- {name}: describe as a wearable fragment from the [4DRFT] reconstruction system.")
    return "\n".join(lines)


def _analytics_markdown(candidates: list[dict], cycle: int) -> str:
    formats = Counter(item["format"] for item in candidates)
    return "\n".join(
        [
            f"# Local Analytics Notes - Cycle {cycle}",
            "",
            "Approval status: Draft for review",
            "",
            "No live performance pull was used. Track these manually after posting:",
            "- Saves per post",
            "- Profile visits",
            "- Product page clicks",
            "- Carousel completion or Reel retention",
            "",
            "Planned format mix:",
            *[f"- {name}: {count}" for name, count in sorted(formats.items())],
        ]
    )


def _ads_markdown(candidates: list[dict], cycle: int) -> str:
    return "\n".join(
        [
            f"# Local Ad Readiness Notes - Cycle {cycle}",
            "",
            "Approval status: Draft for review",
            "",
            "Do not launch ads yet. Use organic response to identify the strongest hook.",
            "",
            "Potential future tests:",
            "- Transformation hook: physical painting to wearable fragment.",
            "- Body proof hook: see the fragment on body.",
            "- Product object hook: heavyweight cotton, reconstructed source, premium silhouette.",
        ]
    )


def _report_markdown(paths: dict[str, str], candidates: list[dict], cycle: int) -> str:
    return "\n".join(
        [
            f"# Local Daily Growth Report - Cycle {cycle}",
            "",
            "Approval status: Draft for review",
            "",
            "Run mode: Local only. No OpenAI text generation and no OpenAI image generation were used.",
            "",
            "## Summary",
            f"- Built {len(candidates)} content candidates from the current Drive asset pool.",
            "- Prioritized First Post inspiration, Photoshoot / Campaign assets, product mockups, process/studio files, and design assets.",
            "- All outputs are review-ready drafts only.",
            "",
            "## Output Paths",
            *[f"- {name}: {path}" for name, path in paths.items()],
        ]
    )
