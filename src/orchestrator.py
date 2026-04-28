import asyncio
from datetime import date

from .agents import (
    analytics_agent,
    content_creator_agent,
    content_strategist_agent,
    orchestrator_agent,
    run_agent,
    seo_agent,
)
from .drive_service import GoogleDriveService
from .file_store import read_text, save_markdown
from .settings import BRAND_CONTEXT_DIR, BRAND_WEBSITE_URL
from .web import fetch_website_summary


def build_shared_context() -> str:
    brand_brief = read_text(BRAND_CONTEXT_DIR / "brand_brief.md")
    asset_inventory = GoogleDriveService().get_asset_inventory().summary
    website_summary = fetch_website_summary(BRAND_WEBSITE_URL)

    return "\n\n".join(
        [
            f"Date: {date.today().isoformat()}",
            "Brand brief:",
            brand_brief,
            "Raw asset inventory:",
            asset_inventory,
            "Website summary:",
            website_summary,
        ]
    )


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

    return paths


def main() -> None:
    paths = asyncio.run(run_daily_workflow())
    print("Daily growth workflow complete.")
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
