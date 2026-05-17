# Brand Growth Agent Implementation Checklist

Last updated: 2026-05-16

## Priority 1 - Content State And Approval Foundation

Status: Completed initial implementation on 2026-05-16.

Goal: make every object in the system carry a clear lifecycle so agents know what is drafted, approved, rejected, scheduled, posted, measured, and learned from.

Checklist:
- [x] Add shared lifecycle states for posts, highlights, SEO actions, ads actions, and generated visuals.
- [x] Persist approvals, rejections, edits, and reasons in a structured memory file.
- [x] Add approval/rejection controls to Calendar, Feed Grid, Builder, Highlights, SEO, and Ads.
- [x] Add a global "What changed?" history panel for each content item.
- [x] Make agents read this state before suggesting new content.

Implementation notes:
- Added `memory/content_state.json` as the shared lifecycle state file.
- Added `memory/content_state_events.jsonl` as the append-only state change log.
- Added dashboard approval controls for posts, highlights, SEO checklist items, Ads checklist items, and generated output previews.
- Calendar posts and highlights now mirror approved/rejected/review statuses back into their native memory files.
- SEO/Ads checklist items now attach persisted lifecycle state on load.

Why first:
- This supports every other feature.
- It prevents the agents from repeatedly suggesting rejected ideas.
- It gives Shopify/Ads automation a safe approval gate.

Can be tackled with:
- SEO checklist persistence.
- Ads checklist persistence.
- Performance tracking schema.

## Priority 2 - Smarter Highlight Curator

Status: Completed initial implementation on 2026-05-16.

Goal: make profile highlights feel curated, lively, and useful instead of just asset groupings.

Checklist:
- [x] Add "regenerate this highlight" per highlight group.
- [x] Add "regenerate cover only" per highlight.
- [x] Add highlight warnings: too many process frames, missing product frame, missing body/campaign frame, weak cover.
- [x] Add editable title, cover, overlay text, and frame role.
- [x] Add status: Draft, Approved, Needs Cover, Needs Frames.
- [x] Add learning notes so frame swaps teach future highlight suggestions.

Implementation notes:
- Added per-highlight regenerate and regenerate-cover endpoints.
- Added editable highlight title and purpose fields.
- Added editable frame overlay text and frame role.
- Added warning logic for missing frames, weak covers, too many process frames, missing product frames, missing body/campaign frames, and repetitive buckets.
- Highlight frame swaps, text edits, cover regenerations, and full regenerations append edit history for learning.

Why now:
- Highlights are separate from feed/calendar but use the same assets and taste layer.
- This is a fast win before deeper external integrations.

Can be tackled with:
- Content state foundation.
- Visual fingerprint improvements.

## Priority 3 - Visual Intelligence Upgrade

Status: Completed initial implementation on 2026-05-16.

Goal: move from filename/category heuristics toward real art-direction awareness.

Checklist:
- [x] Add image-derived dominant color and brightness analysis for local/generated images.
- [x] Cache image visual metadata in memory.
- [x] Add visual similarity score between neighboring grid posts.
- [x] Add product visibility score.
- [x] Add text-heavy / graphic-heavy / photo-heavy detection.
- [x] Make Visual Watch warnings more precise and actionable.
- [x] Add "suggest swap" for a specific warning, not only "fix all clusters."

Implementation notes:
- Added `memory/visual_metadata.json` as the cache for local/generated image color, brightness, contrast, density, and image-type metadata.
- Added image-derived metadata for generated/local outputs.
- Added visual similarity scores and severity/suggested-action fields to Visual Watch warnings.
- Added product visibility score and content weight fields to visual fingerprints.
- Feed and calendar warning panels now show suggested actions.

Why:
- This directly improves the Feed Curator and Highlight Curator.
- It solves issues like several black/dense posts placed too close together.

Can be tackled with:
- Feed Curator visual-warning loop.
- Photoshoot / Campaign ingestion.

## Priority 4 - Photoshoot / Campaign Asset Integration

Status: Completed initial implementation on 2026-05-16.

Goal: make new photoshoot folders act as premium campaign anchors in feed, highlights, and AI image generation.

Checklist:
- [x] Confirm Drive bucket detection for `Photoshoot / Campaign`.
- [x] Add photoshoot-specific visual roles: hero, full-body, detail, lifestyle, campaign anchor.
- [x] Prefer photoshoot assets for feed breathing room and highlight covers.
- [x] Add shoot-folder summaries once files are uploaded.
- [x] Add "photoshoot gap" warnings: need bright body shot, product detail, motion, cover crop, etc.

Implementation notes:
- `Photoshoot / Campaign` is a first-class Drive bucket.
- Asset inventory now includes a Photoshoot / Campaign summary by folder.
- Highlight frames now assign campaign-specific roles like campaign cover, campaign anchor, full-body campaign, and campaign detail.
- Feed/calendar strategy now warns when the next grid lacks enough campaign/body anchors.

Why:
- Once photos are uploaded, this becomes the highest-quality visual material.

Can be tackled with:
- Visual intelligence upgrade.
- Shoot Planner Agent.

## Priority 5 - SEO Checklist Persistence And Shopify Preview

Status: Completed initial implementation on 2026-05-16.

Goal: turn SEO markdown into an approval workflow before making store changes.

Checklist:
- [x] Persist SEO checklist item status: Needs Review, Approved, Rejected, Applied.
- [x] Allow editing proposed SEO text inline.
- [x] Show current Shopify value next to proposed value.
- [x] Add item types: product title, meta title, meta description, product description, image alt text, collection copy, homepage copy.
- [x] Add read-only Shopify Admin API connection first.
- [x] Add approved-only apply action after preview is reliable.

Implementation notes:
- SEO checklist IDs are now stable per source report.
- Inline SEO edits save into lifecycle memory with item status and action type.
- The SEO page shows a read-only Shopify preview panel for each item.
- Shopify preview stays safe when credentials are missing and reports the missing `.env` keys instead of blocking the dashboard.
- Apply actions remain disabled until the read-only preview and approval flow are reliable.

Required later:
- Shopify store domain.
- Shopify Admin API access token.
- Scopes likely needed: product read/write, collection read/write, file/media read depending on alt text/media work, theme read/write only if editing theme copy.

Can be tackled with:
- Content state foundation.
- Product Merchandising Agent.

## Priority 6 - Ads Checklist Persistence And Readiness Workflow

Status: Completed initial implementation on 2026-05-16.

Goal: keep ads safe and strategic before touching ad accounts.

Checklist:
- [x] Persist ad checklist item status.
- [x] Add ad readiness score: creative ready, product match, landing page ready, proof available, budget risk.
- [x] Add required creative list per ad angle.
- [x] Add copy variants and CTA variants.
- [x] Map ad concept to Shopify product/page.
- [x] Keep "apply/launch" disabled until approval and platform credentials are intentionally added.

Implementation notes:
- Ads checklist items now share the same saved edit/status flow as SEO items.
- Each ad item shows readiness score, missing checks, required creative, copy variants, CTA variants, and mapped destination.
- Launch/apply controls remain disabled and explicitly locked until approval and platform credentials are added.

Why:
- Ads need stricter permission and budget controls.
- Early value is in readiness and creative planning, not auto-launching.

Can be tackled with:
- SEO checklist persistence.
- Performance Analyst Agent.

## Priority 7 - Performance Feedback Loop

Status: Completed initial implementation on 2026-05-16.

Goal: make agents learn from what actually works.

Checklist:
- [x] Add posted content records.
- [x] Track platform, post URL, posted date, format, assets, product family, caption, hook.
- [x] Add manual metric entry first: reach, saves, shares, follows, profile visits, clicks, orders.
- [x] Later integrate Instagram/Meta and Shopify metrics.
- [x] Feed performance summaries into content candidates, curator, highlights, SEO, and ads.

Implementation notes:
- Added `memory/performance_records.json` as the manual performance memory.
- Added a Performance dashboard tab with scheduled post records, post URL/date fields, metric inputs, and notes.
- Saving metrics marks posts as Posted or Measured in lifecycle memory.
- Performance summaries are shown in the Calendar strategy and included in shared agent context for future runs.
- Platform API integrations remain intentionally manual until permissions are added.

Why:
- This is where the product becomes a learning system instead of a content organizer.

Can be tackled with:
- Content state foundation.
- Ads readiness.

## Priority 8 - Creative Brief Memory

Status: Completed initial implementation on 2026-05-16.

Goal: provide one editable steering note that affects all agents.

Checklist:
- [x] Add dashboard page or panel for current brand direction.
- [x] Fields: current drop focus, products to push, products to pause, tone, visual references, avoid list, seasonal direction.
- [x] Feed this into all agent prompts.
- [x] Add timestamped revisions.

Implementation notes:
- Added `memory/creative_brief.json` as the editable creative steering memory.
- Added a Direction tab with all requested steering fields and revision notes.
- Shared agent context now includes the current creative steering brief before generation.

Why:
- Gives you fast control over the whole system without editing multiple files.

Can be tackled with:
- Any agent prompt improvement work.

## Priority 9 - Shoot Planner Agent

Status: Completed initial implementation on 2026-05-16.

Goal: turn feed/highlight/content gaps into a practical photoshoot brief.

Checklist:
- [x] Use Visual Watch, product rotation, highlight warnings, and product gaps.
- [x] Generate shot list: product, angle, crop, mood, background, lighting, use case.
- [x] Suggest priority: must shoot, nice to have, optional.
- [x] Link each shot request to the post/highlight/feed gap it solves.

Implementation notes:
- Added a Shoot Planner dashboard tab and `/api/shoot-plan`.
- The planner creates Must Shoot, Nice To Have, and Optional requests.
- Each shot request includes product, angle, crop, mood, background, lighting, use case, and the gap it solves.
- Current signals include photoshoot gaps, visual rhythm warnings, highlight needs, repeated products, and underused products.

Why:
- This turns the dashboard into a real creative production planner.

Can be tackled with:
- Photoshoot / Campaign integration.
- Visual intelligence upgrade.

## Priority 10 - Product Merchandising Agent

Status: Completed initial implementation on 2026-05-16.

Goal: decide what products deserve attention next.

Checklist:
- [x] Read product catalog and Drive product assets.
- [x] Later read inventory/sales from Shopify.
- [x] Suggest product rotation based on freshness, content gaps, season, stock, and performance.
- [x] Warn when the feed overuses one product.

Implementation notes:
- Added a Product Merchandising dashboard tab and `/api/merchandising`.
- The plan compares Drive product families, current calendar product mix, performance product mix, and read-only Shopify preview state.
- Products are grouped into Push, Pause, and Maintain recommendations with next actions.
- Shopify stock/sales-aware merchandising remains pending until Shopify credentials and scopes are configured.

Why:
- Prevents the brand from looking visually repetitive and helps commercial priorities stay visible.

Can be tackled with:
- Shopify read-only integration.
- Product rotation.

## Priority 11 - Shopify SEO Execution Agent

Status: Completed initial implementation on 2026-05-16.

Goal: safely apply approved SEO changes to Shopify.

Checklist:
- [x] Read current Shopify product/collection/page fields.
- [x] Convert approved checklist item into exact API mutation/update.
- [x] Show before/after diff.
- [x] Apply only approved items.
- [x] Log applied changes.
- [x] Add rollback note where possible.

Implementation notes:
- Added gated Shopify SEO execution endpoint `/api/shopify/seo-actions/apply`.
- The SEO page has an Apply Approved SEO action that checks only Approved SEO checklist items.
- Writes are blocked unless Shopify is connected and `SHOPIFY_WRITE_ENABLED=true`.
- Product title, product description, meta title, and meta description can be converted into Shopify product updates.
- Each attempt is logged to `memory/shopify_seo_changes.jsonl`; successful writes include before/after and rollback note.

Why:
- This is useful only after the checklist approval flow is stable.

Can be tackled with:
- SEO checklist persistence.
- Shopify preview.

## Priority 12 - Drop Launch Agent

Status: Completed initial implementation on 2026-05-16.

Goal: coordinate campaigns around a product/drop.

Checklist:
- [x] Generate launch sequence: teaser, source story, product reveal, model shot, detail post, Reel, story highlight, SEO update, email/social copy.
- [x] Connect calendar, feed, highlights, SEO, ads, and shoot planner.
- [x] Track readiness by channel.

Implementation notes:
- Added a Drop Launch dashboard tab and `/api/drop-launch`.
- Launch sequence now coordinates teaser, source story, product reveal, body proof, detail/process, Reel/motion, highlights, SEO, and Ads readiness.
- Readiness tracks calendar posts, approved posts, highlights, SEO approvals, ad readiness, shoot gaps, and product push needs.
- Blockers call out approval, shoot, and SEO gaps before a launch is treated as ready.

Why:
- This becomes powerful once the core surfaces are stable.

Can be tackled with:
- Creative brief memory.
- Performance feedback loop.

## Priority 13 - Community / DM FAQ Agent

Status: Completed initial implementation on 2026-05-16.

Goal: turn repeated questions into useful content and highlights.

Checklist:
- [x] Build Q&A highlights.
- [x] Draft sizing, shipping, drop, process, and product replies.
- [x] Create story stickers/Q&A prompts.
- [x] Later ingest comments/DM themes manually or through platform APIs.

Implementation notes:
- Added a Community / FAQ dashboard tab and `/api/community-faq`.
- Generates sizing, shipping, drop, process, and product replies.
- Suggests story prompts and practical highlight groups.
- Comment/DM ingestion remains manual until platform permissions are added.

Why:
- Useful for brand clarity and conversion, but lower priority than core content and store workflows.

Can be tackled with:
- Highlight Curator.
- Shopify product context.

## Priority 14 - Email / SMS Agent

Status: Completed initial implementation on 2026-05-16.

Goal: reuse approved content and product context for owned-channel marketing.

Checklist:
- [x] Draft drop emails from approved calendar/highlight/product content.
- [x] Create subject lines, preview text, and sections.
- [x] Later connect Klaviyo/Mailchimp/etc. only after approval flow is proven.

Implementation notes:
- Added an Email / SMS dashboard tab and `/api/email-sms`.
- Generates subject lines, preview text, basic email sections, SMS drafts, and source post references from current content, launch, and merchandising state.
- ESP integrations remain intentionally future gated.

Why:
- Valuable after product/state/performance data is cleaner.

Can be tackled with:
- Drop Launch Agent.
- Shopify product context.

## Priority 15 - Automation Schedule

Status: Completed initial implementation on 2026-05-16.

Goal: make the system run on a dependable rhythm without removing user approval.

Checklist:
- [x] Add daily/weekly run presets.
- [x] Add "agents finished" notification.
- [x] Add review popup after run completion.
- [x] Add scheduled curator refresh.
- [x] Add automation logs.
- [x] Keep all external changes approval-gated.

Implementation notes:
- Added an Automation dashboard tab and `/api/automation`.
- Supports Manual, Daily Review, and Weekly Planning presets.
- Automation config persists to `memory/automation_schedule.json`.
- Agent run completion and automation config changes log to `memory/automation_log.jsonl`.
- Existing run notice and review popup remain the approval checkpoint after agents finish.
- External changes remain explicitly approval-gated.

Why:
- Best added once the state model is stable enough to avoid automated clutter.

Can be tackled with:
- Content state foundation.
- SEO/Ads checklist persistence.
