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
rounded:
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
    height: "5.5rem"
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

Yak Shears is an instrument you operate at speed, so the interface is a console panel rather than a page of documents. It refuses the arrangement every note app ships: a grey sidebar tree beside a white document pane, with every note drawn as an identical card. The vault is a rack of channel strips, one unit per note, each with its category cap, its readout, and its level meter in the same place. You sweep the readout column, throw a switch, and work in the center section.

Three materials do all the structural work and every component is built from them. The **panel** is the painted face things are mounted on. The **well** is a recess milled into it, where content and inputs sit down. The **engrave** is a groove cut into the panel, drawn as a dark line over a lighter one so it reads as cut rather than as a stroked border. On top of the materials sit the parts: screen-printed legends, anodized caps carrying category color, indicator lamps, and meters with real ballistics.

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

- **Category Anodize** (generated `hsl()`, full-spectrum hue, 58–82% saturation, 48–68% lightness): Not a fixed value. `get_category_color()` hashes the category name (djb2, ported from the author's WezTerm config) into a deterministic hue and picks saturation and lightness from a band held deliberately high. The earlier 25–45% band was mud that disappeared against the dark panel. This color fills the card cap, tints the whole row, lights the level meter, and marks the editor head plate.

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
- **Label** (600, 0.75rem, 0.09em tracking, uppercase): Every key face, nav switch, and control legend.
- **Signal** (400, 0.8125rem, tabular figures): Filenames, paths, dates, counts, tags, and the editor's own text (0.9375rem there).

### Named Rules

**The Legend-Never-Content Rule.** A legend names a control. It never carries the note. Panel heading styles are scoped away from rendered content with `h1:not(.preview-content h1, .card__preview h1, .search-preview h1)`, because a heading the user wrote is theirs and stays a heading.

**The Tabular Column Rule.** Anything that appears at the same position on consecutive rows takes `font-variant-numeric: tabular-nums`. Counts and dates in a rack must line up on the digit or the readout column stops being a column.

## Layout

The container caps at 1200px with gutters that step 1rem → 1.5rem → 2rem at 640px and 768px, each adding the matching `env(safe-area-inset-*)` so content clears the notch. The single breakpoint is **768px**, duplicated as `MOBILE_BREAKPOINT` in `editor.js`, `search.js`, and `nav.js`.

The rack is the defining layout. It is a flex column with a 1px gap over an engrave-colored ground, so the gap shows through as a hairline and the strips read as mounted in one frame rather than as floating cards. Each unit is a three-track grid (`6px | minmax(0,1fr) | auto`) at a fixed `5.5rem` height. The fixed height is load-bearing: notes whose first blocks happen to be short or tall must not change the row pitch. The preview inside is line-clamped to exactly two lines at a fixed `2.2rem`, and block margins are zeroed so a sliced third line never peeks through.

The readout at the right end uses fixed grid tracks (`7rem | 5.5rem | auto`) rather than flex. The point of a readout is that category, date, and patch count land on the same x-position on every row, so the eye reads down a column instead of hunting along each row.

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

Panel hardware is machined, so radii are small and deliberate: 3px on caps, keys, and switches, 5px on chassis corners, and full round only on lamps. Nothing is pillowy. The pill radius survives on two legacy controls and should not spread.

Structure is carried by material rather than by outline. Where a border does appear it is `--engrave`, and it is nearly always paired with its catch-light to read as a cut. The category cap is a full-height 6px bar with an inner catch-light (`inset 1px 0 0 rgba(255,255,255,0.22)`) and an outer contact shadow, which is what makes it read as a machined part rather than a flat colored rule.

The level meter is the system's recurring signature geometry: a 3.5rem × 9px recessed slot carrying a segmented bargraph, drawn as a repeating 3px-on/2px-off mask over both an unlit layer and a lit fill.

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
- **Height:** fixed 5.5rem

### Level Meter (signature component)

Word count read against a 500-word full scale, driven by `--card-fill` (0–1). A recessed 3.5rem × 9px slot holds two masked layers: unlit segments at `rgba(255,255,255,0.1)`, and a lit fill in the category color with a matching glow. The fill is revealed by `clip-path: inset(0 calc((1 - var(--card-fill,0)) * 100%) 0 0)` and transitions on `--settle` (260ms, `cubic-bezier(0.16, 1, 0.3, 1)`), so the needle settles rather than snapping.

Clipping is the correct mechanism here, not merely the compliant one: animating width thrashes layout, and `transform: scaleX` would stretch the segment mask along with the fill.

### Inputs

- **Style:** recessed. Well background, engrave border, well inset, `--signal` text in the mono face. Both the editor and the search field are places the user puts signal in, so they are the same material
- **Focus:** the well inset plus a 2px amber ring, keeping the recess visible underneath
- **Global focus-visible:** `box-shadow: 0 0 0 3px rgba(247, 207, 70, 0.4)` with the outline suppressed

### Navigation

Switches on the panel's top strip: tracked uppercase, dim at rest, `--panel` face with an engrave border on hover, 1px drop on press. The engaged switch seats into the well and lights a 2px amber indicator across its lower edge. Below 768px the wordmark drops, the four links collapse into a `<details>` hamburger, and each link takes a full 44px row.

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
- **Don't** ship a rule no page exercises. There is no build step to tree-shake, the asset budget is 14KB, and the e2e suite fails below 90% CSS rule coverage.
