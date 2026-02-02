# PR #4 Review: Research Tool Calling with pydantic-ai

**Reviewer**: Claude Code
**Date**: 2026-01-24
**Status**: Changes Requested

## Summary

This PR adds a comprehensive research platform for agentic LLM development with PydanticAI, Pydantic Evals, and PostgreSQL/pgvector. The research documentation and architecture are thorough, but several implementation issues should be addressed before merge.

---

## Required Changes

### 1. Fix Session Handling in Seed Script

**File**: `agent-research-platform/scripts/seed_data.py:48-52`

**Problem**: Only the first organization is refreshed, leaving other orgs without IDs for foreign key references.

**Fix**:
```python
async with get_session() as session:
    session.add_all(orgs)
    await session.commit()
    for org in orgs:
        await session.refresh(org)
```

### 2. Fix Database URL Parsing

**File**: `agent-research-platform/scripts/setup_db.py:26-36`

**Problem**: Manual string splitting breaks on passwords containing `@` or `:`.

**Fix**:
```python
from sqlalchemy import make_url

def parse_database_url(database_url: str):
    url = make_url(database_url.replace("+asyncpg", ""))
    return {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port or 5432,
        "database": url.database,
    }
```

### 3. Fix Type Annotation

**File**: `agent-research-platform/src/research_platform/agents/tools/medical.py:463`

**Problem**: `datetime.date` is not a valid type annotation.

**Fix**:
```python
from datetime import date

def _calculate_age(date_of_birth: date) -> int:
```

### 4. Add Initial Alembic Migration

**Problem**: `migrations/versions/` directory is empty. `alembic upgrade head` will fail.

**Fix**: Generate initial migration:
```bash
cd agent-research-platform
alembic revision --autogenerate -m "initial_schema"
```

### 5. Fix README Encoding Issue

**File**: `agent-research-platform/README.md:128`

**Problem**: `=�` appears instead of proper emoji.

**Fix**: Replace with plain text or proper Unicode:
```markdown
**Ready to Implement** (following architecture):
```

---

## Recommended Changes

### 6. Add Error Handling to Embedding Service

**File**: `agent-research-platform/src/research_platform/db/embeddings.py:51-54`

**Suggestion**: Add retry logic and error handling for API calls:
```python
async def embed(self, text: str) -> list[float]:
    if not text.strip():
        raise ValueError("Cannot embed empty text")

    try:
        client = self._get_client()
        model_name = self.model.split(":")[-1]
        response = await client.embeddings.create(input=text, model=model_name)
        return response.data[0].embedding
    except Exception as err:
        raise RuntimeError(f"Embedding generation failed: {err}") from err
```

### 7. Fix JSONB Author Query

**File**: `agent-research-platform/src/research_platform/agents/tools/research.py:211`

**Problem**: Query assumes `authors` is a flat JSON array, but schema suggests `{"authors": [...]}`.

**Suggestion**: Either:
- Document the expected schema clearly, or
- Fix the query:
```python
.where(Publication.authors["authors"].contains([author_name]))
```

### 8. Add Basic Tests

**Problem**: No test files included in PR despite comprehensive test documentation.

**Suggestion**: Add at minimum:
- `tests/test_db/test_models.py` - Model instantiation
- `tests/test_db/test_embeddings.py` - Embedding service (mocked)
- `tests/conftest.py` - Shared fixtures

---

## Observations

### Strengths

- Comprehensive research documentation on PydanticAI vs alternatives
- Production-ready patterns: multi-tenant isolation, HIPAA audit logging, type safety
- Reusable Claude Skills in `.claude/skills/`
- Proper use of `RunContext[DepsType]` for dependency injection
- pgvector HNSW indexes for semantic search performance

### Security

- Multi-tenant isolation enforced via `organization_id`/`institution_id` in all queries
- PHI de-identified where possible (age vs DOB)
- Audit logging for medical data access
- API keys properly excluded via `.gitignore`

### Scope Concern

This PR is ~10,000 lines across many concerns. Consider splitting for future maintainability:
1. Research docs + Claude Skills
2. Database models + migrations
3. Agent implementations + tools

---

## Checklist Before Merge

- [ ] Fix session handling in seed script
- [ ] Use `sqlalchemy.make_url()` for URL parsing
- [ ] Fix `datetime.date` type annotation
- [ ] Generate initial Alembic migration
- [ ] Fix README encoding issue
- [ ] Add error handling to embedding service
- [ ] Verify JSONB query matches schema
- [ ] Add basic test coverage

---

## Files Changed

| Category | Files | Lines |
|----------|-------|-------|
| Claude Skills | 2 | ~1,100 |
| Documentation | 6 | ~2,500 |
| Database Models | 3 | ~800 |
| Agent Tools | 4 | ~1,200 |
| Scripts | 2 | ~500 |
| Config | 5 | ~300 |
| Other | 10+ | ~3,500 |

**Total**: ~9,989 additions, 21 deletions
