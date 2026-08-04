# Next Steps

Open work left by the console redesign (2026-07-26), on branch `redesign-console`. The visual system is recorded in [DESIGN.md](./DESIGN.md); this file is what is not done yet. For the product roadmap see [ROADMAP.md](./ROADMAP.md) and [PLAN.md](./PLAN.md), which this does not duplicate.

## The redesign

### 1. The patchbay

The largest outstanding piece, and the one that carries both the color and the weakest part of the app. Links and backlinks currently render as a number in a readout and a plain list in the metadata panel. On a console they are routing: colored patch connections on the editor and in the rack, showing where a note connects rather than how many connections it has.

The editor is the natural starting point, because `render_yak_edit` already receives `backlinks: list[tuple[str, str]]`. The rack's `.card__stat--links` readout follows.

### 2. Surfaces still on the old world

These inherit the tokens, so they are not broken, but they keep the shape of the discarded design and have not been rebuilt from the three materials:

- `/new` (`yak/new.html.jinja`), which still uses the generic `.form` block
- Login (`auth/login.html.jinja`), still a centered card with `--shadow-md`
- The error page
- The metadata panel, which is still styled as a terminal/TUI pane from an earlier direction and now speaks a different vocabulary than the editor it sits beside
- The search preview modal and the empty states

The design detector flags exactly four literals on these surfaces (a 4rem empty-state icon, a 1.35rem mobile title, a 1.125rem doctor heading, and a 0.25rem code radius). That list is the backlog; it should reach zero as each surface is rebuilt, and no literal should be waived to get there.

### 3. Verification that has not happened

- **Phone.** Nothing has been checked at 390x844. Chrome would not resize below ~400px during the build, so use `scripts/capture_screenshots.py` (Playwright), which can.
- **Dark mode.** The dark block was rewritten as material overrides and never looked at.
- **The save-status lamps and `.alert--warn`**, changed on 2026-07-26 and verified by test rather than by eye.

### 4. Motion

One orchestrated moment is missing. What exists is per-control: the 70ms switch throw and the 260ms meter settle. Nothing coordinates on page entry beyond a leftover staggered `fadeIn` on the first six cards, which is from the old design and should either become part of the world or go.

### 5. Finish handoffs

- Run the `impeccable-finish-reviewer` subagent against the direction contract with screenshots, once the phone and dark-mode passes exist to hand it
- `/impeccable live` is unblocked now that DESIGN.md exists, if variant exploration is wanted
- Regenerate the four README screenshots after the surfaces above are rebuilt, not before

## Pre-existing bugs found during the redesign

Found while working, out of scope for a visual pass, and not fixed:

- **Search previews highlight nothing.** `AGENTS.md` says matches are highlighted in the preview; `.search-highlight` exists in the CSS and no rendered preview applies it.
- **The search sidebar shows title plus path**, where the documented behavior is a single unwrapped preview line.
- **The asset budget is roughly 4x over.** `main.css` alone is ~3.1k lines against a stated 14KB total. Either the budget is stale and should be restated, or the stylesheet needs a pass. Worth deciding explicitly, because the e2e suite enforces 90% rule coverage on the assumption that the budget matters.

## Decisions waiting

- **Stream colors vs. category colors.** Phase 5 plans a curated named palette (fjord, teal, moss, ...) while the console generates category color by hashing the name into a fixed saturation and lightness band. Two color systems on one screen unless they are reconciled. `amber` in that draft palette also collides with the panel's one lit color, which means armed.
- **Tasks, work streams, and habits** were raised as layers that may change the direction. The console world handles them without strain (a stream is a rack, a habit is a meter with real ballistics, a WIP limit is a lamp that goes amber), but that is an argument, not a decision.
