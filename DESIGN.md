---
name: Yak Shears
description: A console panel for a vault of Djot files, built from three materials and one lit color.
colors:
  panel: "#22262b"
  panel-raised: "#2b3037"
  well: "#14171a"
  engrave: "#0a0c0e"
  engrave-light: "#3d434b"
  legend: "#e8ecf1"
  legend-dim: "#99a3ae"
  signal: "#f7f9fb"
  amber: "#ffb02e"
  lamp-live: "#3ddc7f"
  lamp-warn: "#ffb02e"
  lamp-fault: "#ff5c47"
  lamp-off: "#464d55"
  link: "#6fb7ff"
  ink-on-amber: "#1b1206"
  ink-on-lit: "#000000"
  ink-on-fault: "#ffffff"
  scrim: "rgba(0, 0, 0, 0.5)"
  category-clay: "hsl(16, 72%, 58%)"
  category-rose: "hsl(352, 68%, 62%)"
  category-pink: "hsl(328, 62%, 64%)"
  category-mauve: "hsl(302, 52%, 62%)"
  category-violet: "hsl(276, 58%, 64%)"
  category-indigo: "hsl(250, 62%, 62%)"
  category-azure: "hsl(216, 72%, 56%)"
  category-sky: "hsl(196, 74%, 50%)"
  category-teal: "hsl(174, 62%, 44%)"
  category-moss: "hsl(150, 52%, 46%)"
  category-fern: "hsl(118, 46%, 48%)"
  category-olive: "hsl(72, 52%, 46%)"
typography:
  legend:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.14em"
  headline:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: "normal"
  label:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.09em"
  signal:
    fontFamily: "ui-monospace, Menlo, Monaco, 'Cascadia Mono', 'Roboto Mono', Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontFeature: "tabular-nums"
  subhead:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  source:
    fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  field:
    fontFamily: "ui-monospace, Menlo, Monaco, 'Cascadia Mono', 'Roboto Mono', Consolas, monospace"
    fontSize: "1.05rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  note:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  micro:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.11em"
  nano:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.1em"
rounded:
  hairline: "1px"
  hardware: "2px"
  sm: "3px"
  lg: "5px"
  pill: "999px"
spacing:
  1: "0.25rem"
  2: "0.5rem"
  3: "0.75rem"
  4: "1rem"
  5: "1.5rem"
  6: "2rem"
  7: "3rem"
  8: "4rem"
components:
  button:
    backgroundColor: "{colors.panel-raised}"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
    height: "44px"
  button-primary:
    backgroundColor: "{colors.amber}"
    textColor: "#1b1206"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
    height: "44px"
  button-latched:
    backgroundColor: "{colors.well}"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
    height: "44px"
  card:
    backgroundColor: "{colors.panel-raised}"
    textColor: "{colors.legend-dim}"
    typography: "{typography.title}"
    rounded: "0"
    padding: "0"
    height: "8.5rem"
  input-search:
    backgroundColor: "{colors.well}"
    textColor: "{colors.signal}"
    typography: "{typography.signal}"
    rounded: "{rounded.sm}"
    padding: "0.75rem"
    height: "44px"
  editor-well:
    backgroundColor: "{colors.well}"
    textColor: "{colors.signal}"
    typography: "{typography.signal}"
    rounded: "0"
    padding: "1.5rem"
  preview-pane:
    backgroundColor: "{colors.panel-raised}"
    textColor: "{colors.legend}"
    typography: "{typography.body}"
    rounded: "0"
    padding: "1.5rem"
    width: "68ch"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.legend-dim}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.75rem"
  nav-link-active:
    backgroundColor: "{colors.well}"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.75rem"
---

# Design System: Yak Shears

## Overview

**Creative North Star: "The Console"**

Yak Shears is an instrument you operate at speed, so the interface is a console panel rather than a page of documents. It refuses the arrangement every note app ships: a grey sidebar tree beside a white document pane, with every note drawn as an identical card. The vault is a rack of channel strips, one unit per note, each with its category cap, its four lines of note, and its readout in the same place. You sweep the readout column, throw a switch, and work in the center section.

Three materials do all the structural work and every component is built from them. The **panel** is the painted face things are mounted on. The **well** is a recess milled into it, where content and inputs sit down. The **engrave** is a groove cut into the panel, drawn as a dark line over a lighter one so it reads as cut rather than as a stroked border. On top of the materials sit the parts: screen-printed legends, anodized caps carrying category color, and indicator lamps that report state in size as well as color.

The panel is anodized charcoal, slightly blue rather than neutral, with a fine directional grain instead of a flat fill. This matters because a flat neutral grey is the timid rendition of this world and it takes the life out of every cap and lamp mounted on it. Both color schemes are real consoles: light is a painted panel under daylight, dark is the same desk at night. Neither is an inversion of the other, and neither turns the instrument into paper.

**Key Characteristics:**

- Three materials (panel, well, engrave) compose every component; nothing is a floating card
- Amber is the only lit color in the chrome and it means armed
- Category color owns whole rows, not slivers
- Depth is machined, not ambient: insets and catch-lights, no drop shadows on the panel
- Screen-printed sans for chrome, monospace for anything literal or measured
- Hardware travel is 1px; controls move a little, not a lot

## Colors

An anodized charcoal panel with a full-spectrum category system mounted on it, plus a small set of lamps that are only ever allowed to mean state.

### Primary

- **Armed Amber** (#ffb02e): The panel's one lit color. It marks the action that will fire (the Save key), the seated position of a latched control (the 2px underline on active nav, view toggle, pagination, and search selection), and the warn lamp. Against neutral grey it read as a 2010 warning banner; against charcoal it reads as a lit lamp.

### Secondary

- **Category Anodize** (twelve fixed slots, `clay` through `olive`): A closed palette rather than a generated value. Hashing the category name into a free hue produced neighbours 13° apart (`evergreen` at 217, `tasks` at 204) that read as two shades of one blue, so the wheel is now cut into twelve slots a category is pinned to. Hues 25–55 are left out: that band is armed amber, and a lit color that means "this will fire" must not also mean "filed under tasks". This color fills the card cap, tints the whole row, and marks the editor head plate.

  Assignment is a stored mapping, not a function of the name. `.yak-shears/categories.json` beside the vault records category → slot, so colors travel with the notes over Syncthing and survive an index rebuild. A new category takes the next free slot walking the palette in steps of five, which keeps the first several categories far apart on the wheel instead of adjacent. A category named after a slot (`teal`, `moss`) claims that slot when it is free. Past twelve categories slots repeat, which is the honest failure: two categories share one color rather than drifting into two shades of it. `/settings` reassigns any of them.

### Tertiary

- **Routing Blue** (#6fb7ff): Rendered links inside note content. Distinct from amber because a link in the user's prose is content, not a panel control.

### Neutral

- **Panel** (#22262b): The painted face. Page background.
- **Panel Raised** (#2b3037): Anything mounted proud of the face: header strip, key faces, card bodies, the preview bay, the transport bar.
- **Well** (#14171a): Recesses. The editor source bay, the search patch field, latched controls, doctor rows.
- **Engrave** (#0a0c0e) and **Engrave Light** (#3d434b): The two halves of a milled groove, always used as a pair (dark line over light) so a division reads as cut rather than drawn.
- **Legend** (#e8ecf1): Panel text at full strength.
- **Legend Dim** (#99a3ae): Screen-printed labels, secondary readout values, and unlit-but-legible text. This is the floor for text; it holds roughly 5:1 against the panel in both schemes.
- **Signal** (#f7f9fb): The brightest ink on the panel, reserved for what the user types.

### Lamps

- **Live** (#3ddc7f), **Warn** (#ffb02e), **Fault** (#ff5c47), **Off** (#464d55): Indicator lamps. A lamp is a 7px circle with a matching glow at ~55% mix.

The rack's recency lamp is the one place a lamp varies in size as well as color: 9px lit live inside a week, 7px at 70% live within a month, 5px at 30% within a year, 4px unlit beyond. Both channels carry the tier, so it survives a monochrome rendering and reads down a column without being read.

### Ink on Lit Surfaces

A lit surface takes dark ink, because the panel's text colors are built for a dark ground and would vanish on amber.

- **Ink on Amber** (#1b1206): The armed key's label. Warm near-black rather than pure black, so it belongs to the amber rather than punching through it.
- **Ink on Lit** (#000000): Labels on any other fully lit surface: the skip link, the active combobox option, a pressed toolbar key, a search highlight.
- **Ink on Fault** (#ffffff): Labels on a filled fault-red surface.

### Shading

Shading is material, not palette. The alpha blacks and whites in inset shadows, the anodize grain, and cap catch-lights are how a material is drawn and they are recorded with their materials in the sidecar, not as color tokens. One carries a role and is named:

- **Scrim** (rgba(0, 0, 0, 0.5)): Behind a surface that leaves the panel plane, which today is the editor's metadata panel and the search preview.

### Named Rules

**The Lamps-Only Rule.** Green, red, and amber appear as state and never as decoration. A lamp answers a question about the system right now; if nothing is being reported, no lamp lights.

**The One Armed Key Rule.** Amber marks the action that will fire, so exactly one primary key belongs in any control group. A full-width slab of amber on a control that is always present spends the panel's only lit color on nothing.

**The Unlit-Off-Limits Rule.** `--lamp-off` (#464d55) is for hardware that is dark, never for text. Dim text steps down to `--legend-dim`, which stays above the contrast floor.

## Typography

**Legend Font:** system sans (`ui-sans-serif`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, Roboto)
**Signal Font:** system mono (`ui-monospace`, Menlo, Monaco, Cascadia Mono, Roboto Mono, Consolas)

**Character:** The panel is screen-printed, so its chrome is sans: small, tracked, and uppercase. Monospace is reserved for what is actually literal or measured, which means note source, filenames, paths, timestamps, and counts. Setting the whole interface in mono was the old surface wearing "technical" as a costume.

### Hierarchy

- **Legend** (700, 0.8125rem, 0.14em tracking, uppercase): Section names printed on the panel. This is what `h1` becomes everywhere outside rendered note content. A 2rem heading over a bank of controls reads as a document, not an instrument.
- **Headline** (600, 1.5rem, 1.3): `h2`. Used inside rendered content and on the few document-shaped surfaces.
- **Title** (600, 0.9375rem, 1.35): A rack unit's name, lifted from the note's first block. Single line, ellipsized.
- **Body** (400, 1rem, 1.7, max 68ch): Rendered note prose in the preview bay. Prose is read rather than scanned, so it takes a reading measure.
- **Subhead** (600, 1.25rem, 1.3): `h3` inside rendered content, and the one large readout value on a stat tile.
- **Label** (600, 0.75rem, 0.09em tracking, uppercase): Every key face, nav switch, and control legend.
- **Note** (400, 0.875rem): Secondary panel text that is still meant to be read rather than scanned: a vault path, a result's first line, a backlink, a doctor reference.
- **Micro** (600, 0.6875rem, 0.11em tracking, uppercase): The smallest screen-printed legend. Section labels, small key faces, readout tracks, tags, the maker's badge.
- **Nano** (600, 0.625rem, 0.1em tracking, uppercase): Tighter still, for a legend that has to sit inside a row without competing with it: the rack unit's category chip, the editor head's category.
- **Signal** (400, 0.8125rem, tabular figures): Filenames, paths, dates, counts, and tags.
- **Source** (400, 0.9375rem, 1.6): The editor's own text. One step up from signal, because it is read for minutes rather than glanced at.
- **Field** (400, 1.05rem, mono): Text the user is typing into a patch field.

### Named Rules

**The Legend-Never-Content Rule.** A legend names a control. It never carries the note. Panel heading styles are scoped away from rendered content with `h1:not(.preview-content h1, .card__preview h1, .search-preview h1)`, because a heading the user wrote is theirs and stays a heading.

**The Tabular Column Rule.** Anything that appears at the same position on consecutive rows takes `font-variant-numeric: tabular-nums`. Counts and dates in a rack must line up on the digit or the readout column stops being a column.

## Layout

The container caps at 1200px with gutters that step 1rem → 1.5rem → 2rem at 640px and 768px, each adding the matching `env(safe-area-inset-*)` so content clears the notch. The rack page narrows the container to **52rem**, so the vault head, the filter switches, and the units sit in one column instead of leaving the rack stranded under a header running the full width. The single breakpoint is **768px**, duplicated as `MOBILE_BREAKPOINT` in `editor.js`, `search.js`, and `nav.js`.

Every page clears the header groove with `--space-6` of top padding. The editor is the only exception: it is a full-height chassis measuring itself from `--header-height`, and any padding above it runs the chassis off the viewport.

The rack is the defining layout. It is a flex column with a 1px gap over an engrave-colored ground, so the gap shows through as a hairline and the strips read as mounted in one frame rather than as floating cards. Each unit is a three-track grid (`6px | minmax(0,1fr) | 6.5rem`) at a fixed `8.5rem` height. The fixed height is load-bearing: notes whose first blocks happen to be short or tall must not change the row pitch. The preview inside is line-clamped to exactly four lines at a fixed `4.4rem`. Every block in it runs on the preview's own leading and font size, including fenced code, because the clamp counts lines while the height cuts pixels: one child with a taller line box pushes a sliced fifth line out under the bottom edge.

The narrow measure is what buys those four lines. Stretched to the old 72rem a long note ran as one stranded line and a short one wasted the row; at 52rem both wrap into the same block of readable text.

The readout at the right end is a fixed stack of rows rather than flow: category, date, then the lamp and patch count. The point of a readout is that each value lands at the same position on every row, so the eye reads down a column instead of hunting along each row.

The editor is a head plate over a two-bay chassis: `.editor-head` carries the identity and the source selector and never scrolls away, and `.editor-container` holds the source well and the preview bay separated by a 1px engrave gap. Below 768px the chassis stacks, split view gives each bay `min-height: 40dvh`, and the metadata sidebar becomes a bottom sheet capped at 70vh.

Vertical units come from an eight-step scale (0.25rem to 4rem). Fixed bars offset themselves from `--header-height`, `--action-bar-height`, `--safe-bottom`, and `--keyboard-inset` rather than from hardcoded pixels, and full-height measurements use `dvh`, because iOS Safari's `100vh` assumes a hidden URL bar.

### Named Rules

**The Row-Pitch Rule.** Every rack unit is exactly one rack height. Content never sets the row height.

**The dvh Rule.** `dvh`, never `vh`. `overflow-x: clip`, never `hidden`, because `hidden` stops the sticky header from sticking.

## Elevation & Depth

There are no ambient drop shadows on the panel. Depth is machined: things are either recessed into the face, flush with it, or standing proud of it, and each state is drawn with insets and catch-lights rather than with a blur cast onto the page. A shadow token set (`--shadow-sm/md/lg`) survives on the few surfaces that genuinely float above the panel (the mobile nav popover, the search preview modal, the combobox list), and nowhere else.

### Shadow Vocabulary

- **Well** (`inset 0 2px 4px rgba(0,0,0,0.55), inset 0 -1px 0 rgba(255,255,255,0.06)`): A recess milled into the panel. Dark at the top lip where light is occluded, with a thin catch-light along the bottom lip. Used for the editor, the search field, latched controls, and doctor rows.
- **Key face** (`inset 0 1px 0 var(--engrave-light), 0 1px 1px rgba(0,0,0,0.12)`): A capped button standing slightly proud. Catch-light on the top edge, contact shadow under the lower lip.
- **Anodize** (`linear-gradient(180deg, rgba(255,255,255,0.05), rgba(0,0,0,0.06))` over a 1px/3px vertical grain): Not a shadow, but the reason surfaces do not look plastic. Real anodized aluminium has a fine directional grain and catches light unevenly. Two cheap gradient layers, no image.
- **Lamp glow** (`0 0 6px color-mix(in srgb, <lamp> 55%, transparent)`): The only glow in the system. Lamps only.
- **Float** (`--shadow-lg`, `0 8px 16px rgba(0,0,0,0.1)`): Reserved for genuine overlays that leave the panel plane.

### Named Rules

**The Machined-Depth Rule.** Depth is stated by inset and catch-light, not by a blur under the element. If a surface is on the panel, it casts no shadow onto it.

**The Engraved-Pair Rule.** A division is a `1px solid var(--engrave)` over a `1px solid var(--engrave-light)` (or the equivalent `box-shadow: 0 1px 0`). A single grey line is a border; the pair is a groove.

## Shapes

Panel hardware is machined, so radii are small and deliberate: 3px on caps, keys, and switches, 5px on chassis corners, and full round only on lamps. Below that sit two hardware steps that exist because a milled part has a broken edge rather than a sharp one: 2px on a segmented control's outer positions, and an inline code run, and 1px on the smallest details (a lit indicator bar, a cap edge, the head plate's rule). Nothing is pillowy. The pill radius survives on two legacy controls and should not spread.

Structure is carried by material rather than by outline. Where a border does appear it is `--engrave`, and it is nearly always paired with its catch-light to read as a cut. The category cap is a full-height 6px bar with an inner catch-light (`inset 1px 0 0 rgba(255,255,255,0.22)`) and an outer contact shadow, which is what makes it read as a machined part rather than a flat colored rule.

The anodized cap is the system's recurring signature geometry: a full-height 6px bar in the category color, repeated down the rack, on the editor's head plate, on every category key on `/new`, and on every row of the settings bench. Wherever a category is named, that bar names it.

### Named Rules

**The No-Side-Bar Rule.** State is never communicated by a colored border down one edge of a row. That vocabulary belongs to the category cap, which means identity. Severity uses lamps; selection uses the seated well plus the lit underline.

## Components

### Buttons (keys)

- **Shape:** 3px radius, minimum 44px tall (`--tap-target`), label in tracked uppercase
- **Default:** panel-raised face, engrave border, catch-light on top, contact shadow beneath
- **Hover:** face drops to `--panel`
- **Active:** `translateY(1px)` and the well inset replaces the key shadow. The light comes off the top and the key drops. Travel is 1px, which is the whole gesture
- **Primary (armed):** amber face, #1b1206 text, border mixed 70% amber into black
- **Latched:** seats into the well with `inset 0 -2px 0` amber. Filter chips, view modes, pagination, and the search selection all read their state from depth plus that underline, never from a fill color
- **Ghost danger:** outline at 0.75 opacity until hover, then fills fault red
- **Motion:** `--throw` (70ms, `cubic-bezier(0.2, 0, 0.1, 1)`) on background, shadow, and transform. Fast to seat, like a real key

### Cards (rack units)

- **Shape:** square. Only the rack frame is rounded (5px), and only its first and last caps take the corner
- **Background:** a category-tinted gradient (13% at rest, 30% on hover, fading out by 42–55%) over the anodize grain over panel-raised
- **Cap:** 6px full-height anodized bar in the category color
- **Border:** none. Units are separated by the 1px rack gap showing the engrave ground through
- **Shadow:** none. A unit is mounted in the rack, not floating over it
- **Height:** fixed 8.5rem
- **Category:** stated once, by the cap. The name is set in nano caps in the readout at `opacity: 0` and fades in on hover and focus. Faded rather than removed, so it stays in the accessibility tree and its row stays reserved and nothing shifts under the pointer. Below 768px it is always lit, because a phone has no pointer to hover with

A word-count level meter used to sit at the end of every readout. It spent 3.5rem of every row on a number nothing was decided by, so it was removed along with `YakInfo.word_count` and the `--settle` easing that drove its ballistics. The recency lamp took the slot.

### Empty State

An empty rack: the frame at 8rem wide with three vacant `--well` slots in it, hairline
gaps showing the engrave ground through, and no caps mounted. It reuses the rack's own
geometry, so an empty vault looks like the thing it is rather than like a missing
picture. The two emoji it replaced (📝 and 🔍) were the only marks in the interface
that belonged to no world, and sizing one at 4rem was the only type on the page with
no step on the ramp.

### New yak

`/new` is a page of its own. It carries a bank of category keys, each with its own anodized cap, and pressing one files the note in a single click. The new-category field sits in a **separate form** from the key bank, because a submit button sharing a form with a text field fires on Enter and would file the note under whichever category happened to be first. Nothing autofocuses, so arriving does not throw the software keyboard over the keys.

It was briefly a modal over the rack. Rendering it meant rendering the whole rack behind it, which is the most expensive page in the app and the one a phone waits on.

### Inputs

- **Style:** recessed. Well background, engrave border, well inset, `--signal` text in the mono face. Both the editor and the search field are places the user puts signal in, so they are the same material
- **Focus:** the well inset plus a 2px amber ring, keeping the recess visible underneath
- **Global focus-visible:** `box-shadow: 0 0 0 3px rgba(247, 207, 70, 0.4)` with the outline suppressed

### Navigation

Switches on the panel's top strip: tracked uppercase, dim at rest, `--panel` face with an engrave border on hover, 1px drop on press. The engaged switch seats into the well and lights a 2px amber indicator across its lower edge.

New and Search stay on the bar at every width. They are what a phone reaches for constantly, and a tap-then-wait through the hamburger for either of them is a tax on the two most common actions. Yaks, Doctor, and Settings collapse into a `<details>` hamburger below 768px, where the wordmark also drops and each link takes a full 44px row.

Every route but the rack carries a back control at the left edge of the bar. A standalone homescreen app has no browser chrome, so an unreliable edge swipe is otherwise the only way back. It is an anchor to `/yaks`, which is what it does with scripting off or in a fresh tab. When a same-origin page is behind it, `nav.js` sends it to `history.back()` instead.

**The Drawn-Mark Rule.** Panel chrome is drawn from boxes and borders in `currentColor`, never typed as a glyph. The hamburger is a 2px bar with two pseudo-element bars hung off it, and the back mark at the other end of the same bar is built the same way: a 12px shaft with an 8px square rotated 45° for the head, two borders showing. A drawn mark takes no step off the type ramp, inherits the switch's dim-to-lit color, and scales with the panel rather than with a font. The empty-state mark follows the same rule at a larger size.

The header itself is opaque anodized panel-raised with an engraved bottom groove. It is not translucent, because a console face is metal and blur let content swim underneath it.

### Editor Head Plate

The one thing on the editor that never scrolls away: category cap, filename in mono, category in tracked caps, and the three-position source selector. The selector is one control with three positions rather than three loose buttons, so the seated position reads as the monitored source.

## Do's and Don'ts

### Do:

- **Do** build new surfaces from the three materials. Ask whether the thing is recessed, flush, or proud, and use `--inset-well`, the panel face, or the key shadow accordingly.
- **Do** put `--anodize` under any large panel surface. A flat fill is what made the first rendition read as dated.
- **Do** reserve amber for the armed action and the seated position of latched controls.
- **Do** use lamps (7px circle plus 55% glow) for state, and the category cap for identity.
- **Do** set anything literal or measured in `--font-signal` with tabular figures, and anything that labels a control in tracked uppercase sans.
- **Do** give repeating rows a fixed height and fixed readout tracks so the column can be swept in one pass.
- **Do** read the layout tokens (`--header-height`, `--action-bar-height`, `--tap-target`, `--keyboard-inset`, `--safe-*`) instead of hardcoding a value one of them already names.
- **Do** pair every engraved division with its catch-light.

### Don't:

- **Don't** mark state with a colored border down one side of a row. Lamps for severity, seated well plus lit underline for selection.
- **Don't** cast a drop shadow onto the panel. Only genuine overlays (modals, popovers) leave the panel plane.
- **Don't** use `--lamp-off` for text; it sits near 2:1 on the panel. Dim text is `--legend-dim`.
- **Don't** let a lit color decorate. If it is not reporting state or arming an action, it is not lit.
- **Don't** style rendered note content with panel chrome. Scope panel heading and legend rules away from `.preview-content`, `.card__preview`, and `.search-preview`.
- **Don't** animate `width` or `height` for a fill or a reveal. Clip it.
- **Don't** make the light scheme white. Both schemes are the same instrument under different room light.
- **Don't** ship a rule no page exercises. There is no build step to tree-shake, so an unused rule ships forever. `main.css` is render-blocking on every route and is held under 22KB gzipped by `tests/test_assets.py`; see [ASSETS.md](./ASSETS.md) for how that number is measured and what it would take to move it.
