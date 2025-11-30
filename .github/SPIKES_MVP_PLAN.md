# Yak Shears Metadata & Linking: Spikes & MVP Plan

> **Reference**: Spikes completed. See [spikes/SPIKE_RESULTS.md](../spikes/SPIKE_RESULTS.md) for results and [ROADMAP.md](../ROADMAP.md) for current progress.

**Goal**: Validate core technical concepts and deliver a minimal but functional linking system.

---

## Technical Spikes (Week 1)

### Spike 1: YAML Frontmatter Parsing ⚡
**Question**: Can we reliably parse YAML frontmatter in Djot files?

**Tasks**:
1. Parse `---\nYAML\n---` pattern
2. Handle edge cases (malformed, missing, nested)
3. Preserve formatting on write-back
4. Benchmark performance (100, 1000, 10000 files)

**Success Criteria**:
- Parse 1000 files in <100ms
- No data loss on write-back
- Graceful handling of bad YAML

**Prototype** (`spikes/frontmatter_parser.py`):
```python
import yaml
from pathlib import Path
from typing import Any

def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from content."""
    if not content.startswith('---\n'):
        return {}, content

    try:
        end_idx = content.index('\n---\n', 4)
        yaml_str = content[4:end_idx]
        body = content[end_idx + 5:].lstrip()

        fm = yaml.safe_load(yaml_str) or {}
        return fm, body
    except (ValueError, yaml.YAMLError) as e:
        print(f"Parse error: {e}")
        return {}, content

def write_frontmatter(frontmatter: dict, body: str) -> str:
    """Write frontmatter and body to string."""
    if not frontmatter:
        return body

    yaml_str = yaml.dump(frontmatter,
                         default_flow_style=False,
                         allow_unicode=True,
                         sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"

# Test
test_content = """---
title: Test Note
tags: [python, parsing]
created: 2025-11-23
---

# Test Note

Content here with [[wikilink]].
"""

fm, body = parse_frontmatter(test_content)
print("Frontmatter:", fm)
print("Body:", body[:50])

# Round-trip test
reconstructed = write_frontmatter(fm, body)
fm2, body2 = parse_frontmatter(reconstructed)
assert fm == fm2
assert body.strip() == body2.strip()
print("✅ Round-trip successful")
```

**Risks**:
- YAML ordering not preserved (solution: use `ruamel.yaml`)
- Comments lost (acceptable for MVP)
- Complex YAML edge cases (multi-line strings, anchors)

---

### Spike 2: Link Detection & Resolution ⚡
**Question**: Can we accurately detect and resolve wikilinks?

**Tasks**:
1. Regex for `[[wikilink]]` and `[[link|alias]]`
2. Fuzzy matching for link targets
3. Handle relative paths, spaces, special chars
4. Performance with 10,000 files

**Success Criteria**:
- 99%+ accuracy on link detection
- Resolve links in <10ms each
- Handle ambiguous names

**Prototype** (`spikes/link_detector.py`):
```python
import re
from pathlib import Path
from difflib import get_close_matches

WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')

def extract_wikilinks(content: str) -> list[tuple[str, str]]:
    """Extract (target, alias) tuples from content."""
    matches = []
    for match in WIKILINK_RE.finditer(content):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else target
        matches.append((target, alias))
    return matches

def resolve_link(target: str, yak_dir: Path) -> Path | None:
    """Resolve wikilink target to file path."""
    target_lower = target.lower().replace(' ', '-')

    # Exact match
    exact = yak_dir / f"{target_lower}.dj"
    if exact.exists():
        return exact

    # Fuzzy match
    all_yaks = list(yak_dir.rglob("*.dj"))
    all_names = [p.stem.lower() for p in all_yaks]

    matches = get_close_matches(target_lower, all_names, n=1, cutoff=0.7)
    if matches:
        idx = all_names.index(matches[0])
        return all_yaks[idx]

    return None

# Test
test_content = """
# My Note

See [[implementation-plan]] for details.
Also check [[Implementation Plan|the plan]] (alias test).
Related: [[impl plan]] (fuzzy match test).
"""

links = extract_wikilinks(test_content)
print(f"Found {len(links)} links:")
for target, alias in links:
    print(f"  {target} → {alias}")

# Test resolution (mock directory)
test_dir = Path("tests/test_data/mock_djot_dir_0")
if test_dir.exists():
    resolved = resolve_link("yak1", test_dir)
    print(f"\nResolved 'yak1' → {resolved}")

    # Fuzzy match
    resolved = resolve_link("yak 1", test_dir)
    print(f"Resolved 'yak 1' (fuzzy) → {resolved}")
```

**Risks**:
- False positives (code blocks with `[[`, Djot syntax)
- Performance with large files (solution: stream parsing)
- Case sensitivity issues across platforms

---

### Spike 3: DuckDB Link Graph Queries ⚡
**Question**: Can DuckDB efficiently query bi-directional link graphs?

**Tasks**:
1. Schema design for links table
2. Query for backlinks
3. Query for "related" (shared links)
4. Performance with 10K notes, 100K links

**Success Criteria**:
- Backlinks query <50ms
- Related notes query <100ms
- Efficient indexing

**Prototype** (`spikes/link_graph.py`):
```python
import duckdb
import time
from pathlib import Path

# Schema
con = duckdb.connect(':memory:')

con.execute("""
    CREATE TABLE yak_links (
        source_path TEXT,
        target_path TEXT,
        link_type TEXT,
        PRIMARY KEY (source_path, target_path)
    )
""")

con.execute("""
    CREATE INDEX idx_target ON yak_links(target_path)
""")

# Insert test data
test_links = [
    ('note-a.dj', 'note-b.dj', 'wikilink'),
    ('note-a.dj', 'note-c.dj', 'wikilink'),
    ('note-c.dj', 'note-b.dj', 'wikilink'),
    ('note-d.dj', 'note-b.dj', 'wikilink'),
]

con.executemany(
    "INSERT INTO yak_links VALUES (?, ?, ?)",
    test_links
)

# Query 1: Get backlinks for a note
start = time.perf_counter()
backlinks = con.execute("""
    SELECT source_path, COUNT(*) as count
    FROM yak_links
    WHERE target_path = ?
    GROUP BY source_path
""", ['note-b.dj']).fetchall()
elapsed = time.perf_counter() - start

print(f"Backlinks for 'note-b.dj': {backlinks}")
print(f"Query time: {elapsed*1000:.2f}ms")

# Query 2: Get related notes (notes that share outbound links)
start = time.perf_counter()
related = con.execute("""
    SELECT
        l2.source_path as related_note,
        COUNT(DISTINCT l1.target_path) as shared_links
    FROM yak_links l1
    JOIN yak_links l2 ON l1.target_path = l2.target_path
    WHERE l1.source_path = ?
      AND l2.source_path != ?
    GROUP BY l2.source_path
    ORDER BY shared_links DESC
    LIMIT 10
""", ['note-a.dj', 'note-a.dj']).fetchall()
elapsed = time.perf_counter() - start

print(f"\nRelated to 'note-a.dj': {related}")
print(f"Query time: {elapsed*1000:.2f}ms")

# Benchmark with larger dataset
print("\n--- Benchmark with 10K links ---")
import random

# Generate synthetic links
num_notes = 1000
num_links = 10000

synthetic_links = []
for _ in range(num_links):
    source = f"note-{random.randint(0, num_notes)}.dj"
    target = f"note-{random.randint(0, num_notes)}.dj"
    if source != target:
        synthetic_links.append((source, target, 'wikilink'))

con.execute("DELETE FROM yak_links")
con.executemany("INSERT INTO yak_links VALUES (?, ?, ?)", synthetic_links)

# Benchmark backlinks
target = "note-500.dj"
start = time.perf_counter()
backlinks = con.execute(
    "SELECT source_path FROM yak_links WHERE target_path = ?",
    [target]
).fetchall()
elapsed = time.perf_counter() - start

print(f"Backlinks for {target}: {len(backlinks)} found in {elapsed*1000:.2f}ms")
```

**Risks**:
- Query complexity for deep graphs (6+ degrees)
- Memory usage with materialized views
- Concurrent read/write performance

---

### Spike 4: Metadata UI Interaction ⚡
**Question**: Can we build a responsive metadata panel with good UX?

**Tasks**:
1. Right sidebar layout (desktop)
2. Bottom sheet (mobile)
3. Form generation from schema
4. HTMX for live updates

**Success Criteria**:
- Renders in <100ms
- Smooth animations
- Works on mobile

**Prototype** (`spikes/metadata_ui_mockup.html`):
```html
<!DOCTYPE html>
<html>
<head>
    <title>Metadata Panel Spike</title>
    <style>
        body {
            margin: 0;
            font-family: system-ui, -apple-system, sans-serif;
            background: #f5f3ef;
        }
        .layout {
            display: grid;
            grid-template-columns: 1fr 320px;
            height: 100vh;
            gap: 0;
        }
        .editor-area {
            padding: 2rem;
            overflow-y: auto;
        }
        .metadata-panel {
            background: white;
            border-left: 1px solid #d9d4cc;
            padding: 1.5rem;
            overflow-y: auto;
        }
        .metadata-section {
            margin-bottom: 2rem;
        }
        .metadata-section h3 {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #666;
            margin: 0 0 1rem 0;
        }
        .form-field {
            margin-bottom: 1rem;
        }
        .form-field label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 0.25rem;
            color: #333;
        }
        .form-field input,
        .form-field select {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #d9d4cc;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        .form-field input:focus,
        .form-field select:focus {
            outline: none;
            border-color: #f7cf46;
            box-shadow: 0 0 0 3px rgba(247, 207, 70, 0.1);
        }
        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        .tag {
            background: #f0f0f0;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .tag button {
            background: none;
            border: none;
            cursor: pointer;
            padding: 0;
            color: #999;
        }
        .backlinks-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .backlinks-list li {
            padding: 0.5rem 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .backlinks-list a {
            color: #333;
            text-decoration: none;
        }
        .backlinks-list a:hover {
            color: #f7cf46;
            text-decoration: underline;
        }

        @media (max-width: 768px) {
            .layout {
                grid-template-columns: 1fr;
                grid-template-rows: 1fr auto;
            }
            .metadata-panel {
                border-left: none;
                border-top: 1px solid #d9d4cc;
                max-height: 50vh;
            }
        }
    </style>
</head>
<body>
    <div class="layout">
        <div class="editor-area">
            <h1>Implementation Plan</h1>
            <p>Content area with editor...</p>
            <p>See [[architecture-design]] for system design.</p>
            <p>Related to #backend and #database tags.</p>
        </div>

        <div class="metadata-panel">
            <div class="metadata-section">
                <h3>📋 Properties</h3>

                <div class="form-field">
                    <label for="type">Type</label>
                    <select id="type">
                        <option>note</option>
                        <option selected>ticket</option>
                        <option>practice</option>
                    </select>
                </div>

                <div class="form-field">
                    <label for="status">Status</label>
                    <select id="status">
                        <option>backlog</option>
                        <option selected>in-progress</option>
                        <option>done</option>
                        <option>archived</option>
                    </select>
                </div>

                <div class="form-field">
                    <label for="priority">Priority</label>
                    <select id="priority">
                        <option>low</option>
                        <option>medium</option>
                        <option selected>high</option>
                    </select>
                </div>

                <div class="form-field">
                    <label for="due">Due Date</label>
                    <input type="date" id="due" value="2025-12-15">
                </div>

                <div class="form-field">
                    <label>Tags</label>
                    <div class="tag-list">
                        <span class="tag">backend <button>×</button></span>
                        <span class="tag">database <button>×</button></span>
                    </div>
                    <input type="text" placeholder="Add tag..." style="margin-top: 0.5rem;">
                </div>
            </div>

            <div class="metadata-section">
                <h3>🔗 Backlinks</h3>
                <ul class="backlinks-list">
                    <li><a href="#">architecture-design.dj</a></li>
                    <li><a href="#">project-roadmap.dj (2)</a></li>
                    <li><a href="#">meeting-notes-2025-11.dj</a></li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
```

**Risks**:
- Mobile UX complexity (bottom sheet interaction)
- Performance with many form fields
- State management (local vs. server)

---

## MVP Scope (Weeks 2-4)

### Core Features

**1. Basic Frontmatter Support** ✅
- Read YAML frontmatter on file load
- Display in metadata panel
- Edit via simple form
- Write back to file on save

**2. Wikilink Detection** ✅
- Parse `[[wikilinks]]` from content
- Store in `yak_links` table
- Show backlinks in metadata panel

**3. Minimal Metadata Panel** ✅
- Right sidebar on edit page
- Show/edit frontmatter key-value pairs
- Backlinks section
- Collapsible on mobile

**4. One Data Model** ✅
- "Ticket" model with:
  - status (backlog, in-progress, done)
  - priority (low, medium, high)
  - tags (array)
  - due_date (date)

### Non-Goals (Deferred to v2)

❌ Link autocomplete (Phase 3)
❌ Link suggestions (Phase 3)
❌ Multiple data models (Phase 4)
❌ Aggregation views (Phase 5)
❌ Graph visualization (Phase 6)
❌ Fuzzy link resolution (Phase 3)
❌ Schema validation (Phase 4)

---

## MVP Implementation Tasks

### Week 2: Frontmatter Foundation

**Day 1-2: Parser Integration**
```python
# yak_shears/frontmatter.py
from typing import Any
import yaml

def parse_djot(content: str) -> tuple[dict[str, Any], str]:
    """Parse Djot file with optional frontmatter."""
    # Use spike learnings
    pass

def write_djot(frontmatter: dict, body: str) -> str:
    """Write Djot file with frontmatter."""
    pass
```

**Day 3: Database Schema**
```sql
-- Add to existing DB
CREATE TABLE IF NOT EXISTS yak_frontmatter (
    path TEXT PRIMARY KEY,
    frontmatter_json TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS yak_links (
    source_path TEXT,
    target_path TEXT,
    link_type TEXT DEFAULT 'wikilink',
    PRIMARY KEY (source_path, target_path)
);

CREATE INDEX idx_links_target ON yak_links(target_path);
CREATE INDEX idx_links_source ON yak_links(source_path);
```

**Day 4-5: Indexing on Save**
```python
# yak_shears/indexer.py
async def index_yak_file(path: Path, db):
    """Index frontmatter and links from yak file."""
    content = path.read_text()
    frontmatter, body = parse_djot(content)

    # Store frontmatter
    await db.execute(
        "INSERT OR REPLACE INTO yak_frontmatter VALUES (?, ?, ?)",
        [str(path), json.dumps(frontmatter), datetime.now()]
    )

    # Extract and store links
    links = extract_wikilinks(body)
    await db.execute(
        "DELETE FROM yak_links WHERE source_path = ?",
        [str(path)]
    )
    for target, _ in links:
        await db.executemany(
            "INSERT INTO yak_links VALUES (?, ?, ?)",
            [(str(path), target, 'wikilink')]
        )
```

### Week 3: Metadata UI

**Day 1-2: Panel Layout**
```html
<!-- yak_shears/_templates/yak/edit.html.jinja -->
<div class="editor-layout">
    <div class="editor-main">
        <!-- existing editor -->
    </div>

    <aside class="metadata-panel" id="metadata-panel">
        <section class="metadata-section">
            <h3>Properties</h3>
            <form hx-post="/api/yak/{{ yak_path }}/frontmatter"
                  hx-trigger="change">
                {% for key, value in frontmatter.items() %}
                <div class="form-field">
                    <label>{{ key }}</label>
                    <input name="{{ key }}" value="{{ value }}">
                </div>
                {% endfor %}
            </form>
        </section>

        <section class="metadata-section">
            <h3>Backlinks</h3>
            <ul>
                {% for backlink in backlinks %}
                <li><a href="/edit?yak={{ backlink }}">{{ backlink }}</a></li>
                {% endfor %}
            </ul>
        </section>
    </aside>
</div>
```

**Day 3: CSS**
```css
/* yak_shears/static/css/main.css */
.editor-layout {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 0;
    height: calc(100vh - var(--header-height));
}

.metadata-panel {
    background: var(--color-surface);
    border-left: 1px solid var(--color-border);
    padding: var(--space-5);
    overflow-y: auto;
}

@media (max-width: 768px) {
    .editor-layout {
        grid-template-columns: 1fr;
    }
    .metadata-panel {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        max-height: 50vh;
        border-left: none;
        border-top: 1px solid var(--color-border);
        transform: translateY(calc(100% - 3rem));
        transition: transform 0.3s ease;
    }
    .metadata-panel.open {
        transform: translateY(0);
    }
}
```

**Day 4-5: HTMX Integration**
```python
# yak_shears/server/_routes.py

@app.post("/api/yak/{yak_path:path}/frontmatter")
async def update_frontmatter(request: Request, yak_path: str):
    """Update frontmatter for a yak."""
    form = await request.form()

    # Read current file
    file_path = YAK_DIR / yak_path
    content = file_path.read_text()
    _, body = parse_djot(content)

    # Build new frontmatter from form
    new_fm = dict(form)

    # Write back
    new_content = write_djot(new_fm, body)
    file_path.write_text(new_content)

    # Reindex
    await index_yak_file(file_path, db)

    return HTMLResponse("✓ Saved")

@app.get("/api/yak/{yak_path:path}/backlinks")
async def get_backlinks(yak_path: str):
    """Get backlinks for a yak."""
    backlinks = await db.execute(
        "SELECT source_path FROM yak_links WHERE target_path = ?",
        [yak_path]
    ).fetchall()

    return render_template(
        "partials/backlinks.html.jinja",
        backlinks=[b[0] for b in backlinks]
    )
```

### Week 4: Polish & Testing

**Day 1-2: Error Handling**
- Malformed YAML warnings
- Missing file handling
- Concurrent edit detection

**Day 3: E2E Tests**
```python
# tests/e2e/test_metadata.py

async def test_edit_frontmatter(page: Page):
    """Test editing frontmatter via UI."""
    await page.goto("/edit?yak=test.dj")

    # Wait for metadata panel
    await page.wait_for_selector(".metadata-panel")

    # Edit status
    await page.select_option("select[name='status']", "done")

    # Should auto-save via HTMX
    await page.wait_for_selector(".save-indicator")

    # Verify in file
    content = Path("test.dj").read_text()
    assert "status: done" in content

async def test_backlinks_display(page: Page):
    """Test backlinks are shown."""
    await page.goto("/edit?yak=note-a.dj")

    backlinks = await page.locator(".metadata-panel .backlinks-list li").count()
    assert backlinks > 0
```

**Day 4-5: Documentation**
- Update README with frontmatter syntax
- Example yak files with metadata
- User guide for metadata panel

---

## Success Metrics

**Technical**:
- ✅ Parse 1000 files in <100ms
- ✅ Backlinks query in <50ms
- ✅ Metadata panel renders in <100ms
- ✅ Zero data loss on save

**UX**:
- ✅ 1-click to edit metadata
- ✅ Instant backlinks visibility
- ✅ Mobile-friendly panel
- ✅ No page refreshes (HTMX)

**Code Quality**:
- ✅ 80%+ test coverage
- ✅ Type hints throughout
- ✅ No regressions in existing features

---

## MVP Deliverables

1. **Working frontmatter** in Djot files
2. **Metadata panel** showing/editing properties
3. **Backlinks section** with clickable links
4. **Link indexing** on save
5. **Tests** for core functionality
6. **Documentation** for users

---

## Post-MVP: Next Iterations

**v0.2 - Link Intelligence**:
- Autocomplete on `[[`
- Fuzzy link resolution
- Broken link detection

**v0.3 - Data Models**:
- Schema validation
- Multiple built-in models
- Type selector

**v0.4 - Views**:
- Board view for tickets
- Table view
- Calendar view

**v0.5 - Advanced**:
- Graph visualization
- Block references
- Custom models

---

## Questions for You

1. **Spike Priority**: Which spike should we run first?
   - Frontmatter parsing (safest)
   - Link detection (most impactful)
   - DuckDB performance (highest risk)
   - Metadata UI (most visible)

2. **MVP Scope**: Is this too ambitious for 3 weeks?
   - Add more features?
   - Cut anything?
   - Different timeline?

3. **Data Model**: Start with "ticket" or something else?
   - Ticket (status, priority, due)
   - Practice (language, activity, duration)
   - Generic note (tags only)

4. **UI Location**: Right sidebar or different placement?
   - Right sidebar (Obsidian style)
   - Left sidebar
   - Modal/overlay
   - Bottom panel

Ready to start spiking? I can begin with any of the 4 spikes immediately!
