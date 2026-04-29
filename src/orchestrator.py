import asyncio
from datetime import date

from openai import AuthenticationError, OpenAIError, RateLimitError

from .agents import (
    analytics_agent,
    content_creator_agent,
    content_strategist_agent,
    orchestrator_agent,
    run_agent,
    seo_agent,
    visual_designer_agent,
)
from .drive_service import GoogleDriveService
from .file_store import read_text, save_markdown
from .image_concepts import generate_image_concepts
from .learning import feedback_summary
from .settings import (
    BRAND_CONTEXT_DIR,
    BRAND_WEBSITE_URL,
    IMAGE_CONCEPTS_ENABLED,
    ROOT_DIR,
    VISUAL_ASSET_LIMIT,
    VISUAL_OUTPUT_ENABLED,
)
from .visual_renderer import extract_json_plan, render_carousel
from .web import fetch_website_summary


def build_shared_context() -> str:
    brand_brief = read_text(BRAND_CONTEXT_DIR / "brand_brief.md")
    growth_strategy = read_text(BRAND_CONTEXT_DIR / "growth_strategy.md")
    visual_system = read_text(BRAND_CONTEXT_DIR / "visual_system.md")
    asset_inventory = GoogleDriveService().get_asset_inventory().summary
    website_summary = fetch_website_summary(BRAND_WEBSITE_URL)
    learning_context = feedback_summary()

    return "\n\n".join(
        [
            f"Date: {date.today().isoformat()}",
            "Brand brief:",
            brand_brief,
            "Growth strategy:",
            growth_strategy,
            "Visual system:",
            visual_system,
            "Learning loop feedback:",
            learning_context,
            "Raw asset inventory:",
            asset_inventory,
            "Website summary:",
            website_summary,
        ]
    )


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
    shared_context = build_shared_context()

    ideas = await run_agent(
        content_strategist_agent,
        f"{shared_context}\n\nGenerate today's seven content ideas.",
    )
    drafts = await run_agent(
        content_creator_agent,
        f"{shared_context}\n\nApproved idea input for drafting:\n{ideas}\n\nDraft three captions, three short video scripts, and one carousel concept.",
    )
    seo = await run_agent(
        seo_agent,
        f"{shared_context}\n\nCreate three SEO improvements and one organic content idea for the website.",
    )
    analytics = await run_agent(
        analytics_agent,
        f"{shared_context}\n\nAnalyze available performance data. If none is available, define the minimum tracking setup for tomorrow.",
    )
    visual_paths = await generate_visual_content(shared_context, ideas, drafts)

    report = await run_agent(
        orchestrator_agent,
        "\n\n".join(
            [
                shared_context,
                "Content ideas:",
                ideas,
                "Drafts:",
                drafts,
                "SEO recommendations:",
                seo,
                "Analytics notes:",
                analytics,
                "Visual content outputs:",
                "\n".join(f"{key}: {value}" for key, value in visual_paths.items()) or "No visual content generated.",
                "Compile the final daily growth report.",
            ]
        ),
    )

    paths = {
        "ideas": str(save_markdown("content_ideas", "content-ideas", ideas)),
        "drafts": str(save_markdown("content_drafts", "content-drafts", drafts)),
        "seo": str(save_markdown("seo", "seo-recommendations", seo)),
        "analytics": str(save_markdown("analytics", "analytics-notes", analytics)),
        "report": str(save_markdown("daily_reports", "daily-growth-report", report)),
    }
    paths.update(visual_paths)

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
