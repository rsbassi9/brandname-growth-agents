# User Guide

Updated: 2026-07-13

This guide explains how to use each section of the BRAND NAME Growth Studio. The app is designed for review-ready marketing work: generate assets, organize campaigns, plan manual publishing, learn from performance, and prepare SEO/ad/repurposing drafts without auto-publishing or spending ad budget.

## Global Controls

### Navigation

Use the left sidebar to move between:

- Playground
- Campaigns
- Library
- Calendar
- Feed Grid
- Ads & SEO
- Strategy Hub
- System

On small screens, use the menu button in the top bar to open or close navigation.

### Jobs Drawer

Use the `Jobs` button in the top right whenever you start a generation, workflow, audit, render, or scheduled job.

The drawer is where you check:

- Whether a job is queued, running, succeeded, or failed.
- Progress messages.
- Whether a newly generated asset/version is ready to inspect in Library or Strategy Hub.

If a job fails, treat the failed message as the first debugging clue. Most generated work is saved as draft assets only after a job succeeds.

### Premium Model Toggle

Use `Premium model` when you want live provider generation to prefer the configured premium model. Leave it off for ordinary drafts and local-only dry runs.

This toggle matters only when provider mode is configured. If the top bar says `Local only`, paid/provider calls are blocked and deterministic local paths are used.

### Local Only / Provider Ready Badge

- `Local only`: safe dry-run mode. The app avoids paid/provider calls.
- `Provider ready`: live providers may be used if credentials and base URLs are configured.

For review/testing, prefer local-only mode. For production-quality generation, switch only after provider credentials are intentionally configured.

## Playground

Use Playground for one-off generation and experimentation.

Typical uses:

- Draft captions, hooks, product copy, carousel copy, video scripts, and voiceover scripts.
- Generate image-concept prompt packs grounded in brand/source context.
- Test how Brand Brain memory affects output.
- Quickly create a draft asset without starting a full campaign.

How to use it:

1. Pick an asset type.
2. Write a clear brief.
3. Add optional campaign/source references when relevant.
4. Start generation.
5. Watch the Jobs drawer.
6. Review the completed result and memory-used disclosure.

Good briefs include:

- Product or campaign name.
- Target channel.
- What source material or proof should be emphasized.
- Desired output format.
- Any phrases or claims to avoid.

After generating, inspect the asset in Library if you want to compare versions, select a winner, critique, iterate, or create a video prompt pack.

## Campaigns

Use Campaigns to group work around a drop, launch, product push, seasonal story, or ad/SEO initiative.

Typical uses:

- Create a campaign container before generating related assets.
- See all assets attached to a campaign.
- Jump from a campaign into Playground with the campaign prefilled.
- Keep multi-asset work organized instead of scattering drafts across Library.

How to use it:

1. Create a campaign with a name and goal.
2. Open the campaign.
3. Use generation shortcuts to create assets tied to that campaign.
4. Review campaign assets as they accumulate.

Use Campaigns when multiple pieces belong together. Use Playground directly for isolated drafts.

## Library

Use Library as the source of truth for generated assets and indexed source photos.

### Generated Assets

Use this tab to:

- Filter by asset type, status, campaign, date, or search text.
- Open an asset detail drawer.
- Review immutable versions.
- Select the strongest version.
- Regenerate from the latest version.
- Critique and iterate a version.
- Create video prompt packs from selected copy/assets.

Recommended workflow:

1. Generate in Playground, Campaigns, Ads & SEO, Strategy Hub, or a scheduled job.
2. Open Library.
3. Filter to the relevant type/status/campaign.
4. Review versions.
5. Select the best version.
6. Use selected versions as the material you manually publish or repurpose.

Asset statuses:

- `draft`: still being reviewed or waiting for scheduling.
- `selected`: chosen as the current best take.
- `archived`: not active.

### Source Photos

Use this tab to index and browse source assets from local folders, Google Drive, or Shopify/read-only inventory.

Source photos are important because generation is intended to stay grounded in real photoshoots and product truth.

Use source photos when:

- Generating source-grounded copy or prompt packs.
- Starting a repurpose shoot.
- Keeping product-linked content connected to actual material.

## Calendar

Use Calendar to plan manual publishing work.

The calendar supports month and week planning. The week view is where most hands-on scheduling happens.

Typical uses:

- Move planned items between days.
- Drag draft assets from the unscheduled tray onto a day.
- Use best-time suggestions when performance data qualifies.
- See soft guardrail warnings for over-scheduling or duplicate asset use.

How to use it:

1. Open Calendar.
2. Switch to week view for detailed planning.
3. Review scheduled items and unscheduled draft assets.
4. Drag an item to a day or use the date fallback.
5. Watch for warning banners.
6. Reload or revisit later to confirm persistence.

Important: Calendar is a planning surface. It does not publish to Instagram, TikTok, Facebook, email, Shopify, or Meta Ads automatically.

## Feed Grid

Use Feed Grid to arrange and review manual publishing order.

Typical uses:

- Reorder planned feed items.
- Preview sequence and rhythm.
- Keep visual/content order coherent before manual posting.

How to use it:

1. Open Feed Grid.
2. Review current feed items.
3. Reorder items as needed.
4. Save/persist the order.

Use Feed Grid after Calendar planning, when the exact sequence matters.

## Ads & SEO

Use Ads & SEO for paid-social briefs and read-only Shopify SEO preparation.

### Ads

Use the Ads tab to create structured `ad_brief` assets.

Typical uses:

- Generate Meta Ads Manager-ready copy blocks.
- Prepare campaign angle, audience, creative notes, hooks, and CTAs.
- Keep ad work as reviewable assets in Library.

Important: The app does not connect to Meta Ads Manager and does not spend ad budget. Copy blocks are for manual entry.

### SEO

Use the SEO tab for read-only catalog audits and paste-ready fixes.

Typical uses:

- Run a Shopify SEO audit.
- Review product scores and issue chips.
- Generate `seo_fix` assets for specific audit rows.
- Generate an `seo_plan` with keyword maps, blog outlines, and internal links.

Recommended workflow:

1. Generate or refresh the SEO keyword/content plan.
2. Run the catalog audit.
3. Review scores and issues.
4. Generate fixes for priority products.
5. Copy fixes manually into Shopify after review.

Important: Shopify writes are disabled by default. Keep `SHOPIFY_WRITE_ENABLED=false` unless a future write workflow is explicitly designed and reviewed.

## Strategy Hub

Use Strategy Hub as the operating center for context, planning, manual shipping, learning, and standups.

Strategy Hub has five lanes.

### Know

Use Know to read brand context and Brand Brain profile versions.

Typical uses:

- Review current strategy/context documents.
- Inspect the latest distilled brand profile.
- Compare profile history.
- Understand what evidence the system is using to guide generation.

Use Know before major campaign work, especially if outputs feel off-brand.

### Plan

Use Plan to view calendar work from inside the Strategy Hub.

Typical uses:

- Check upcoming planned items.
- Confirm what is already scheduled.
- Move from strategic review into Calendar if changes are needed.

Use Plan for a quick strategy-level look. Use Calendar for detailed scheduling.

### Build

Use Build to inspect draft assets ready for review.

Typical uses:

- Browse draft assets without leaving Strategy Hub.
- Pick assets for manual shipping.
- Move from planning into concrete draft review.

If you need version comparison or source-photo inspection, use Library.

### Ship Manually

Use Ship Manually as a manual publishing checklist.

Typical uses:

- Select a draft asset.
- Copy caption/content text.
- Confirm file path/reference.
- Prepare the item for manual posting outside the app.

Important: This lane supports manual publishing. It does not auto-post.

### Learn

Learn has two internal tabs: Standup and Performance.

#### Standup

Use Standup to review weekly operating summaries.

A standup report includes:

- What published that week.
- Top performer.
- Bottom performer.
- Next week's plan.
- Exactly three agent recommendations grounded in Brand Brain and metrics.

Each recommendation has `Add to Calendar as Draft`. This creates an unscheduled draft asset that appears in the draft tray. It does not automatically schedule or publish it.

Recommended workflow:

1. Run or wait for the weekly standup job.
2. Open Strategy Hub -> Learn -> Standup.
3. Read the report.
4. Choose useful recommendations.
5. Add them as drafts.
6. Drag them onto Calendar only after review.

#### Performance

Use Performance to import social performance data and teach the system what worked.

Typical uses:

- Upload or paste Meta Business Suite / TikTok Studio CSV exports.
- View top posts.
- Review weekly engagement-rate trends.
- Review performance by asset type.
- Link imported posts to calendar items.
- Submit feedback into the learning loop.

Recommended workflow:

1. Export content performance CSV from Meta Business Suite or TikTok Studio.
2. Open Strategy Hub -> Learn -> Performance.
3. Upload or paste the CSV.
4. Confirm detected metrics.
5. Link posts to calendar items when needed.
6. Review top posts and trends.
7. Add feedback when a draft/output should influence future work.

Metric insights are written into Brand Brain so future generations can learn from real performance.

## System

Use System for runtime configuration and manual job controls.

Typical uses:

- Check local-only/provider mode.
- Configure daily workflow cadence.
- Configure brand profile distillation cadence.
- Configure recycling cadence.
- Configure weekly standup cadence.
- Configure calendar guardrails.
- Trigger manual workflow runs.

Cadence settings are stored in the database and are off by default unless explicitly enabled.

Recommended defaults:

- Keep local-only mode for dry runs.
- Enable brand profile distillation weekly only after feedback and selected versions are meaningful.
- Enable recycling monthly only after importing enough performance data.
- Enable weekly standup when Calendar and performance imports are part of the operating rhythm.
- Keep calendar guardrails conservative until the posting rhythm is stable.

## Repurposing Pipeline

The repurpose shoot pipeline is API/job-driven and appears through the generated campaign/assets it creates.

It takes 1-10 indexed `source_assets` and creates:

- Post copy.
- Reel/video script.
- Story set copy.
- Meta ad brief.
- Product-page SEO refresh when a product handle is linked.

Completed child assets are preserved even if one step fails. Failed repurpose child draft assets can be retried individually through the repurpose retry endpoint.

Use this pipeline when you have a real photoshoot or source batch and want a full campaign draft set from it.

## Brand Brain

Brand Brain is the app's memory layer.

It indexes:

- Generated asset versions.
- Feedback events.
- Read-only product/catalog context.
- Strategy context files.
- Metric insights from imported performance data.

Generation uses Brand Brain to prepend auditable memory evidence to prompts. The UI shows memory-used metadata where relevant.

Useful operator actions:

```powershell
python -m app.services.brain backfill
python -m app.services.jobs distill_brand_profile
```

Run backfill after importing or migrating meaningful data. Run profile distillation when there is enough selected-vs-unselected output and feedback to learn from.

## Suggested Operating Rhythm

Daily:

- Use Calendar to review planned work.
- Use Playground or Campaigns for needed drafts.
- Use Library to select/refine versions.
- Use Ship Manually when ready to post.

Weekly:

- Import performance CSVs.
- Review Strategy Hub -> Learn -> Performance.
- Run/review Weekly Standup.
- Add useful standup recommendations as drafts.
- Adjust next week's Calendar.

Monthly:

- Run recycling for older top-quartile posts.
- Review SEO audit and generate fixes for priority products.
- Review Brand Brain profile history for drift or useful new patterns.

Before Any Merge Or Deployment:

- Run backend tests.
- Run frontend tests/type-check/build.
- Run the UI token scan.
- Check `docs/FINAL_REVIEW.md`.
- Confirm provider credentials and cadence settings are intentional.
