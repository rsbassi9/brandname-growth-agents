# Builder Slot And Design Surface Checklist

Last updated: 2026-05-16

## Priority 1 - Builder Slide Slot System

Status: Complete.

Checklist:
- [x] Treat visual sets as individual editable slide/frame slots.
- [x] Clicking a slot changes the main Builder preview.
- [x] Visual-group slides are preferred over raw source names when the post has rendered slides.

## Priority 2 - Hot Swap From Drive

Status: Complete.

Checklist:
- [x] Replacing from the Drive asset library updates only the active slot.
- [x] Slot updates are persisted on the calendar item.
- [x] Calendar/feed metadata is recalculated after slot changes.

## Priority 3 - Per-Slide Notes

Status: Complete.

Checklist:
- [x] Active slot has role, overlay text, and notes fields.
- [x] Slot changes are logged into edit history.
- [x] Slot roles can teach the curator what the image is doing.

## Priority 4 - Asset Role Taxonomy

Status: Complete.

Checklist:
- [x] Assets receive designRoles such as text_backdrop, texture_backdrop, feed_breaker, transition_slide, canvas_surface, hero_product, on_body, and campaign_anchor.
- [x] Manual role overrides are supported in `brand_context/asset_tags.csv`.
- [x] Builder library includes Text Backdrops and Feed Breakers filters.

## Priority 5 - Backdrop / Surface Scoring

Status: Complete.

Checklist:
- [x] Product mockups, folded cloth, texture/detail files, and canvas/source files are scored as design surfaces.
- [x] Strategy exposes top design_surface_candidates.
- [x] Campaign Memory can convert these into visual needs.

## Priority 6 - Curator Design Intuition

Status: Complete.

Checklist:
- [x] Feed Curator prompt explains how to use design surfaces for breathing room.
- [x] Content Candidate prompt explains when to use product/detail files as backdrops.
- [x] Run Today receives design-surface context.

## Verification

Checklist:
- [x] Python compile passed.
- [x] Dashboard JavaScript syntax check passed.
- [x] `/api/calendar` returns visual_slots for rendered slide sets.
- [x] `/api/calendar/{item_id}/slots/{slot_index}` saves slot-level edits.
- [x] `/api/calendar` returns design_surface_candidates.
