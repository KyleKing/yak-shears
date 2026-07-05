# Djot Search: Progressive Implementation Plan

Local hybrid search for djot files with Python webserver integration.

## Context

- **Scope:** Few hundred short djot files in subdirectories
- **Deployment:** Small server, offline LLMs/embeddings
- **Integration:** Python webserver with 15-minute incremental ingestion
- **Goal:** qmd-like hybrid search (BM25 + vectors) without external APIs

---

## Phase 1: BM25 Full-Text Search

**Goal:** Fast keyword search with zero ML dependencies.

**Components:**
- SQLite database with FTS5 virtual table
- File watcher tracking mtime for incremental updates
- Simple HTTP endpoint returning ranked results

**Schema:**
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    mtime REAL NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
    title, content,
    content='documents',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;
-- (similar for UPDATE, DELETE)
```

**Indexing logic:**
```python
def index_directory(root: Path, db: Connection) -> IndexStats:
    """Scan directory, index new/modified files, remove deleted."""
    current_files = {p: p.stat().st_mtime for p in root.rglob("*.djot")}
    indexed = {row["path"]: row for row in db.execute("SELECT * FROM documents")}

    # Detect changes
    to_add = [p for p in current_files if p not in indexed]
    to_update = [p for p, mtime in current_files.items()
                 if p in indexed and mtime > indexed[p]["mtime"]]
    to_delete = [p for p in indexed if p not in current_files]

    # Apply changes...
```

**Search endpoint:**
```python
@app.get("/search")
def search(q: str, n: int = 10) -> list[SearchResult]:
    rows = db.execute("""
        SELECT path, title, snippet(documents_fts, 1, '<b>', '</b>', '...', 32) as snippet,
               bm25(documents_fts) as score
        FROM documents_fts
        WHERE documents_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """, (q, n))
    return [SearchResult(**row) for row in rows]
```

**Dependencies:** `sqlite3` (stdlib only)

**Effort:** ~150 lines | **Quality:** ~60% of qmd

---

## Phase 2: Vector Semantic Search

**Goal:** Find conceptually similar documents even without keyword matches.

**New components:**
- sqlite-vec extension for vector storage
- Small embedding model via sentence-transformers
- Hybrid RRF fusion of BM25 + vector results

**Model choice for small server:**
| Model | Size | Dim | Notes |
|-------|------|-----|-------|
| all-MiniLM-L6-v2 | 80MB | 384 | Good baseline, CPU-friendly |
| bge-small-en-v1.5 | 130MB | 384 | Better quality |
| nomic-embed-text-v1.5 | 550MB | 768 | Best quality, needs more RAM |

Recommend: `all-MiniLM-L6-v2` for small server (runs well on 2GB RAM).

**Schema additions:**
```sql
CREATE VIRTUAL TABLE vectors USING vec0(
    document_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Embedding on index:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_document(doc: Document) -> list[float]:
    text = f"{doc.title}\n\n{doc.content}"
    return model.encode(text, normalize_embeddings=True).tolist()
```

**Vector search:**
```python
def vsearch(query: str, k: int = 10) -> list[tuple[int, float]]:
    query_vec = model.encode(query, normalize_embeddings=True)
    return db.execute("""
        SELECT document_id, distance
        FROM vectors
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
    """, (query_vec.tobytes(), k)).fetchall()
```

**RRF fusion:**
```python
def rrf_fusion(
    bm25_results: list[tuple[str, float]],
    vec_results: list[tuple[str, float]],
    k: int = 60
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion with k=60."""
    scores: dict[str, float] = defaultdict(float)

    for rank, (doc_id, _) in enumerate(bm25_results):
        scores[doc_id] += 1.0 / (k + rank + 1)

    for rank, (doc_id, _) in enumerate(vec_results):
        scores[doc_id] += 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: -x[1])
```

**Dependencies:** `sqlite-vec`, `sentence-transformers`, `torch` (CPU)

**Effort:** +200 lines | **Quality:** ~80% of qmd

---

## Phase 3: Incremental Ingestion Service

**Goal:** Background task syncs index every 15 minutes.

**Architecture:**
```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Djot Files     │────▶│  Ingestion   │────▶│   SQLite    │
│  (filesystem)   │     │  Worker      │     │   (FTS+vec) │
└─────────────────┘     └──────────────┘     └─────────────┘
                              │
                              ▼
                        ┌──────────────┐
                        │  Webserver   │◀──── Search queries
                        └──────────────┘
```

**Implementation options:**

*Option A: APScheduler (simple)*
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(index_directory, "interval", minutes=15, args=[root, db])
scheduler.start()
```

*Option B: Dedicated worker (robust)*
```python
# ingestion_worker.py
import time
from pathlib import Path

def run_worker(root: Path, db_path: Path, interval: int = 900):
    while True:
        with connect(db_path) as db:
            stats = index_directory(root, db)
            logger.info(f"Indexed: +{stats.added}, ~{stats.updated}, -{stats.deleted}")
        time.sleep(interval)
```

**Locking for concurrent access:**
```python
# Use WAL mode for concurrent reads during writes
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=5000")
```

**Change detection optimization:**
```python
# Store directory state hash to skip unchanged dirs
def dir_hash(path: Path) -> str:
    entries = sorted(f"{p.name}:{p.stat().st_mtime}" for p in path.iterdir())
    return hashlib.md5("".join(entries).encode()).hexdigest()
```

**Effort:** +100 lines | **Quality:** Production-ready sync

---

## Phase 4: Smart Chunking (Optional)

**Goal:** Handle longer documents by chunking for better embedding relevance.

Only needed if documents exceed ~1500 tokens. For short files, skip this phase.

**Strategy:**
- Target: 512 tokens per chunk (matches model context)
- Overlap: 64 tokens (12.5%)
- Break at: paragraph > sentence > line

```python
def chunk_document(content: str, max_tokens: int = 512, overlap: int = 64) -> list[str]:
    paragraphs = content.split("\n\n")
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para.split())  # Approximate token count
        if current_len + para_len > max_tokens and current:
            chunks.append("\n\n".join(current))
            # Keep overlap from end
            overlap_text = current[-1] if current else ""
            current = [overlap_text] if overlap_text else []
            current_len = len(overlap_text.split())
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks
```

**Schema change:**
```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    seq INTEGER NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(document_id, seq)
);

CREATE VIRTUAL TABLE chunk_vectors USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Effort:** +150 lines | **Quality:** ~85% of qmd

---

## Phase 5: Query Expansion (Optional)

**Goal:** Improve recall by generating query variations.

For small server, use a tiny local LLM or skip entirely. The cost/benefit is marginal for a few hundred documents.

**Lightweight option: Synonym expansion**
```python
# Use WordNet instead of LLM
from nltk.corpus import wordnet

def expand_query(query: str) -> list[str]:
    words = query.lower().split()
    expansions = [query]
    for word in words:
        synsets = wordnet.synsets(word)
        if synsets:
            synonyms = {l.name() for s in synsets[:2] for l in s.lemmas()[:3]}
            for syn in list(synonyms)[:2]:
                if syn != word:
                    expansions.append(query.replace(word, syn.replace("_", " ")))
    return expansions[:3]
```

**LLM option (if resources allow):**
```python
# Use llama-cpp-python with a tiny model
from llama_cpp import Llama

llm = Llama(model_path="qwen2.5-0.5b-instruct-q4_k_m.gguf", n_ctx=512)

def expand_with_llm(query: str) -> list[str]:
    prompt = f"Rewrite this search query 2 different ways:\n{query}\n\n1."
    response = llm(prompt, max_tokens=100, stop=["\n\n"])
    # Parse response...
```

**Effort:** +100 lines | **Quality:** ~90% of qmd (diminishing returns)

---

## Recommended Implementation Order

| Phase | Time | RAM | Dependencies |
|-------|------|-----|--------------|
| 1. BM25 | Day 1 | <100MB | stdlib |
| 2. Vectors | Day 2-3 | ~500MB | sqlite-vec, sentence-transformers |
| 3. Ingestion | Day 3-4 | - | apscheduler (optional) |
| 4. Chunking | If needed | - | - |
| 5. Expansion | If needed | +1GB | llama-cpp-python |

**Stop at Phase 3** for most use cases. Phases 4-5 add complexity with marginal gains for small document sets.

---

## Project Structure

```
djot_search/
├── __init__.py
├── db.py           # Schema, migrations, connection handling
├── index.py        # File scanning, document parsing, embedding
├── search.py       # BM25, vector, hybrid search functions
├── worker.py       # Background ingestion service
├── api.py          # FastAPI/Flask endpoints
└── models.py       # Pydantic models for API
```

---

## API Design

```python
# Endpoints
GET  /search?q=<query>&n=10&mode=hybrid  # Search documents
GET  /document/<path:path>                # Get full document
GET  /status                              # Index stats, last sync time

# Response model
class SearchResult(BaseModel):
    path: str
    title: str | None
    snippet: str
    score: float

class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    mode: Literal["bm25", "vector", "hybrid"]
    took_ms: int
```

---

## Resource Estimates (Small Server)

**Baseline (Phase 1-3):**
- CPU: Any (FTS5 is fast)
- RAM: ~500MB (model loaded)
- Disk: ~50MB index for 500 docs
- Latency: 10-50ms per search

**With embeddings:**
- Initial indexing: ~2 docs/sec on CPU
- Incremental: <1 sec for changed files
- Search: +20-50ms for vector component

---

## Key Simplifications vs QMD

1. **No re-ranking** - RRF alone is sufficient for small collections
2. **No query expansion** - Keywords + vectors cover most cases
3. **Single embedding per doc** - Skip chunking for short files
4. **No docid system** - Use file paths directly
5. **No collection management** - Single root directory
6. **Simpler fusion** - Equal weight RRF without position bonuses
