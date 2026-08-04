# Glossary: the metaphors and where they appear on screen

Yak-shears runs on two metaphors. The whole app is **a hardware console** (DESIGN.md): an anodized panel you mount things on, like an audio mixing desk or a server rack. The streams page adds a second metaphor on top: **a canal**, where work flows upward through gates. This file maps every term to the pixels it names, so a screen can be reviewed with the right words.

## The console (every page)

The interface is an instrument panel, not a page of documents. Three materials build everything:

- **Panel** — the painted charcoal face things are mounted on. The page background.
- **Well** — a recess milled into the panel where content sits down: the editor's text area, the search field, any latched (selected) control. Drawn with an inset shadow so it reads as sunk.
- **Engrave** — a groove cut into the panel: a dark line over a light line, used wherever another app would draw a border.

Mounted on the materials:

- **Legend** — screen-printed label text (small, tracked, uppercase), like the "GAIN" printed under a knob.
- **Lamp** — a small glowing dot that only ever reports state (green live, amber warn, red fault). If nothing is being reported, no lamp is lit.
- **Cap / anodize** — the colored part carrying category color, from a fixed 12-slot palette.
- **Armed amber** — the one lit accent color. It always means "this will fire" or "attention": the Save key, the active nav underline, warn lamps.

### Rack (the /yaks list)

"Rack" as in a 19-inch equipment rack: a frame holding identical-height units. Each note is one **rack unit** (also called a **channel strip**, from mixing desks): a fixed-height row with its parts in the same place on every row, so your eye reads down a column instead of hunting.

```
┌─ rack ────────────────────────────────────────────────┐
│▌ Title of the note                        ┌─ readout ┐│ ← one rack unit
│▌ four lines of preview text…              │ CATEGORY ││   (channel strip)
│▌ …                                        │ 2026-08-01││
│▌ …                                        │  ●  3    ││ ← recency lamp
│└─ cap (6px category color bar)            └──────────┘│
├───────────────────────────────────────────────────────┤ ← engrave hairline
│▌ Next note …                                          │
└───────────────────────────────────────────────────────┘
```

- **Readout** — the fixed column at the right end of each unit: category, date, lamp, count. Same position every row.
- **Recency lamp** — the one lamp that varies in size as well as color: 9px bright (touched this week) down to 4px unlit (over a year).
- **Bench** — a rack variant for things you operate rather than read: the habits page (and, planned, the workout routines page). Same rows, but each carries a key you press.
- **Key** — a pressable button drawn as a physical key cap (catch-light on top, shadow under). "Mark" / "Done" on habits, checkboxes on lists.

## The canal (the /streams page)

Task management is not a kanban board here. It is a canal with locks: work enters at the bottom and is raised, gate by gate, until it exits at the top. The vertical page layout IS the metaphor: scroll position equals progress.

```
      ═════ tray (pull-down) ═════   ← all streams at a glance; click to open,
              ▼ TLR-MIGRATION          pick a stream to focus the canal on
┌─ canal ───────────────────────┐
│ IN PROGRESS          ● WIP 2/3│ ← top reach; WIP lamp goes amber over limit
│  ▌▍ Ship the importer   due +2│
│  ▌▍ Fix auth redirect        ●│
╞═══════════════ sill ══════════╡ ← crossing a sill = state change
│ QUEUE                         │
│  ▌▍ Write the migration doc   │
│  ▌▍ ⏸ Waiting: vendor reply   │ ← waiting = closed gate; dimmed, stays put
╞═══════════════ sill ══════════╡
│ BACKLOG                       │ ← bottom reach; work enters here
│  ▌▍ Investigate flaky test    │
└───────────────────────────────┘
   drained ▸ complete / not planned  (below, out of the canal)
```

- **Stream** — a durable thread of related work (a note with `type: stream`), scoped under a category: `work/tlr-migration`. Not a sprint, not a project with an end date.
- **Canal** — the focused stream's column of tasks, flowing bottom to top.
- **Reach** — one stretch of canal between gates; holds every task in one state. Three reaches: backlog, queue, in progress.
- **Sill** — the raised bar a lock gate rests on; here, the boundary between reaches. Moving a task across a sill is a state change.
- **Waiting** — a closed gate. The task holds in its reach, dimmed, with the reason printed (`waiting: vendor reply`). It is a flag, not a fourth state, so nothing has to move backward when the wait ends.
- **WIP lamp** — reports tasks in progress against the stream's `wip-limit`. Amber over the limit. It never blocks anything; it only reports.
- **Drained** — tasks that left the canal: complete or not planned. Water out of the system.
- **Tray** — the pull-down panel at the top (a `<details>` bar) holding every stream's meter, grouped by category. It replaces both a sidebar dock and a stream switcher: closed, it is one line naming the focused stream; open, it is the overview.
- **Mark** — the two touching vertical stripes at each task's left edge: 8px category color, then 5px stream color, both from the same 12-slot palette. Category outranks stream, so its stripe is thicker.
- **Due +n** — the KISS deadline model: one `due` date plus `flex` days of acceptable slip. Amber inside the flex window, red past it. No priorities, no estimates.
- **Triage** — task notes with no stream, or naming a stream that does not exist. Surfaced so nothing silently vanishes.

## Habits (the /habits bench)

- **Heat row** — 28 day-cells per habit: filled when done, hollow when scheduled-but-missed, faint when unscheduled.
- **Streak** — consecutive scheduled successes, in days (`4d`) for daily/weekdays schedules or weeks (`2w`) for `n/week` quotas.
- **Grace** — banked forgiveness, shown as `+n`. It is earned, never granted: completing on an unscheduled day banks one (cap 7), and a missed scheduled day spends one before the streak breaks.
- **Makeup** — an off-schedule completion right after a miss retroactively covers it (the Friday you did on Saturday).

```
Morning stretch   WEEKDAYS   ▪▪▪▫▪▪·▪▪▪▪▫▪·  4d +1   [ MARK ]
                              └ heat row ┘   │  │      └ key
                                        streak  grace
```

## One-line map, term to page

| You see it on | The words for it |
|---|---|
| /yaks | rack, rack unit / channel strip, cap, readout, recency lamp |
| /streams | canal, reach, sill, tray, mark, WIP lamp, waiting, drained, triage, due +n |
| /habits | bench, heat row, streak, grace, makeup, key |
| /lists | rack of list cards; first unchecked item as the preview |
| /settings | swatch bank (the 12-slot color picker; taken slots carry the owner's initial) |
| everywhere | panel, well, engrave, legend, lamp, armed amber |
