# Work Streams: design brief and data model

Drafted 2026-08-02 from the shape interview. This is the design source for PLAN.md Phase 5 (streams, backlog, triage) and the parts of Phase 4 the views demand. Mockups live in `mockups/streams.html`; a throwaway read-only prototype is at `/streams`.

## Job

One person, two scenes. During the day the active stream is Work; in the evening it is Personal. The board's job is to answer "what am I doing now, what is next, and what is waiting on someone else" for exactly one stream at a time, while keeping the other streams visible at the edge as a dock. Cross-stream views (everything in progress, everything due soon, everything untriaged) are secondary surfaces, not the home screen.

This is Operate mode inside the committed Console world. tlr's ADR 0012 defines a stream as "a durable thread of related work, longer-lived than a cycle, narrower than a project" and leaves open where a stream is defined. This design makes the vault a candidate answer: a stream is a note, and tlr could later read the same ids.

## The metaphor: a canal, not a kanban

Work flows bottom to top. Each stream renders as a vertical channel cut into the panel: backlog at the bottom, queue above it, in-progress at the top, with complete draining off the view. The state boundaries are gates (engraved sills across the channel). A task is a vessel between gates.

Two properties make the canal more honest than columns:

- Crossing a gate is the meaningful event, so the boundary is drawn as a physical sill the strip visibly sits above or below, and moving a task animates it across the sill
- A closed gate models waiting. A task waiting on an external event (code review, a reply, a delivery) stays in its reach but sits against a closed gate: dimmed strip, gate lamp unlit, the reason printed on the sill. Waiting is a flag, not a state, matching the no-`on-hold` lifecycle decision and tlr's shelf-as-capacity-state conclusion

WIP pressure is a lamp, not a rule. When in-progress holds more tasks than `wip-limit`, the reach's lamp goes warn amber. Nothing blocks.

## Layout

### Desktop

Dock left, focus right, inside the 1200px container.

- The dock is a rail of narrow flow meters, one per stream, grouped under category legends. Each meter is the stream in miniature: stacked segments bottom to top (backlog, queue, in-progress), category cap on the left edge, stream band beside it, WIP lamp at the top, name in nano caps beneath. The focused meter seats into the well with the 2px amber underline, the same vocabulary as every latched control
- The focus pane is the expanded canal for one stream: full-width task strips in reaches by state, gates between them. Strips reuse the rack unit grammar (fixed height, cap, title, readout column with due date and waiting lamp) at a shorter pitch than the note rack, because a task strip carries a title and a readout, not a four-line preview
- A view switch above the focus pane toggles Stream, In Progress, Horizon, Triage, and Backlog. The non-stream views replace the canal with a flat rack or table across streams, each strip carrying its two-color designation so the stream stays identifiable

Grid use of the width: at wide sizes the focus pane may run two channels side by side (the focused stream plus a pinned second, for the day/evening pair). This is the only multi-stream canal; more than two re-creates the column kanban this design refuses.

### Phone (390px)

One stream fills the screen. The dock compresses to a horizontal rail of meters at the bottom, above the safe area, thumb-reachable; tapping a meter swaps focus. Two zoom levels and a scroll:

- Zoomed out (default): each task is a full strip with title, due readout, and waiting reason. Scroll moves through the canal; crossing a gate is a full-width sill that cannot be missed
- Zoomed in (compact): strips collapse to ticks (title only, single line) so the whole canal fits a screen or two. A side minimap appears at the right edge: a thin track with a notch per task and a legend per reach, the current position lit. Tapping a reach on the minimap jumps to it

The zoom control is a two-position switch in the view bar, and pinch chooses the same two positions. There is no continuous zoom; two named levels keep the layout deterministic.

## Data model

All state lives in frontmatter. Files round-trip verbatim; every board action rewrites only the lines it touches. The board is a query over the vault (Phase 4 engine), never a stored list.

### Stream note

```yaml
type: stream
id: tlr-migration
name: TLR Migration
category: work
color: sky
wip-limit: 3
```

- `id` is a slug, unique within its category. Tasks reference `category/id`
- `category` scopes the stream. Work and Personal will carry several streams; most categories carry one
- `color` names one of the twelve anodize slots (`clay` through `olive`). It defaults to the category's slot from `categories.json`. The separate fjord/teal/moss palette from the earlier draft is dropped: one palette, no amber possible, the NEXT_STEPS collision resolved
- `wip-limit` is optional and only ever drives the lamp

The body of a stream note is free prose (the stream's charter, links, whatever). The note is a normal note.

### Task note

```yaml
state: queue
stream: work/tlr-migration
due: 2026-08-09
flex: 3
waiting: code review from Sam
blocked-by:
  - "[[2026-07-22T14_03_51Z]]"
relates:
  - "[[2026-07-30T09_12_04Z]]"
```

- A note is a task when it carries `state`. No new syntax, no separate task store. One task per note
- `state` keeps the decided enum: `backlog | queue | in-progress | complete | not-planned`
- `stream` is optional. A task with `state` and no `stream` lands in Triage
- `due` is a date, optionally with a time. `flex` is days of acceptable slip (default 0). Urgency is derived: overdue when past `due + flex`, pressing when inside the flex window, scheduled otherwise. No estimates, no priority field. "Do today" is `due: <today>`; "do tomorrow" is `due: <tomorrow>`
- `waiting` marks the closed gate. Free text names the external event; a wikilink points at a note about it. Presence is the flag
- `blocked-by` and `relates` are wikilink lists. Rendering blocked-by as a drawn dependency is a later iteration; the first release prints the relation in the strip's readout
- Within a reach, order is derived: due (with flex) ascending, then last modified. Explicit manual ordering is an open decision (below)

### Reference lists (groceries and friends)

```yaml
type: list
name: Groceries
```

A list note is a normal note whose body is headings and Djot task items. The Reference surface pins all `type: list` notes for one-tap access (the physically-in-the-store scene), renders their checkboxes live, and writes check state back to the body. Semi-automatic organization (grouping items under aisle headings) is a later iteration and probably a command ("file this item"), not magic. Lists never appear in streams; `type: list` and `state` are mutually exclusive, and Doctor flags a note carrying both.

### Views config

Saved views are per-vault app configuration, not notes: `.yak-shears/views.toml` beside the vault, next to `categories.json`, synced by Syncthing with everything else.

```toml
[[view]]
id = "deep-work"
name = "Deep Work"
filter = { state = ["in-progress", "queue"], category = ["work"] }
group = "stream"
sort = ["due", "modified"]
```

Built-ins (In Progress, Horizon, Triage, Backlog) ship in code and need no entry. The file adds custom views and can set the default view and dock order. Doctor validates it.

## Views

- The Stream canal is the home surface, one stream focused, dock at the edge
- In Progress: every `state: in-progress` task across streams, one flat rack, grouped by category
- Horizon: tasks with `due` set, ranked by derived urgency (overdue, pressing, then by date). This is the do-today / do-tomorrow surface
- Triage: tasks missing `stream` or carrying an unknown one, plus notes whose body says task but whose frontmatter does not (later, once inline surfacing exists)
- Backlog: the same query as a sortable table (title, stream, state, due, waiting, modified)
- Prune queue (Phase 5 sibling): unchanged from PLAN.md, `last-reviewed` plus interval; shares the strip and command grammar so a review can end in a state change

## The command grammar

The board's writes go through one composable grammar, shared between the desktop keyboard and the mobile command panel (ADR 0011's panel extended to the board). An action is verb, field, operand, applied to the focused task or the selection.

- State: advance one gate (the most common action gets the cheapest key), or set a named state
- Dates: set absolute (`today`, `tomorrow`, a picked date) or shift relative (`+1d`, `+7d`, `-1d`) against `due`; the same relative grammar applies to `flex`
- Stream: move to a stream chosen from the resolver (same completion machinery as Phase 3's `[[` autocomplete)
- Waiting: toggle, with a reason prompt
- Relations: add `blocked-by` / `relates` via the resolver

Repetition is the design center, per the interview:

- Repeat: one key replays the last action on the current target, vim's dot
- History: a secondary panel lists past actions deduplicated and ordered by frecency, each a single press to reapply. This is where "due +7d" becomes a reusable tool rather than a menu path
- Batch: a count or a multi-select applies one action to many tasks in one gesture, and the strips it will touch tint amber before it fires, the command panel's existing convention

Every binding is rendered somewhere visible (tlr's rule: a binding not rendered does not exist). Every write shows an inverse-action toast for undo. Frecency data is app state, not vault state, and lives with the app's other local data.

## Color and the two-color designation

A task strip carries category and stream as two adjacent anodized bands on its left edge: the 6px category cap, then a 3px stream band. Single-stream categories show one visual color (the band matches the cap). The palette is the existing twelve-slot anodize system and its stored mapping; stream `color` uses the same names. Amber stays reserved for armed and warn.

## Doctor checks

- Task references a stream that does not exist (`stream` with no matching stream note)
- Stream `color` not a palette name
- Duplicate stream `id` within a category
- Stream over its `wip-limit` (warn, mirrors the lamp)
- `state` value outside the enum, `due`/`flex` unparseable
- `type: list` combined with `state`
- `views.toml` invalid or referencing unknown fields

## What Phase 4 must provide

The views above impose the engine's minimum surface:

- Filter by field equality and set membership, field presence and absence, and date comparison against a relative today
- Group by a field, with counts per group (the dock meters are group counts)
- Multi-key sort including derived urgency
- Resolve a task's `category/id` stream reference to its stream note in one pass
- Everything rebuildable from files; no membership state anywhere

## Sequencing

1. Phase 4 engine with the surface above, plus stream-reference resolution
2. Read-only canal, dock, and Triage (proves the geometry; no writes)
3. The command grammar: state advance, due set/shift, stream move, waiting toggle, repeat. Frontmatter line-rewrite machinery with round-trip tests
4. History/frecency panel, batch, saved views via `views.toml`, Horizon and Backlog
5. Reference lists surface; prune queue rides the same strip grammar

## Open decisions

- Inline task surfacing: whether a Djot task item (`- [ ]`) or a TODO-like line inside a non-task note can surface into Triage as a candidate task, and what marks it. Deferred; frontmatter-only is the first release
- Explicit manual ordering within a reach (an `order` field or list) versus the derived due-then-modified order. Derived ships first
- Short-form `stream:` references (bare `id` when unambiguous) versus always-qualified `category/id`. Qualified ships first
- Grocery-list auto-organization (aisle sections) and whether check state resetting is time-based or manual
- tlr interop: whether tlr reads stream ids from the vault or maps them to Linear labels. Nothing here blocks either answer
