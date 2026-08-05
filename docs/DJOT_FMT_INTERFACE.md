# What yak-shears needs from djot-fmt

Yak-shears reimplements a fair amount of djot in regexes, in two languages, because
there was no library to call. This lists what it carries, ranked by how well it
would sit in a general djot library, so djot-fmt can decide what to absorb.

Nothing here is a request to change formatting behaviour. It is all parsing and
structured editing that happens to need the same line and block model the formatter
already builds.

## Constraint that shapes everything: verbatim round-trip

Yak-shears edits notes people are also editing by hand and syncing with Syncthing.
A write that reformats untouched lines shows up as a spurious sync conflict and as
noise in `git diff`.

So every mutating call below must change only the lines it was asked to change and
leave the rest byte for byte identical, including trailing whitespace, blank line
runs, and comments. That rules out parse-to-AST-then-render for the editing API.
`yak_shears/frontmatter.py:rewrite_frontmatter_field` exists precisely because
`update_frontmatter` (YAML round-trip) reorders keys and drops comments.

A formatter is allowed to normalise, because the user asked for it. An editing call
is not.

## Tier 1: pure djot, no yak-shears concepts

These are the strongest candidates. Yak-shears has no business owning any of them.

### Line classification

`yak_shears/static/js/editor.js` carries `LIST_PATTERNS` (bullet, ordered,
checklist-checked, checklist-unchecked), `BULLET_PREFIX_RE`, and `LINE_CONTENT_RE`;
`yak_shears/_yak/lists.py` carries `_ITEM_RE`; `yak_shears/_yak/habits.py` carries
`_COMPLETION_RE`. All of them are answering the same question and disagreeing at the
edges. `LINE_CONTENT_RE` accepts `1)` as an ordered marker, `_ITEM_RE` accepts
`*` and `+` bullets, and `BULLET_PREFIX_RE` accepts only `-`.

What is needed, given one line:

- is it a list item, and of which kind (bullet, ordered, checklist)
- its indent width, marker text, checkbox state, and content span (byte offsets, so
  a caller can splice without rebuilding the line)

Offsets rather than a rebuilt string is the important part. The editor needs to
restore a caret position after an edit.

### Structured line edits

Each takes source text plus a line or span and returns source text, touching only
those lines:

- toggle bullet on and off, preserving any checkbox
- toggle a checkbox between `[ ]` and `[x]`
- indent and outdent, which needs the parent item's indent to refuse an indent that
  would skip a level (`editor.js:_indentSelection`)
- continue a list on newline, including ending the list when the item is empty
  (`editor.js:_handleListContinuation`)
- renumber an ordered list (the "all `1.`" normalisation, and the one item on this
  list djot-fmt likely already does)

These are ~350 lines of `editor.js` and the only reason that file is 1400 lines. They
are also the ones most likely to be subtly wrong, since they are tested only through
the browser.

### Inline marker toggles

`editor.js:_toggleInlineMarker` wraps and unwraps a span in `_`, `*`, and friends.
Needs to know djot's inline nesting rules to avoid producing `**bold**` where djot
wants `*bold*`. Currently it does not.

### Word and text extraction

`yak_shears/_yak/database.py` splits body text into words for the search index and
`derive_title` pulls the first heading. Both currently see raw source, so they index
markup characters and can title a note from a line that is not a heading. A library
call that yields plain text with source offsets would fix both.

## Tier 2: conventions djot has no opinion on

These need a home, but they are not djot. If djot-fmt takes them it should be behind
an explicit opt-in, since they are conventions rather than syntax.

### Frontmatter

`yak_shears/frontmatter.py`. Two formats in the wild here:

- YAML delimited by `---`, which is a Jekyll convention, not djot
- Apple Notes and iCloud exports, whose leading lines look like `: name=value\`
  where the trailing backslash is a djot hard break

What yak-shears needs:

- detect and split a frontmatter block from the body, returning the body's offset
  so links and words can be indexed with positions that map back to the file
- read one scalar field
- write or delete one scalar field, rewriting only that field's lines and leaving
  everything else byte identical, which includes consuming a multi-line block value
  along with its key line

The last one is the load-bearing call. It is what makes board and stream writes safe
to run against a file the user has open elsewhere.

Serialization format is negotiable on this end. YAML today, and TOML or JSON would
be fine, so long as one file's format is detected rather than configured, since
existing notes cannot be migrated in bulk without breaking the verbatim guarantee.

### Wikilinks and tags

`yak_shears/links.py` carries `WIKILINK_RE` (`[[target|label]]`) and `TAG_RE`
(`#tag`). Both are Obsidian and Roam conventions rather than djot, but every djot
note-taking tool will grow them, and getting `#tag` right means not matching inside
a code span or a URL fragment, which a regex over raw source cannot do and a parser
can. Yak-shears' `TAG_RE` gets this wrong today.

## Tier 3: stays here

Listing these so the boundary is explicit. They read djot but encode yak-shears
product decisions, and a general library should not carry them:

- habit schedules, streaks, and makeup days (`_yak/habits.py`)
- stream and board actions, and their inverses for undo (`_yak/board.py`)
- category-to-colour mapping, filename conventions, recency buckets
- preview truncation rules

Each of these would be a thin caller once tier 1 exists. `_toggle_today` in
`habits.py`, for instance, is date logic wrapped around a checkbox toggle that tier 1
would own.

## Shape of the interface

Two consumers with different needs:

- **Python, server side.** A wheel per platform vendoring the Go binary, called over
  stdin and stdout, is enough for whole-file operations. It is not enough for
  per-keystroke line edits, so if the editing API is the goal, an importable
  extension module matters more than the CLI.
- **JavaScript, in the editor.** `editor.js` runs these on every keystroke against
  the CodeJar buffer, so a network round trip is out. That points at a WASM build,
  which the repo does not have a target for today. Without one, the line
  classification and edit rules stay duplicated in JS and the two copies keep
  drifting, which is the situation now.

A single source of truth compiled to both is the outcome worth aiming at. If only
one lands first, the Python side is the safer half, because its callers
(`lists.py`, `habits.py`, `board.py`) write files, and the JS side only edits a
buffer the user can see.

### Errors

Editing calls need to refuse rather than guess: an ordinal that no longer exists, a
checkbox toggle on a line that is not a checkbox, an indent with no parent. Yak-shears
turns each of those into a user-visible message (`lists.py` already returns "Item not
found; the note may have changed"), so a typed error beats a best-effort result.
