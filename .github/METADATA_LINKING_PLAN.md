# Yak Shears: Metadata, Linking, and Data Models - Comprehensive Plan

> **Reference**: This is the detailed technical plan. For a summary, see [ROADMAP.md](../ROADMAP.md).

**Date**: November 23, 2025
**Status**: Planning Phase
**Goal**: Evolve yak-shears from simple note-taking to flexible knowledge management

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Research: Industry Best Practices](#research-industry-best-practices)
3. [Core Architecture](#core-architecture)
4. [Feature 1: Frontmatter & Metadata](#feature-1-frontmatter--metadata)
5. [Feature 2: Bi-directional Linking](#feature-2-bi-directional-linking)
6. [Feature 3: Flexible Data Models](#feature-3-flexible-data-models)
7. [Feature 4: Aggregation Views](#feature-4-aggregation-views)
8. [UX Design](#ux-design)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Use Case Examples](#use-case-examples)
11. [Technical Challenges](#technical-challenges)
12. [Open Questions](#open-questions)

---

## Executive Summary

**Vision**: Transform yak-shears into a flexible, file-based knowledge management system that supports:
- Structured metadata via YAML frontmatter
- Wiki-style bi-directional linking with auto-suggestions
- User-defined data models (tickets, practice logs, etc.)
- Aggregated views per data model

**Philosophy**:
- Files remain plain Djot markdown (portable, future-proof)
- Metadata stored in frontmatter (readable, standard)
- No lock-in: Files work without yak-shears
- Progressive enhancement: Basic notes work, advanced features optional

**Key Design Principles**:
1. **File-first**: Djot files are source of truth
2. **Optional metadata**: Notes work without frontmatter
3. **Type safety**: Validate metadata against schemas
4. **Performance**: Index links/metadata for fast queries
5. **Simplicity**: Start minimal, add complexity as needed

---

## Research: Industry Best Practices

### Obsidian (2025)

**Frontmatter**:
```yaml
---
tags: [project, active]
status: in-progress
due: 2025-11-30
related: "[[other-note]]"
custom_field: value
---
```

**Key Learnings**:
- YAML between `---` delimiters
- Links in frontmatter must be quoted: `"[[link]]"`
- Support for lists, dates, numbers, booleans
- Properties UI for editing metadata
- ISO date format (YYYY-MM-DD) for reliability

### Notion (2025)

**Database Model**:
- Each database has a schema (up to 50KB)
- Property types: text, number, date, select, multi-select, relation, formula
- Templates with pre-filled properties
- Views: table, board, calendar, gallery, timeline

**Key Learnings**:
- Flexible property types
- Templates reduce friction
- Multiple views of same data
- Formulas for computed fields (advanced)

### Logseq/Roam

**Block-level Metadata**:
```markdown
- TODO Practice Spanish
  scheduled:: [[2025-11-24]]
  duration:: 30min
```

**Key Learnings**:
- Block references for granular linking
- Page properties vs. block properties
- Tag/link equivalence: `#tag` = `[[tag]]`
- Case-insensitive linking

### Standards

**YAML Frontmatter** (de facto standard):
- Used by Jekyll, Hugo, Obsidian, Foam, Dendron
- Portable across tools
- Human-readable
- Well-supported libraries (PyYAML)

---

## Core Architecture

### Data Flow

```
┌─────────────────┐
│  Djot File      │
│  - Frontmatter  │ ←──────┐
│  - Content      │        │
│  - Links        │        │
└────────┬────────┘        │
         │                 │
         ↓                 │
┌─────────────────┐        │
│  Parser         │        │
│  - Extract YAML │        │
│  - Parse links  │        │
│  - Validate     │        │
└────────┬────────┘        │
         │                 │
         ↓                 │
┌─────────────────┐        │
│  Index DB       │        │
│  - Metadata     │        │
│  - Links graph  │        │
│  - Full-text    │        │
└────────┬────────┘        │
         │                 │
         ↓                 │
┌─────────────────┐        │
│  Views          │        │
│  - Edit page    │        │
│  - Aggregations │        │
│  - Graph viz    │        │
└─────────────────┘        │
         │                 │
         ↓                 │
┌─────────────────┐        │
│  Write Back     │ ───────┘
│  - Update YAML  │
│  - Insert links │
└─────────────────┘
```

### Database Schema

**Extend existing DuckDB with**:

```sql
-- Metadata index
CREATE TABLE yak_metadata (
    yak_path TEXT PRIMARY KEY,
    frontmatter_json TEXT,  -- Stored as JSON for flexibility
    data_model TEXT,         -- Which schema to validate against
    updated_at TIMESTAMP,
    FOREIGN KEY (data_model) REFERENCES data_models(name)
);

-- Links graph
CREATE TABLE yak_links (
    source_path TEXT,
    target_path TEXT,
    link_type TEXT,  -- 'wikilink', 'frontmatter', 'tag'
    context TEXT,    -- Surrounding text
    PRIMARY KEY (source_path, target_path, link_type)
);

-- Backlinks (materialized for performance)
CREATE TABLE yak_backlinks (
    target_path TEXT,
    source_path TEXT,
    link_type TEXT,
    count INTEGER,
    PRIMARY KEY (target_path, source_path)
);

-- Data models (user-defined schemas)
CREATE TABLE data_models (
    name TEXT PRIMARY KEY,
    display_name TEXT,
    icon TEXT,
    schema_json TEXT,  -- JSON Schema for validation
    template_frontmatter TEXT,
    view_config_json TEXT,  -- How to aggregate/display
    created_at TIMESTAMP
);

-- Built-in data models
INSERT INTO data_models VALUES
('note', 'Note', '📝', '{}', '', '{}', CURRENT_TIMESTAMP),
('ticket', 'Ticket', '🎫', '...', '...', '...', CURRENT_TIMESTAMP),
('practice', 'Practice Log', '📚', '...', '...', '...', CURRENT_TIMESTAMP);
```

---

## Feature 1: Frontmatter & Metadata

### File Format

**Example Djot file with frontmatter**:

```markdown
---
title: Implement metadata system
type: ticket
status: in-progress
priority: high
tags: [feature, backend]
assigned_to: "[[people/alice]]"
due_date: 2025-12-01
related: ["[[linking-system]]", "[[ux-design]]"]
created: 2025-11-23T10:30:00
---

# Implement metadata system

## Overview
This ticket tracks the implementation of YAML frontmatter...

## Tasks
- [x] Design schema
- [ ] Implement parser
- [ ] Add UI

## Related
See also [[linking-system]] for bi-directional links.
```

### Frontmatter Parser

**Requirements**:
1. Extract YAML between `---` delimiters
2. Validate against data model schema
3. Parse links in frontmatter values
4. Handle missing/malformed YAML gracefully
5. Preserve unknown fields (forward compatibility)

**Python implementation**:
```python
import yaml
from pathlib import Path
from typing import Any, TypedDict

class Frontmatter(TypedDict, total=False):
    """Frontmatter data structure."""
    title: str
    type: str
    tags: list[str]
    created: str
    # ... extensible

def parse_djot_with_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse Djot file with YAML frontmatter.

    Returns:
        (frontmatter_dict, content_without_frontmatter)
    """
    if not content.startswith('---\n'):
        return {}, content

    # Find closing ---
    try:
        end = content.index('\n---\n', 4)
        yaml_content = content[4:end]
        body = content[end+5:].lstrip()

        frontmatter = yaml.safe_load(yaml_content) or {}
        return frontmatter, body
    except (ValueError, yaml.YAMLError):
        # Malformed frontmatter - treat as regular content
        return {}, content
```

### Metadata Validation

**Use JSON Schema for validation**:

```python
from jsonschema import validate, ValidationError

TICKET_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "ticket"},
        "status": {
            "type": "string",
            "enum": ["backlog", "in-progress", "blocked", "done", "archived"]
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"]
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "due_date": {
            "type": "string",
            "format": "date"  # YYYY-MM-DD
        },
        "assigned_to": {"type": "string"},
        "related": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["type", "status"]
}

def validate_frontmatter(frontmatter: dict, schema: dict) -> list[str]:
    """Validate frontmatter against schema.

    Returns:
        List of validation errors (empty if valid)
    """
    try:
        validate(instance=frontmatter, schema=schema)
        return []
    except ValidationError as e:
        return [str(e)]
```

### Reserved Fields

**Standard fields** (all yaks):
- `title`: Display name (defaults to filename)
- `type`: Data model name
- `tags`: List of tags
- `created`: ISO datetime
- `updated`: ISO datetime (auto-managed)

**Type-specific fields** defined in data model schema.

---

## Feature 2: Bi-directional Linking

### Link Syntax

**Support multiple syntaxes**:

1. **Wikilinks** (primary):
   - `[[other-note]]` - Link to note by filename
   - `[[other-note|alias]]` - Link with custom text
   - `[[folder/note]]` - Path-based linking
   - `#tag` - Tag (treated as page link)

2. **Frontmatter links**:
   - Must be quoted: `related: "[[note]]"`
   - Support lists: `related: ["[[a]]", "[[b]]"]`

3. **Future**: Block references
   - `[[note#heading]]` - Link to heading
   - `[[note^blockid]]` - Link to specific block

### Link Detection

**Regex patterns**:
```python
import re

WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
TAG_PATTERN = re.compile(r'(?:^|\\s)#([a-zA-Z0-9_-]+)')

def extract_links(content: str) -> list[tuple[str, str, str]]:
    """Extract all links from content.

    Returns:
        List of (link_type, target, alias) tuples
    """
    links = []

    # Wikilinks
    for match in WIKILINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else target
        links.append(('wikilink', target, alias))

    # Tags
    for match in TAG_PATTERN.finditer(content):
        tag = match.group(1)
        links.append(('tag', tag, tag))

    return links
```

### Link Resolution

**Algorithm**:
1. Normalize target (lowercase, trim)
2. Try exact match on filename
3. Try exact match on `title` frontmatter field
4. Fuzzy match on filenames (Levenshtein distance < 3)
5. Create stub page if no match (optional)

```python
from pathlib import Path
from difflib import get_close_matches

def resolve_link(target: str, yak_dir: Path) -> Path | None:
    """Resolve wikilink target to file path.

    Args:
        target: Link target (e.g., "my-note" or "folder/note")
        yak_dir: Root yak directory

    Returns:
        Resolved Path or None if not found
    """
    # Normalize
    target = target.strip().lower()

    # Exact match
    candidates = [
        yak_dir / f"{target}.dj",
        yak_dir / target,  # If includes extension
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Fuzzy match on all yak files
    all_yaks = list(yak_dir.rglob("*.dj"))
    all_names = [p.stem.lower() for p in all_yaks]

    matches = get_close_matches(target, all_names, n=1, cutoff=0.8)
    if matches:
        idx = all_names.index(matches[0])
        return all_yaks[idx]

    return None
```

### Backlinks Index

**Update on file change**:

```python
async def index_yak_links(yak_path: Path, content: str, db):
    """Index all links in a yak file."""
    links = extract_links(content)

    # Parse frontmatter for links
    frontmatter, _ = parse_djot_with_frontmatter(content)
    for key, value in frontmatter.items():
        if isinstance(value, str) and '[[' in value:
            # Extract link from frontmatter value
            match = WIKILINK_PATTERN.search(value)
            if match:
                links.append(('frontmatter', match.group(1), key))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and '[[' in item:
                    match = WIKILINK_PATTERN.search(item)
                    if match:
                        links.append(('frontmatter', match.group(1), key))

    # Clear old links
    await db.execute(
        "DELETE FROM yak_links WHERE source_path = ?",
        [str(yak_path)]
    )

    # Insert new links
    for link_type, target, context in links:
        resolved = resolve_link(target, yak_path.parent)
        if resolved:
            await db.execute(
                """INSERT INTO yak_links (source_path, target_path, link_type, context)
                   VALUES (?, ?, ?, ?)""",
                [str(yak_path), str(resolved), link_type, context]
            )

    # Update backlinks (materialized view)
    await update_backlinks(db)
```

### Link Auto-Suggestions

**Features**:
1. **Suggest as you type**: Show matching notes in dropdown
2. **Context-aware**: Prioritize recently edited, frequently linked
3. **Smart completion**: `[[impl` suggests "implementation-plan"

**Algorithm**:
```python
def suggest_links(partial: str, current_yak: Path, db, limit=10) -> list[dict]:
    """Suggest link targets based on partial input.

    Returns:
        List of {path, title, score, reason} dicts
    """
    suggestions = []

    # 1. Exact prefix matches on filename
    query = """
        SELECT path, title, updated_at
        FROM yak_metadata
        WHERE LOWER(path) LIKE ? OR LOWER(title) LIKE ?
        ORDER BY updated_at DESC
        LIMIT ?
    """
    results = db.execute(query, [f"{partial}%", f"{partial}%", limit]).fetchall()

    for path, title, updated in results:
        suggestions.append({
            "path": path,
            "title": title or Path(path).stem,
            "score": 1.0,
            "reason": "Name matches"
        })

    # 2. Frequently linked from current context
    if current_yak:
        query = """
            SELECT target_path, COUNT(*) as freq
            FROM yak_links
            WHERE source_path IN (
                SELECT source_path FROM yak_links WHERE target_path = ?
            )
            AND target_path != ?
            GROUP BY target_path
            ORDER BY freq DESC
            LIMIT ?
        """
        results = db.execute(query, [str(current_yak), str(current_yak), 5]).fetchall()

        for path, freq in results:
            if path.lower().startswith(partial.lower()):
                suggestions.append({
                    "path": path,
                    "score": 0.8,
                    "reason": f"Often linked ({freq}x)"
                })

    # 3. Tag matches
    query = """
        SELECT path, frontmatter_json
        FROM yak_metadata
        WHERE frontmatter_json LIKE ?
        LIMIT ?
    """
    results = db.execute(query, [f'%{partial}%', 5]).fetchall()

    for path, fm_json in results:
        fm = json.loads(fm_json)
        if partial.lower() in ' '.join(fm.get('tags', [])).lower():
            suggestions.append({
                "path": path,
                "score": 0.6,
                "reason": "Tag match"
            })

    # Deduplicate and sort by score
    seen = set()
    unique = []
    for s in sorted(suggestions, key=lambda x: x['score'], reverse=True):
        if s['path'] not in seen:
            seen.add(s['path'])
            unique.append(s)

    return unique[:limit]
```

---

## Feature 3: Flexible Data Models

### Data Model Definition

**Each data model defines**:
1. **Schema**: JSON Schema for validation
2. **Template**: Default frontmatter for new notes
3. **View config**: How to display in aggregations
4. **Icon**: Visual identifier

**Example: Ticket data model**:

```json
{
  "name": "ticket",
  "display_name": "Ticket",
  "icon": "🎫",
  "schema": {
    "type": "object",
    "properties": {
      "type": {"const": "ticket"},
      "status": {
        "type": "string",
        "enum": ["backlog", "in-progress", "blocked", "done", "archived"]
      },
      "priority": {
        "type": "string",
        "enum": ["low", "medium", "high", "critical"]
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"}
      },
      "due_date": {
        "type": "string",
        "format": "date"
      },
      "assigned_to": {"type": "string"},
      "estimate": {
        "type": "string",
        "pattern": "^[0-9]+[hdw]$"
      },
      "related": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["type", "status", "priority"]
  },
  "template": {
    "type": "ticket",
    "status": "backlog",
    "priority": "medium",
    "tags": [],
    "created": "{{now}}"
  },
  "view_config": {
    "group_by": "status",
    "sort_by": "priority",
    "columns": ["title", "status", "priority", "due_date", "assigned_to"],
    "filters": ["status", "priority", "tags"]
  }
}
```

**Example: Language Practice data model**:

```json
{
  "name": "practice",
  "display_name": "Language Practice",
  "icon": "📚",
  "schema": {
    "type": "object",
    "properties": {
      "type": {"const": "practice"},
      "language": {
        "type": "string",
        "enum": ["spanish", "french", "japanese", "german"]
      },
      "activity": {
        "type": "string",
        "enum": ["reading", "writing", "listening", "speaking", "grammar"]
      },
      "duration_minutes": {
        "type": "integer",
        "minimum": 1
      },
      "difficulty": {
        "type": "string",
        "enum": ["beginner", "intermediate", "advanced"]
      },
      "topics": {
        "type": "array",
        "items": {"type": "string"}
      },
      "resources": {
        "type": "array",
        "items": {"type": "string"}
      },
      "notes": {"type": "string"},
      "practiced_at": {
        "type": "string",
        "format": "date-time"
      }
    },
    "required": ["type", "language", "activity", "practiced_at"]
  },
  "template": {
    "type": "practice",
    "practiced_at": "{{now}}",
    "duration_minutes": 30
  },
  "view_config": {
    "group_by": "language",
    "sort_by": "practiced_at",
    "columns": ["practiced_at", "language", "activity", "duration_minutes", "topics"],
    "aggregations": {
      "total_time": "SUM(duration_minutes)",
      "sessions": "COUNT(*)",
      "streak": "consecutive_days(practiced_at)"
    }
  }
}
```

### Creating Data Models

**Admin UI** (future):
- Visual schema builder
- Test with sample data
- Export/import data model JSON

**Initial approach**: Pre-defined models in code
```python
# yak_shears/data_models.py

DATA_MODELS = {
    "note": {
        "name": "note",
        "display_name": "Note",
        "icon": "📝",
        "schema": {},  # Accept anything
        "template": {},
        "view_config": {}
    },
    "ticket": TICKET_MODEL,
    "practice": PRACTICE_MODEL,
}
```

---

## Feature 4: Aggregation Views

### View Types

**1. Board View** (Kanban):
- Group by: status, priority, assigned_to
- Drag-and-drop to change status
- Quick edit metadata in modal

**2. Table View**:
- Sortable columns
- Inline editing
- Bulk operations (tag, archive)
- Export to CSV

**3. Calendar View**:
- Show notes by `due_date` or `practiced_at`
- Color-code by status/type
- Click to edit

**4. Timeline View**:
- Gantt chart for tickets
- Practice frequency over time
- Streaks visualization

**5. Graph View**:
- Network graph of links
- Color by type
- Filter by tags
- Click node to navigate

### Query Engine

**Build views with DuckDB queries**:

```python
async def get_ticket_board(db, status_filter: list[str] | None = None):
    """Get tickets grouped by status for board view."""
    query = """
        SELECT
            path,
            JSON_EXTRACT(frontmatter_json, '$.title') as title,
            JSON_EXTRACT(frontmatter_json, '$.status') as status,
            JSON_EXTRACT(frontmatter_json, '$.priority') as priority,
            JSON_EXTRACT(frontmatter_json, '$.due_date') as due_date,
            JSON_EXTRACT(frontmatter_json, '$.assigned_to') as assigned_to,
            JSON_EXTRACT(frontmatter_json, '$.tags') as tags
        FROM yak_metadata
        WHERE data_model = 'ticket'
    """

    if status_filter:
        placeholders = ','.join('?' * len(status_filter))
        query += f" AND JSON_EXTRACT(frontmatter_json, '$.status') IN ({placeholders})"
        results = await db.execute(query, status_filter).fetchall()
    else:
        results = await db.execute(query).fetchall()

    # Group by status
    board = {}
    for row in results:
        status = row['status'] or 'backlog'
        if status not in board:
            board[status] = []
        board[status].append(dict(row))

    return board

async def get_practice_stats(db, language: str | None = None):
    """Get practice session statistics."""
    query = """
        SELECT
            JSON_EXTRACT(frontmatter_json, '$.language') as language,
            JSON_EXTRACT(frontmatter_json, '$.activity') as activity,
            SUM(CAST(JSON_EXTRACT(frontmatter_json, '$.duration_minutes') AS INTEGER)) as total_minutes,
            COUNT(*) as sessions,
            DATE(JSON_EXTRACT(frontmatter_json, '$.practiced_at')) as date
        FROM yak_metadata
        WHERE data_model = 'practice'
    """

    if language:
        query += " AND JSON_EXTRACT(frontmatter_json, '$.language') = ?"
        results = await db.execute(query + " GROUP BY language, activity, date", [language]).fetchall()
    else:
        results = await db.execute(query + " GROUP BY language, activity, date").fetchall()

    return [dict(row) for row in results]
```

### Aggregation Routes

```python
# yak_shears/server/aggregations.py

@app.get("/aggregate/{data_model}")
async def aggregate_view(request: Request, data_model: str):
    """Render aggregation view for a data model."""
    model_config = DATA_MODELS.get(data_model)
    if not model_config:
        return HTMLResponse("Unknown data model", status_code=404)

    view_type = request.query_params.get("view", "board")

    # Get data based on view config
    if data_model == "ticket":
        if view_type == "board":
            data = await get_ticket_board(db)
        elif view_type == "table":
            data = await get_all_tickets(db)
    elif data_model == "practice":
        data = await get_practice_stats(db)

    return render_template(
        f"aggregate/{view_type}.html.jinja",
        data_model=model_config,
        data=data,
        view_type=view_type
    )
```

---

## UX Design

### Metadata Panel

**Location**: Right sidebar on edit page (collapsible)

**Layout**:
```
┌────────────────────────────────────┐
│  Editing: my-note.dj               │
│  ┌──────┐ ┌──────────┐ ┌─────┐    │
│  │Editor│ │Side-by-│ │Preview│    │
│  └──────┘ └──────────┘ └─────┘    │
├────────────────────┬───────────────┤
│                    │ 📋 Metadata   │
│  # My Note         │ ──────────────│
│                    │ Type: ticket  │
│  Content...        │ Status: ⚙️     │
│                    │   in-progress │
│                    │ Priority: 🔴   │
│                    │   high        │
│                    │ Tags:         │
│                    │   + Add tag   │
│                    │ Due: 📅       │
│                    │   2025-12-01  │
│                    │ Related:      │
│                    │   [[link1]]   │
│                    │   [[link2]]   │
│                    │   + Add link  │
│                    │               │
│  [[other-note]]    │ 🔗 Backlinks  │
│                    │ ──────────────│
│                    │ • note-a      │
│                    │ • note-b (2)  │
│                    │               │
│                    │ 🏷️ Tags Graph │
│                    │ ──────────────│
│                    │ [Graph viz]   │
└────────────────────┴───────────────┘
```

**Features**:
1. **Type selector**: Dropdown to change data model
2. **Field editors**: Appropriate input for each type (date picker, select, etc.)
3. **Link autocomplete**: `[[` triggers suggestion dropdown
4. **Tag autocomplete**: Start typing, shows existing tags
5. **Backlinks list**: Clickable links to referring notes
6. **Quick actions**: Archive, duplicate, delete
7. **Validation feedback**: Show errors inline

### Metadata Edit Form

**Generate form from schema**:

```python
def render_metadata_form(frontmatter: dict, schema: dict) -> str:
    """Generate HTML form for editing frontmatter."""
    html = []

    for field_name, field_schema in schema['properties'].items():
        field_type = field_schema.get('type', 'string')
        current_value = frontmatter.get(field_name, '')

        if field_type == 'string' and 'enum' in field_schema:
            # Select dropdown
            options = field_schema['enum']
            html.append(f'''
                <div class="form-field">
                    <label for="{field_name}">{field_name.title()}</label>
                    <select id="{field_name}" name="{field_name}">
                        {render_options(options, current_value)}
                    </select>
                </div>
            ''')
        elif field_type == 'string' and field_schema.get('format') == 'date':
            # Date picker
            html.append(f'''
                <div class="form-field">
                    <label for="{field_name}">{field_name.title()}</label>
                    <input type="date" id="{field_name}" name="{field_name}" value="{current_value}">
                </div>
            ''')
        elif field_type == 'array':
            # Tag/list editor
            html.append(f'''
                <div class="form-field">
                    <label for="{field_name}">{field_name.title()}</label>
                    <div class="tag-editor" data-field="{field_name}">
                        {render_tags(current_value)}
                        <input type="text" placeholder="Add...">
                    </div>
                </div>
            ''')
        else:
            # Text input
            html.append(f'''
                <div class="form-field">
                    <label for="{field_name}">{field_name.title()}</label>
                    <input type="text" id="{field_name}" name="{field_name}" value="{current_value}">
                </div>
            ''')

    return '\n'.join(html)
```

### Link Autocomplete UI

**HTMX-powered autocomplete**:

```html
<input
    type="text"
    name="link-input"
    hx-get="/api/suggest-links?q={value}"
    hx-trigger="input changed delay:300ms"
    hx-target="#link-suggestions"
    placeholder="Type to search..."
>
<div id="link-suggestions" class="autocomplete-dropdown"></div>
```

**Suggestion rendering**:
```html
<!-- Server returns -->
<div class="suggestions">
    <div class="suggestion" data-path="impl.dj">
        <span class="icon">📝</span>
        <div>
            <div class="title">Implementation Plan</div>
            <div class="meta">Updated 2 days ago • Name matches</div>
        </div>
    </div>
    <div class="suggestion" data-path="arch.dj">
        <span class="icon">🏗️</span>
        <div>
            <div class="title">Architecture Design</div>
            <div class="meta">Frequently linked (5x)</div>
        </div>
    </div>
</div>
```

**Keyboard navigation**:
- Arrow keys to navigate
- Enter to select
- Esc to close
- Tab to autocomplete first suggestion

### Mobile Considerations

**Responsive metadata panel**:
- Desktop: Fixed sidebar
- Tablet: Collapsible sidebar (slide out)
- Mobile: Bottom sheet (tap "Metadata" to expand)

---

## Implementation Roadmap

### Phase 1: Foundation (2-3 weeks)

**Goal**: Basic frontmatter support and link detection

**Tasks**:
1. ✅ **Frontmatter parser**
   - Parse YAML between `---`
   - Handle malformed YAML gracefully
   - Extract to dict

2. ✅ **Database schema**
   - Add `yak_metadata` table
   - Add `yak_links` table
   - Migration script

3. ✅ **Link extraction**
   - Regex for `[[wikilinks]]`
   - Extract from content and frontmatter
   - Store in database

4. ✅ **Index on save**
   - Parse frontmatter on file save
   - Update metadata table
   - Update links graph

**Deliverable**: Files with frontmatter are parsed and indexed

### Phase 2: Basic UI (2-3 weeks)

**Goal**: Edit metadata in UI

**Tasks**:
1. ✅ **Metadata panel**
   - Add right sidebar to edit page
   - Display frontmatter key-value pairs
   - Collapsible sections

2. ✅ **Simple form inputs**
   - Text inputs for strings
   - Textarea for long text
   - Basic save functionality

3. ✅ **Write back to file**
   - Update YAML in frontmatter
   - Preserve formatting
   - Handle concurrent edits

4. ✅ **Backlinks display**
   - Show "Referenced by" section
   - Clickable links to sources
   - Count of references

**Deliverable**: Users can edit frontmatter via UI

### Phase 3: Link Intelligence (3-4 weeks)

**Goal**: Smart linking with auto-suggestions

**Tasks**:
1. ✅ **Link autocomplete**
   - Detect `[[` in editor
   - Show suggestion dropdown
   - HTMX-powered search

2. ✅ **Suggestion algorithm**
   - Prefix matching
   - Recently edited
   - Frequently linked
   - Scoring system

3. ✅ **Link resolution**
   - Fuzzy matching
   - Alias support
   - Broken link detection

4. ✅ **Link preview**
   - Hover to see preview
   - Show first paragraph
   - Display metadata

**Deliverable**: Fast, intelligent linking experience

### Phase 4: Data Models (3-4 weeks)

**Goal**: Support ticket and practice log models

**Tasks**:
1. ✅ **Data model system**
   - Define data model structure
   - JSON Schema validation
   - Template system

2. ✅ **Built-in models**
   - Note (default)
   - Ticket (status, priority, due date)
   - Practice (language, activity, duration)

3. ✅ **Type selector**
   - Dropdown to choose model
   - Update schema on change
   - Validate on save

4. ✅ **Form generation**
   - Generate inputs from schema
   - Appropriate controls (date, select, etc.)
   - Inline validation

**Deliverable**: Users can create tickets and practice logs

### Phase 5: Aggregation Views (4-5 weeks)

**Goal**: Board, table, calendar views

**Tasks**:
1. ✅ **Query engine**
   - DuckDB queries for aggregation
   - Filter by model, status, tags
   - Sort, group, count

2. ✅ **Board view**
   - Kanban for tickets
   - Drag-and-drop status change
   - Quick metadata edit

3. ✅ **Table view**
   - Sortable columns
   - Inline editing
   - Bulk operations

4. ✅ **Calendar view**
   - Show by due date / practiced at
   - Color coding
   - Month/week/day views

**Deliverable**: Rich views for different data models

### Phase 6: Advanced Features (Ongoing)

**Future enhancements**:
- Graph visualization
- Custom data models (user-defined)
- Block references (`[[note#heading]]`)
- Templates for new notes
- Formulas in frontmatter (computed fields)
- Export/import
- Public API for extensions

---

## Use Case Examples

### Use Case 1: Project/Ticket Management

**Scenario**: Software team tracking features, bugs, tasks

**Setup**:
1. Create tickets with frontmatter:
   ```yaml
   ---
   type: ticket
   status: in-progress
   priority: high
   assigned_to: "[[people/alice]]"
   due_date: 2025-12-15
   tags: [backend, database]
   related: ["[[design-doc]]", "[[api-spec]]"]
   ---
   ```

2. Use board view to see tickets by status
3. Filter by `assigned_to` to see workload
4. Calendar view for deadlines
5. Link tickets to design docs, meeting notes

**Benefits**:
- File-based (version control, grep-able)
- No vendor lock-in
- Flexible tagging
- Links to context (code, docs, discussions)

### Use Case 2: Language Learning

**Scenario**: Track practice sessions, vocabulary, resources

**Setup**:
1. Create practice log:
   ```yaml
   ---
   type: practice
   language: spanish
   activity: reading
   duration_minutes: 45
   difficulty: intermediate
   topics: [subjunctive, past-tense]
   resources: ["[[book-don-quixote]]"]
   practiced_at: 2025-11-23T14:30:00
   ---

   # Practice: Spanish Reading

   Read chapter 3 of Don Quixote. Focused on subjunctive usage.

   ## New vocabulary
   - **aunque**: although (triggers subjunctive)
   - **quisiera**: I would like

   ## Notes
   Still struggling with imperfect subjunctive. Need more practice.
   ```

2. Dashboard shows:
   - Total practice time by language
   - Streaks (consecutive days)
   - Topics covered
   - Progress over time (chart)

3. Tag resources:
   ```yaml
   ---
   type: resource
   language: spanish
   resource_type: book
   difficulty: advanced
   tags: [classic-literature]
   ---
   ```

4. Query: "What have I practiced this week?"
   - Table view filtered by `practiced_at > 2025-11-17`

**Benefits**:
- Track progress over time
- Link vocabulary to practice sessions
- Identify weak topics (underrepresented)
- Motivational streak tracking

### Use Case 3: Research Notes

**Scenario**: Academic research with papers, ideas, citations

**Setup**:
1. Paper notes:
   ```yaml
   ---
   type: paper
   authors: [Smith et al.]
   year: 2024
   venue: ACL
   tags: [nlp, transformers]
   related: ["[[attention-mechanism]]", "[[bert]]"]
   status: read
   rating: 4/5
   ---
   ```

2. Idea notes:
   ```yaml
   ---
   type: idea
   status: exploring
   related_papers: ["[[smith-2024]]", "[[jones-2023]]"]
   tags: [architecture, efficiency]
   ---
   ```

3. Graph view to see:
   - Which papers cite similar work
   - Clusters of related ideas
   - Unexplored connections

**Benefits**:
- Networked thinking
- See citation graph
- Find related work
- Generate bibliography from links

---

## Technical Challenges

### Challenge 1: Concurrent Edits

**Problem**: User edits frontmatter in UI while file changes on disk

**Solutions**:
1. **File watching**: Detect changes, reload
2. **Optimistic updates**: Update UI immediately, resolve conflicts
3. **Last-write-wins**: Simplest, but loses data
4. **Three-way merge**: Complex but safe

**Recommended**: Optimistic updates + conflict detection
- Show warning if file changed
- Offer to reload or merge

### Challenge 2: Performance with Large Graphs

**Problem**: 10,000+ notes, 100,000+ links → slow queries

**Solutions**:
1. **Materialized views**: Pre-compute backlinks
2. **Indexes**: On frequently queried fields
3. **Pagination**: Don't load all at once
4. **Caching**: Cache suggestion results

**Recommended**: All of the above
```sql
-- Indexes for fast queries
CREATE INDEX idx_links_target ON yak_links(target_path);
CREATE INDEX idx_links_source ON yak_links(source_path);
CREATE INDEX idx_metadata_type ON yak_metadata(data_model);
CREATE INDEX idx_metadata_updated ON yak_metadata(updated_at DESC);
```

### Challenge 3: Schema Evolution

**Problem**: User changes data model schema, old files invalid

**Solutions**:
1. **Versioning**: Track schema version in file
2. **Migration scripts**: Auto-update on load
3. **Backwards compatibility**: Optional fields
4. **Validation warnings**: Don't block, just warn

**Recommended**: Combination
```yaml
---
_schema_version: 2  # Internal tracking
type: ticket
status: in-progress  # Required in v2
legacy_field: value  # Ignored but preserved
---
```

### Challenge 4: Link Rot

**Problem**: File renamed/moved → links break

**Solutions**:
1. **Refactoring**: Update all links on rename
2. **Aliases**: Use frontmatter `aliases: [old-name]`
3. **Redirects**: Create stub file with redirect
4. **Broken link report**: Show all broken links

**Recommended**: Aliases + refactoring
```python
async def rename_yak(old_path: Path, new_path: Path, db):
    """Rename yak and update all links."""
    # Get all referring links
    links = await db.execute(
        "SELECT source_path FROM yak_links WHERE target_path = ?",
        [str(old_path)]
    ).fetchall()

    # Update each referring file
    for source_path in links:
        content = Path(source_path).read_text()
        old_name = old_path.stem
        new_name = new_path.stem
        updated = content.replace(f"[[{old_name}]]", f"[[{new_name}]]")
        Path(source_path).write_text(updated)

    # Move file
    old_path.rename(new_path)

    # Update database
    await reindex_all_affected(db, links + [new_path])
```

### Challenge 5: Mobile Editing

**Problem**: Touch keyboard → hard to type `[[`

**Solutions**:
1. **Quick insert button**: Toolbar button for `[[`
2. **Voice input**: Detect "link to [note name]"
3. **Recent links**: Dropdown of recent links
4. **Hashtag equivalence**: `#tag` creates page link

**Recommended**: Quick insert + recent links

---

## Open Questions

**For Discussion**:

1. **How far to go with data models?**
   - Start with 3-4 built-in models?
   - Allow user-defined models from day 1?
   - When to add visual schema builder?

2. **Frontmatter vs. inline metadata?**
   - Pure YAML frontmatter (Obsidian style)?
   - Allow inline `key:: value` (Logseq style)?
   - Both?

3. **Link syntax preference?**
   - `[[wikilinks]]` only?
   - Also support `#tags` as page links?
   - Markdown `[links](path)`?

4. **Aggregation complexity?**
   - Simple groups/filters?
   - Full SQL-like query builder?
   - Pre-defined views only?

5. **Graph visualization**:
   - D3.js (powerful, complex)?
   - Cytoscape.js (graph-focused)?
   - Simple SVG (minimal)?

6. **Authentication for aggregation views?**
   - Same as current (email login)?
   - Per-view permissions?
   - Public read-only views?

7. **Performance targets?**
   - Support how many notes? (1K, 10K, 100K?)
   - Link suggestion latency? (<100ms, <500ms?)
   - Graph render time? (<1s, <5s?)

8. **File format extensions?**
   - Support existing Obsidian vaults?
   - Import from Notion/Roam?
   - Export to standard formats?

---

## Next Steps

**Immediate Actions**:

1. **Review this plan**:
   - Is the vision aligned with your goals?
   - Are the use cases compelling?
   - Is the scope appropriate?

2. **Prioritize features**:
   - Which phases are must-have?
   - What can be deferred?
   - Any missing critical features?

3. **Decide on data models**:
   - Start with ticket + practice?
   - Add others (habit, book, person, etc.)?
   - User-defined vs. pre-built?

4. **UX validation**:
   - Sketch mockups of key screens
   - Test metadata panel concept
   - Validate aggregation views

5. **Technical validation**:
   - Prototype frontmatter parser
   - Test DuckDB query performance
   - Evaluate link suggestion speed

**Decision Points**:

- **Go/No-Go**: Is this the right direction?
- **Scope**: Full roadmap or MVP first?
- **Timeline**: Aggressive (3 months) or relaxed (6 months)?
- **Resources**: Solo or invite contributors?

**I'm ready to**:
- Refine any section based on feedback
- Create detailed mockups for UX
- Prototype critical components
- Start Phase 1 implementation

What aspects would you like to explore further?
