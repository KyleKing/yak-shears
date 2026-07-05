# Roadmap

Vision and long-term direction for Yak Shears. For concrete sequenced work, see [PLAN.md](./PLAN.md); for current state, see [STATUS.md](./STATUS.md).

## Vision

A flexible, file-based knowledge management system supporting:
- Structured metadata via frontmatter (edited as plain text, rendered read-only; see ADR 0003)
- Wiki-style bi-directional linking with auto-suggestions
- Media attachments that live inside the synced vault (see ADR 0004)
- Aggregated views over note metadata

## Design Principles

1. **File-first**: Djot files are source of truth; files round-trip verbatim
2. **Optional metadata**: Notes work without frontmatter
3. **No lock-in**: Files work without Yak Shears
4. **Progressive enhancement**: Basic notes work, advanced features optional
5. **Scandinavian minimalism**: Clean, functional, subtle design

## Completed

- Phase 0 foundation: Starlette/HTMX app, auth, listing, editor with live preview, DuckDB search
- Scandinavian minimal design system with E2E coverage (see `archive/IMPROVEMENTS.md`)
- Frontmatter parsing (YAML and Apple Notes export format), link extraction, backlinks storage
- Media upload with transcoding, thumbnails, and doctor view

## Near Term

Sequenced in [PLAN.md](./PLAN.md): Hetzner deployment (Phase 1), data-integrity and auth hardening (2), media hardening (3), search backend abstraction with ripgrep/DuckDB FTS (4), link intelligence (5).

### Link Intelligence (PLAN.md Phase 5)

- `[[` autocomplete in editor (prefix, recent, frequent)
- Fuzzy link resolution and broken-link detection (doctor-style report first)
- Link preview on hover
- Frontmatter key completion in the editor

## Longer Term

### Semantic Search (PLAN.md Phase 6)

Hybrid keyword + vector search as a **separate general-purpose CLI**, integrated through the SearchBackend seam (ADR 0002). Blueprint preserved in `archive/djot-search-sqlite-exploration.md`.

### Data Models and Aggregation

Reduced from the original phases 4-6 after the frontmatter decision (no form generation):
- Optional schema validation for known `type:` values (report-style, like the doctor view)
- Table view over frontmatter (sortable), board view for task-like notes
- Query engine over the metadata store
- Graph visualization, block references (`[[note#heading]]`), templates for new notes, export/import

### CLI Ideas (from 2026-07 planning notes)

A possible `shears` companion CLI over the same vault:
- `shears new (evergreen|personal|work)?` with the category ("yak pen") set via env var or argument; or reconsider one flat directory with category as metadata
- `shears list -order=(created|modified|count-links|...)` defaulting to most recently modified
- Note state lifecycle: no state initially, manually promoted to `Atomic` once reviewed; tasks are notes with `state: backlog|queue|in-progress|complete|not-planned` (no `on-hold`: partially complete subtasks self-document and return to `queue`)
- `shears split <name>?` / `shears merge <from>? <to>?` with interactive selection, recording `split-from` / `merged-from` frontmatter so links to deleted/moved notes stay resolvable
- `shears link <from?> <to?>` managing a `links:` list (bi-directionality comes from the database, not the file)
- Planning metadata for time-sensitive tasks: `start-date`, `soft-deadline`, `hard-deadline`
- Bookmarklet notes managed by a browser extension, to archive tabs instead of cluttering the bookmarks bar
- Trip-planning note type (location, cost, must-see, category, best time, dates) enabling dynamic calendar scheduling and nearby lookups

## Performance Targets

- Parse 1000 files in <500ms (validated: 0.318ms/file)
- Backlinks query <50ms (validated: 2-3ms)
- Related notes query <100ms
- UI render <100ms

## References

- `adr/` — decision records
- `archive/METADATA_LINKING_PLAN.md` — original detailed architecture (partially superseded by ADR 0003)
- The `spikes/` directory was removed in 2026-07 (all spikes validated and integrated); results survive in git history and the numbers above
