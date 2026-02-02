# Roadmap

This document outlines the vision and planned development phases for Yak Shears.

## Vision

Transform Yak Shears from a simple note-taking app into a flexible, file-based knowledge management system supporting:
- Structured metadata via YAML frontmatter
- Wiki-style bi-directional linking with auto-suggestions
- User-defined data models (tickets, practice logs, etc.)
- Aggregated views per data model

## Design Principles

1. **File-first**: Djot files are source of truth
2. **Optional metadata**: Notes work without frontmatter
3. **No lock-in**: Files work without Yak Shears
4. **Progressive enhancement**: Basic notes work, advanced features optional
5. **Scandinavian minimalism**: Clean, functional, subtle design

---

## Completed Work

### Phase 0: Foundation (Complete)
- Starlette/HTMX web application
- User authentication with sessions
- Yak listing with pagination/sorting
- Editor with live preview
- Full-text search with DuckDB

### UI Improvements (Complete)
- Scandinavian minimal design system
- Single accent color (yellow #f7cf46)
- Responsive layout (mobile, tablet, desktop)
- Empty states and loading indicators
- Accessibility (ARIA labels, keyboard navigation)
- E2E test coverage (~26 tests)

### Technical Spikes (Complete)
All core technical assumptions validated:
- YAML frontmatter parsing: 0.318ms/file
- Link extraction: 0.010ms/file
- DuckDB backlinks query: 2-3ms
- Metadata UI render: ~20ms

---

## Current Development

### Phase 1: Frontmatter Foundation (In Progress)
- [x] Frontmatter parser
- [x] Database schema for metadata/links
- [x] Link extraction from content
- [x] Index on save
- [ ] Metadata panel UI
- [ ] Backlinks display

### Phase 2: Metadata UI (Planned)
- Right sidebar on edit page
- Display/edit frontmatter key-value pairs
- Write back to file
- Collapsible on mobile

---

## Future Phases

### Phase 3: Link Intelligence
- `[[` autocomplete in editor
- Suggestion algorithm (prefix, recent, frequent)
- Fuzzy link resolution
- Link preview on hover
- Broken link detection

### Phase 4: Data Models
- JSON Schema validation
- Built-in models: Note, Ticket, Practice Log
- Type selector dropdown
- Form generation from schema

### Phase 5: Aggregation Views
- Board view (Kanban for tickets)
- Table view (sortable, inline edit)
- Calendar view (by due date)
- Query engine with DuckDB

### Phase 6: Advanced Features
- Graph visualization
- Custom user-defined data models
- Block references (`[[note#heading]]`)
- Templates for new notes
- Export/import

---

## Use Cases

### Ticket Management
```yaml
---
type: ticket
status: in-progress
priority: high
due_date: 2025-12-15
tags: [backend, database]
---
```

### Language Practice
```yaml
---
type: practice
language: spanish
activity: reading
duration_minutes: 45
practiced_at: 2025-11-23T14:30:00
---
```

---

## Technical Notes

### Performance Targets
- Parse 1000 files in <500ms
- Backlinks query <50ms
- Related notes query <100ms
- UI render <100ms

### Database Schema
```sql
-- Metadata index
CREATE TABLE yak_frontmatter (
    path TEXT PRIMARY KEY,
    frontmatter_json TEXT,
    updated_at TIMESTAMP
);

-- Links graph
CREATE TABLE yak_links (
    source_path TEXT,
    target_path TEXT,
    link_type TEXT,
    PRIMARY KEY (source_path, target_path)
);
```

---

## References

For detailed technical documentation, see:
- `.github/METADATA_LINKING_PLAN.md` - Comprehensive architecture
- `spikes/SPIKE_RESULTS.md` - Spike validation results
