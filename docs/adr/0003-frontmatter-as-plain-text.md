# 0003: Frontmatter Is Edited as Plain Text, Not Through a UI

## Status

Accepted (2026-07-03)

## Context

The original roadmap (Phase 2 "Metadata UI") planned a right-sidebar widget for displaying and editing frontmatter key-value pairs with write-back to the file. Two findings changed this:

- Most real notes (46/52 in the vault) are Apple Notes/iCloud exports using a `: key=value\` metadata block plus a `````=html` raw body, not YAML `---` fences. Any write-back path risks mangling that format
- Round-tripping user files through a form-generated serializer conflicts with the file-first principle (files must survive Yak Shears verbatim)

## Decision

- Frontmatter is edited as plain text in the main editor, like the rest of the note
- The metadata panel is read-only: it renders parsed frontmatter and backlinks, nothing more
- No reformat-on-save; files round-trip verbatim
- `parse_frontmatter` understands both YAML fences and the Apple Notes export block; `name` maps to the title

## Rationale

Editing structured metadata through a widget adds a serializer that must preserve two formats losslessly, for a single-user app whose user is comfortable editing text. The read-only panel delivers the visibility benefit without the data-loss risk.

## Consequences

- `write_frontmatter`/`update_frontmatter`/`remove_frontmatter_field` in `frontmatter.py` are intentionally unwired (see PLAN.md Phase 7 for pruning; `update_frontmatter` has a known blank-line-accumulation bug if ever revived)
- Future assistance takes the form of editor completions for frontmatter keys (like list continuation), not forms
- ROADMAP Phase 4 "form generation from schema" is dropped
