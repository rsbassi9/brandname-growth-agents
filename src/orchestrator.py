import asyncio
from datetime import date
import json

from openai import AuthenticationError, OpenAIError, RateLimitError

from .agents import (
    ad_strategist_agent,
    analytics_agent,
    content_candidate_agent,
    content_creator_agent,
    content_strategist_agent,
    orchestrator_agent,
    run_agent,
    seo_agent,
    visual_designer_agent,
)
from .asset_design_roles import asset_design_context
from .campaign_memory import campaign_memory_context
from .creative_brief import creative_brief_context
from .drive_service import GoogleDriveService
from .file_store import read_text, save_markdown
from .image_concepts import generate_image_concepts
from .learning import feedback_summary
from .performance import performance_context_for_agents
from .product_rotation import product_rotation_context
from .settings import (
    BRAND_CONTEXT_DIR,
    BRAND_WEBSITE_URL,
    IMAGE_CONCEPTS_ENABLED,
    MEMORY_DIR,
    ROOT_DIR,
    VISUAL_ASSET_LIMIT,
    VISUAL_OUTPUT_ENABLED,
)
from .visual_renderer import extract_json_plan, render_carousel, text_slide_edit_context
from .web import fetch_website_summary, product_catalog_summary


def build_asset_inventory_markdown(asset_inventory_summary: str) -> str:
    return "\n".join(
        [
            "# Raw Asset Inventory",
            "",
            "Approval status: Draft for review",
            "",
            asset_inventory_summary,
            "",
            "## Content Use Notes",
            "- Use only assets that appear in this inventory, unless requesting a missing asset.",
            "- Prioritize transformation evidence: painting process, reconstruction screens, product fragments, and motion studies.",
            "- Keep all recommendations review-ready. Do not publish automatically.",
        ]
    )


def build_shared_context(asset_inventory_summary: str | None = None) -> str:
    brand_brief = read_text(BRAND_CONTEXT_DIR / "brand_brief.md")
    growth_strategy = read_text(BRAND_CONTEXT_DIR / "growth_strategy.md")
    visual_system = read_text(BRAND_CONTEXT_DIR / "visual_system.md")
    social_visual_direction = read_text(BRAND_CONTEXT_DIR / "social_visual_direction.md")
    fashion_marketing = read_text(BRAND_CONTEXT_DIR / "fashion_marketing_inspiration.md")
    creative_steering = creative_brief_context()
    campaign_context = campaign_memory_context()
    asset_inventory = asset_inventory_summary or GoogleDriveService().get_asset_inventory().summary
    raw_assets = GoogleDriveService().list_raw_assets()
    design_role_context = asset_design_context(raw_assets)
    website_summary = fetch_website_summary(BRAND_WEBSITE_URL)
    product_context = product_catalog_summary(BRAND_WEBSITE_URL, raw_assets)
    rotation_context = product_rotation_context(raw_assets)
    learning_context = feedback_summary()
    text_visual_learning = text_slide_edit_context()
    composition_learning = _composition_learning_context()
    quality_context = _calendar_quality_context()
    performance_context = performance_context_for_agents()

    return "\n\n".join(
        [
            f"Date: {date.today().isoformat()}",
            "Brand brief:",
            brand_brief,
            "Growth strategy:",
            growth_strategy,
            "Visual system:",
            visual_system,
            "Current Instagram visual direction reference:",
            social_visual_direction,
            "Fashion marketing inspiration:",
            fashion_marketing,
            "Current editable creative steering:",
            creative_steering,
            "Campaign operating brief:",
            campaign_context,
            "Learning loop feedback:",
            learning_context,
            "Text visual edit learning:",
            text_visual_learning,
            "Creative composition learning:",
            composition_learning,
            "Calendar quality, needs-work, and shoot-placeholder memory:",
            quality_context,
            "Performance memory:",
            performance_context,
            "Raw asset inventory:",
            asset_inventory,
            "Website summary:",
            website_summary,
            "Website product catalog matched to Drive product assets:",
            product_context,
            "Product rotation memory:",
            rotation_context,
            "Design-surface and backdrop asset intelligence:",
            design_role_context,
        ]
    )


def _composition_learning_context() -> str:
    calendar_path = MEMORY_DIR / "content_calendar.json"
    if not calendar_path.exists():
        return "No creative composition plans have been saved yet."
    try:
        items = json.loads(calendar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "No readable creative composition plans have been saved yet."
    lines = ["Saved creative composition preferences:"]
    for item in items[:12]:
        plan = item.get("composition_plan")
        if not plan:
            continue
        lines.append(f"- {item.get('id')}: {plan.get('summary', '')}")
        for slide in plan.get("slide_plan", [])[:4]:
            role = slide.get("role", "slot")
            asset = slide.get("asset_name") or slide.get("image_path") or "current visual"
            reason = slide.get("reason", "")
            lines.append(f"  - {role}: {asset} ({reason})")
    if len(lines) == 1:
        lines.append("- No creative composition plans have been saved yet.")
    return "\n".join(lines)


def _calendar_quality_context() -> str:
    calendar_path = MEMORY_DIR / "content_calendar.json"
    if not calendar_path.exists():
        return "No calendar quality memory yet."
    try:
        items = json.loads(calendar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "No readable calendar quality memory yet."
    lines = ["Calendar quality and shoot-placeholder memory:"]
    for item in items[:18]:
        score = (item.get("quality_score") or {}).get("overall")
        needs = item.get("needs_work") or []
        if score is not None:
            lines.append(f"- {item.get('id')}: quality {score}, status {item.get('status')}, role {item.get('visual_role')}")
        for reason in needs[:2]:
            lines.append(f"  - needs work: {reason.get('type')} / {reason.get('note')}")
        if item.get("format") == "Shoot Placeholder":
            lines.append(f"  - shoot placeholder: {item.get('shoot_brief') or item.get('calendar_note')}")
    if len(lines) == 1:
        lines.append("- No quality scores saved yet.")
    return "\n".join(lines)


async def generate_visual_content(shared_context: str, ideas: str, drafts: str) -> dict[str, str]:
    if not VISUAL_OUTPUT_ENABLED:
        return {}

    drive = GoogleDriveService()
    asset_dir = ROOT_DIR / ".cache" / "drive_assets"
    asset_paths = drive.download_image_assets(asset_dir, VISUAL_ASSET_LIMIT)
    asset_list = "\n".join(f"- {path.name}" for path in asset_paths) or "No image assets downloaded. Render text-first placeholder slides."

    raw_plan = await run_agent(
        visual_designer_agent,
        "\n\n".join(
            [
                shared_context,
                "Content ideas:",
                ideas,
                "Drafts:",
                drafts,
                "Downloaded image assets available for design:",
                asset_list,
                "Create the JSON carousel plan now.",
            ]
        ),
    )

    plan = extract_json_plan(raw_plan)
    rendered_paths = render_carousel(plan, asset_paths)
    image_concept_paths = generate_image_concepts(plan, asset_paths) if IMAGE_CONCEPTS_ENABLED else {}
    brief = "\n".join(
        [
            f"# {plan.get('title', 'Visual Carousel')}",
            "",
            f"Platform: {plan.get('platform', 'Instagram')}",
            f"Format: {plan.get('format', 'carousel')}",
            f"Approval status: {plan.get('approval_status', 'Draft')}",
            "",
            "## Asset Strategy",
            plan.get("asset_strategy", "Use selected raw assets as source material."),
            "",
            "## Rendered Slides",
            *[f"- {path}" for path in rendered_paths],
            "",
            "## OpenAI Image Concepts",
            *[f"- {key}: {value}" for key, value in image_concept_paths.items()],
            "",
            "## Caption",
            plan.get("caption", ""),
        ]
    )
    brief_path = save_markdown("visual_content", "visual-carousel-brief", brief)

    return {
        "visual_brief": str(brief_path),
        "visual_slides": ", ".join(str(path) for path in rendered_paths),
        **image_concept_paths,
    }


async def run_daily_workflow() -> dict[str, str]:
    asset_inventory = GoogleDriveService().get_asset_inventory()
    asset_inventory_path = save_markdown(
        "asset_inventory",
        "asset-inventory",
        build_asset_inventory_markdown(asset_inventory.summary),
    )
    paths = {"asset_inventory": str(asset_inventory_path)}
    shared_context = build_shared_context(asset_inventory.summary)

    ideas = await run_agent(
        content_strategist_agent,
        f"{shared_context}\n\nGenerate today's seven content ideas.",
    )
    paths["ideas"] = str(save_markdown("content_ideas", "content-ideas", ideas))

    candidates = await run_agent(
        content_candidate_agent,
        "\n\n".join(
            [
                shared_context,
                "Create seven Instagram content candidates for the next publishing cycle.",
                "Use only exact filenames from the Raw Content creative sorting section.",
                "Favor real raw content selections over abstract concepts.",
                "Include a mix aligned to the weekly rhythm: Reels, carousels/feed posts, stories, and one deeper concept/process post.",
                "Respect product rotation memory: avoid over-featuring the same product family when other product folders have not had a turn.",
            ]
        ),
    )
    paths["content_candidates"] = str(save_markdown("content_candidates", "content-candidates", candidates))

    drafts = await run_agent(
        content_creator_agent,
        f"{shared_context}\n\nContent ideas:\n{ideas}\n\nAsset-based content candidates:\n{candidates}\n\nDraft three captions, three short video scripts, and one carousel concept from the candidates. Use only the named source files.",
    )
    paths["drafts"] = str(save_markdown("content_drafts", "content-drafts", drafts))

    seo = await run_agent(
        seo_agent,
        f"{shared_context}\n\nCreate three SEO improvements and one organic content idea for the website.",
    )
    paths["seo"] = str(save_markdown("seo", "seo-recommendations", seo))

    analytics = await run_agent(
        analytics_agent,
        f"{shared_context}\n\nAnalyze available performance data. If none is available, define the minimum tracking setup for tomorrow.",
    )
    paths["analytics"] = str(save_markdown("analytics", "analytics-notes", analytics))

    ad_concepts = await run_agent(
        ad_strategist_agent,
        "\n\n".join(
            [
                shared_context,
                "Content ideas:",
                ideas,
                "Analytics notes:",
                analytics,
                "Create Phase 2 paid ad readiness notes. Only draft ad concepts if the available evidence supports them.",
            ]
        ),
    )
    paths["ad_concepts"] = str(save_markdown("ad_concepts", "ad-concepts", ad_concepts))

    visual_paths = await generate_visual_content(shared_context, ideas, drafts)
    paths.update(visual_paths)

    report = await run_agent(
        orchestrator_agent,
        "\n\n".join(
            [
                shared_context,
                "Content ideas:",
                ideas,
                "Asset-based content candidates:",
                candidates,
                "Drafts:",
                drafts,
                "SEO recommendations:",
                seo,
                "Analytics notes:",
                analytics,
                "Future ad strategist notes:",
                ad_concepts,
                "Visual content outputs:",
                "\n".join(f"{key}: {value}" for key, value in visual_paths.items()) or "No visual content generated.",
                "Compile the final daily growth report.",
            ]
        ),
    )
    paths["report"] = str(save_markdown("daily_reports", "daily-growth-report", report))

    return paths


def main() -> None:
    try:
        paths = asyncio.run(run_daily_workflow())
    except AuthenticationError as exc:
        raise SystemExit(
            "OpenAI authentication failed. Check that OPENAI_API_KEY is set in .env and belongs to an active API project."
        ) from exc
    except RateLimitError as exc:
        raise SystemExit(
            "OpenAI quota/rate limit failed. Check platform billing, project credits, and usage limits, then rerun the workflow."
        ) from exc
    except OpenAIError as exc:
        raise SystemExit(f"OpenAI request failed: {exc}") from exc

    print("Daily growth workflow complete.")
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
