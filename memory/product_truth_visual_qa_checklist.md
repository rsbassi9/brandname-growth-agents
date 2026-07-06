# Product Truth And Visual QA Checklist

Last updated: 2026-05-19

## Priority 1 - Product Truth Layer

Checklist:
- [x] Generate product profiles from Drive product folders.
- [x] Classify front, back, detail, folded/texture, and hero reference files.
- [x] Store strict placement requirements for logos, graphics, trims, hems, grommets, silhouette, and wash.
- [x] Surface product truth in Builder.

## Priority 2 - Product Accuracy Prompt Builder

Checklist:
- [x] Inject product truth into every model-shoot and product visual prompt.
- [x] Treat selected product folders as constraints, not mood references.
- [x] Preserve front logo/mark and back graphic placement.

## Priority 3 - Visual QA Agent

Checklist:
- [x] QA each generated image against product truth and reference files.
- [x] Persist QA result on the generated concept.
- [x] Mark images Pass, Needs Iteration, Needs Review, or Reject.

## Priority 4 - Iteration With QA Fixes

Checklist:
- [x] Add Builder action to iterate using the latest QA fix list.
- [x] Pass product truth and QA failures into the iteration prompt.
- [x] Save the new generated image and QA result.

## Priority 5 - Dashboard Warnings

Checklist:
- [x] Add product accuracy warnings to calendar/feed strategy.
- [x] Warn when product posts or model visuals have no verified accurate visual.

## Verification

Checklist:
- [x] Python compile passes.
- [x] Dashboard JavaScript syntax check passes.
- [x] Product truth API returns profiles.
- [x] Visual QA endpoint returns and persists QA.
- [x] Builder shows Product Truth and Visual QA controls.
