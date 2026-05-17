# Quality Scoring And Shoot Loop Checklist

Last updated: 2026-05-17

## Priority 1 - Post Quality Scoring

Status: Complete.

Checklist:
- [x] Score every calendar item for product clarity, brand fit, visual freshness, feed rhythm, duplicate risk, commercial usefulness, and designed-vs-raw quality.
- [x] Store the score on each calendar item.
- [x] Surface the score in Builder/Calendar/Feed.

## Priority 2 - Needs Work Queue

Checklist:
- [x] Automatically classify weak or incomplete posts into needs-work reasons.
- [x] Show a queue of posts that need design, caption, image, product rotation, or shoot support.
- [x] Keep the queue actionable from the dashboard.

## Priority 3 - Shoot Planner To Calendar Loop

Checklist:
- [x] Convert shoot gaps into placeholder calendar posts.
- [x] Mark placeholders clearly as missing-real-asset requests.
- [x] Attach crop, mood, product, lighting, and use-case requirements.
- [x] Let placeholders occupy the feed/calendar so the curator can plan around missing shots.

## Priority 4 - AI Reference Attachment

Checklist:
- [x] Placeholder posts can store AI reference image paths.
- [x] AI references open directly from the placeholder post.
- [x] AI references remain planning references, not final approved posts.

## Priority 5 - Campaign Brief Object

Checklist:
- [x] Add campaign brief fields that summarize current drop goal, story beats, product priorities, visual motifs, and avoid list.
- [x] Feed campaign brief into future agent runs.

## Priority 6 - Feed Row Objectives

Checklist:
- [x] Generate row-by-row objectives for the current feed.
- [x] Use row objectives in curator context.
- [x] Display row objectives compactly.

## Priority 7 - Before / After Learning

Checklist:
- [x] Preserve original version and final user-edited version for calendar edits.
- [x] Summarize what changed for future agents.

## Verification

Checklist:
- [x] Python compile passes.
- [x] Dashboard JavaScript syntax check passes.
- [x] Quality scoring API returns scores and needs-work items.
- [x] Shoot placeholder API creates a calendar item.
- [x] Dashboard loads the new panels/actions.
