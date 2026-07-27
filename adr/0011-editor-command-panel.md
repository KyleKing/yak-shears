# 0011: The Editor Command Panel

## Status

Proposed (2026-07-27). Supersedes the fixed accessory bar chosen in ADR 0008, which stays the record of why a web page cannot supply a real keyboard accessory view.

## Context

ADR 0008 chose an in-page bar pinned above the software keyboard, positioned from `visualViewport`. On device it lands underneath Safari's form assistant, the grey strip of previous/next arrows and Done that iOS draws above the keyboard. The toolbar renders, and Apple's bar covers it.

That defect is recorded in ADR 0008 with sources. Three findings from it drive this decision:

- A page cannot measure the form assistant, detect it, or hide it. It is absent from the DOM, fires no event, and reports no height. Any allowance for it is a hard-coded guess that varies by device, orientation, and iOS version
- The bar appears in the homescreen web app too, because the accessory view belongs to the keyboard rather than to browser chrome
- Whether `visualViewport.height` subtracts the assistant is unspecified. There is a second possible cause in our own arithmetic (`offsetTop` shrinking the computed inset once the page scrolls under the visual viewport) that produces the same picture

The two causes point the same way. The strip directly above the keyboard is contested space that we do not control and cannot measure, so nothing of ours should live there.

There is a second problem the fixed bar never addressed. Indent and outdent are the commands reached for most, and each press costs one tap. Outdenting a list item four levels is four taps at a target the thumb has to hit four times.

## Decision

Replace the always-present bar with a command panel that opens on demand from a movable trigger. The panel composes one instruction (a count, a scope, and a set of commands), applies it, and closes.

### Where it lives

A small trigger tab pinned to the left or right edge of the editor, drawn from boxes and borders per the Drawn-Mark Rule rather than typed as a glyph. Dragging it moves it within an allowed band, and its position persists the way the wrap preference already does. The band excludes the contested bottom strip, so the trigger can never be parked under Apple's bar.

The panel opens on the same edge the trigger sits on, which is what keeps one-handed use working for either hand: the thumb that reached the trigger reaches every command without crossing the screen.

Neither the trigger nor the open panel may cover the line being edited. The caret rectangle is known, so the panel opens on the far side of it and the trigger's allowed band is checked against it.

### When it appears

Only while the editor holds focus and there is a caret or a selection. Every command acts on a cursor position, so a panel with nothing to act on is occlusion for its own sake.

Availability keys off `matchMedia("(pointer: coarse)")` rather than the 768px breakpoint. A touchscreen is what makes the keyboard commands unreachable, so an iPad qualifies and a narrow desktop window does not.

### One instruction

Everything the panel does is one instruction with three parts: a count, a scope, and a set of commands. Applying it fires the instruction and closes the panel. Cancelling discards it and closes the panel. The panel is never left open holding state.

Two speeds reach that instruction, and the difference between them is the only mode in the design:

- **Tap a command.** It fires at the current count and scope, and the panel closes. This is the common case (one emphasis, one outdent) and it costs one tap
- **Compose.** Taps light commands instead of firing them, and nothing happens until Apply. This is how bold and insert land together, or a count plus outdent plus bold on one line

In compose, a second tap on a lit command turns it off. Tapping a command twice never means doing it twice, because repetition is the count's job. An impatient thumb cannot double-apply anything.

### The repeat count

A count of 2 through 5, borrowed from vim, where a number before a motion repeats it. One press outdents four levels the way holding Shift+Tab does on a desktop keyboard.

**Every command stays tappable at every count.** Commands the count multiplies carry a tint while a count is set, and commands it cannot multiply stay untinted and ignore it. Bold at count 3 is bold once.

This is the simplification the whole panel rests on. The alternative (disabling commands a count cannot repeat) needs a rule for every pairing of count and command, and a user who has to work out why a key went dead. The tint says which keys the count reaches and costs one class. In code the only rule is a set of which commands repeat, and applying one is "run it n times if it repeats, once if it does not". There is no validity matrix to get wrong.

A repeated command stops early when the next repetition is not valid Djot, rather than refusing the whole run. Outdenting five levels from three levels deep outdents three times.

### Scope, when there is nothing selected

With a selection, the selection is the scope and there is nothing to decide.

With only a caret, a scope switch picks the target: **line** by default, **word** when thrown. Bold on line wraps the whole line, bold on word wraps the word the caret is touching. The switch goes quiet whenever a selection exists, because it has no say then.

Today an inline command with no selection inserts a bare pair of markers and parks the caret between them, which is typing assistance rather than a command. The scope switch replaces that with something that acts on text already written, which is what the panel is for.

### Commands

The same commands the desktop key bindings call, which is ADR 0008's standing rule and does not change here. The panel is a second entry point, and the key bindings stay.

## Open: what underline maps to

Djot has no underline. `*` is strong and `_` is emphasis, which are the two inline commands that exist today. The nearest thing is `{+insert+}`, which renders as `<ins>` and which browsers underline by default.

So a bold-and-underline pairing needs one of: an insert command added to the panel, or a reading of "underline" as emphasis. Worth settling before the inline commands are built, because it decides whether the panel carries two inline keys or three.

## Alternatives considered

- **A strip along the top of the editor, always visible.** Never contends with the keyboard, needs no viewport arithmetic, and costs zero taps. Rejected because it spends a row of editor height permanently on a phone, where the keyboard has already taken half the screen, and because a control at the top is the wrong end of the device for a thumb
- **Folded into the Save and Menu action bar.** One bottom bar instead of two. Rejected because that bar sits in the same contested strip while typing, so reaching a command means dismissing the keyboard first
- **Keep the bar and add a fixed offset for Apple's.** The smallest change. Rejected because the offset is a magic number nothing can measure, and it breaks on the first device, orientation, or iOS version that draws the assistant at another height

## Consequences

- A command costs a tap to open the panel, which is worse than the fixed bar for a single command and better for any command repeated more than twice
- The panel has state (open, count, scope, lit commands, and trigger position) where the bar had almost none, so it needs its own tests rather than riding on the existing toolbar specs
- Compose is a mode, and modes are the thing this design otherwise avoids. It earns its place by being the only one, by ending in Apply or Cancel every time, and by leaving the single-tap path untouched
- Scope means inline commands act on text the user did not select, so an undo path matters more than it did when they only inserted markers at the caret
- Trigger position and count both need a defined reset, or a trigger dragged somewhere awkward becomes a bug the user cannot undo
- Keying off `pointer: coarse` widens the surface to iPad and to touchscreen laptops, which have never been tested here
- The `--keyboard-inset` measurement stays, because the panel still has to open clear of the keyboard. Its arithmetic should be checked against a device readout of `innerHeight`, `visualViewport.height`, and `offsetTop` first, since ADR 0008 leaves the `offsetTop` term unresolved

## Revisit when

- Safari ships the VirtualKeyboard API, which replaces the viewport arithmetic with `env(keyboard-inset-height)` and makes the contested strip measurable
- Compose turns out to be reached often enough that it should be the default, or rarely enough that it should go
- The underline question above is settled, which decides whether an insert command joins the panel
- A native shell (ADR 0008 Option C) is built, because a real `inputAccessoryView` removes the reason this panel exists
