# Creative Composition And AI Image Visibility Checklist

Last updated: 2026-05-17

## Priority 1 - Creative Composition Agent

Status: Complete.

Checklist:
- [x] Add a creative/art-direction layer for individual posts.
- [x] Give it post context, selected assets, product folder context, visual slots, curator strategy, and design-role metadata.
- [x] Make it produce a premium composition plan, not only raw asset selection.

## Priority 2 - Premium Product / Text Post Design

Checklist:
- [x] Product posts should identify hero, backdrop, detail, transition, and CTA roles.
- [x] Text posts should prefer folded textile, canvas, garment texture, or clean negative-space surfaces where available.
- [x] Product posts should avoid feeling like raw mockups were simply dropped in.

## Priority 3 - Folded Textile / Surface Preference

Checklist:
- [x] Prefer high-scoring text_backdrop, texture_backdrop, canvas_surface, feed_breaker, and transition_slide assets for backdrop slots.
- [x] Product posts such as May 18 and May 21 should surface folded/detail/mockup assets when they exist.

## Priority 4 - Builder Improve Design Flow

Checklist:
- [x] Add an Improve Design action in Builder.
- [x] Save composition plan to the calendar item.
- [x] Expose editable composition notes, slide roles, and design direction.
- [x] Let the user reprompt the creative direction.

## Priority 5 - AI Image Routing By Request Type

Checklist:
- [x] Product/body/campaign shot requests generate model/product/editorial references.
- [x] Process/studio requests generate brush, pencil, canvas, scanner, or studio-detail references.
- [x] Feed-breaker requests generate color/surface/process references.
- [x] Shoot Planner product requests should not accidentally generate pencil/brush imagery.

## Priority 6 - AI Images Stored And Indexed In Visuals

Checklist:
- [x] Builder AI images appear in Visuals.
- [x] Shoot Planner reference images appear in Visuals.
- [x] Campaign Memory visual-need images appear in Visuals.
- [x] Iterations appear in Visuals.

## Priority 7 - Open Generated Image On Source Page

Checklist:
- [x] Wherever an AI image is requested, show a clickable Open Generated Image button on that same page.
- [x] The button should open the image modal directly.
- [x] The user should not need to switch to Visuals to inspect the output.

## Priority 8 - Edit Learning

Checklist:
- [x] Composition plans and user reprompts are logged.
- [x] Future agent runs receive composition-edit memory.

## Verification

Checklist:
- [x] Python compile passes.
- [x] Dashboard JavaScript syntax check passes.
- [x] Composition API returns a design plan for a calendar item.
- [x] AI reference endpoints return source-page open-image metadata.
- [x] Visuals indexes generated image concepts from all request pages.
