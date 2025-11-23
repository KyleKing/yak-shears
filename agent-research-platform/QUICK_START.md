# Quick Start Guide

Get the Agent Research Platform running in 5 minutes.

## Prerequisites

```bash
# Check you have required tools
python --version  # Should be 3.12+
psql --version    # PostgreSQL client
```

## Installation

### 1. Install Dependencies

```bash
# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Setup PostgreSQL

**Option A: Local PostgreSQL**

```bash
# Install pgvector extension
# Ubuntu/Debian:
sudo apt install postgresql-16-pgvector

# macOS:
brew install pgvector

# Create database
createdb research_platform
```

**Option B: Docker PostgreSQL**

```bash
docker run -d \
  --name research-platform-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=research_platform \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Wait for it to start
sleep 5
```

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env and set:
# - DATABASE_URL (if not using defaults)
# - OPENAI_API_KEY (required for embeddings)

# Minimal .env:
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/research_platform
OPENAI_API_KEY=sk-your-key-here
EOF
```

### 4. Initialize Database

```bash
# Create database, enable pgvector, run migrations
python scripts/setup_db.py
```

Expected output:
```
=== Database Setup ===

✓ Database research_platform created
✓ pgvector extension enabled
Running database migrations
✓ Migrations completed

✓ Database setup complete!
```

### 5. Seed Demo Data

```bash
# Generate B2B demo data with embeddings
python scripts/seed_data.py
```

This creates:
- 2 organizations (Acme Corp, TechStart Inc)
- ~10 users per org
- ~40 products with vector embeddings
- ~30 customers
- ~50 orders
- ~20 support tickets with embeddings
- ~20 documents with embeddings

Takes ~1-2 minutes (embedding generation).

## Verify Setup

### Check Database

```bash
# Connect to database
psql research_platform

# Check tables
\dt

# Check organizations
SELECT id, name, tier FROM organizations;

# Check products with embeddings
SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL;

# Should see all products have embeddings
```

### Python REPL

```python
import asyncio
from research_platform.db.session import get_session
from research_platform.db.models import Organization, Product
from research_platform.db.embeddings import EmbeddingService

async def test():
    async with get_session() as session:
        # Check organization
        result = await session.execute(select(Organization))
        org = result.scalars().first()
        print(f"Organization: {org.name}")

        # Test semantic search
        embeddings = EmbeddingService()
        products = await embeddings.search_products(
            session,
            "enterprise software",
            organization_id=org.id,
            limit=3
        )
        print(f"Found {len(products)} products:")
        for p in products:
            print(f"  - {p.name}")

asyncio.run(test())
```

## Next Steps

### Explore the Data

```bash
# PostgreSQL
psql research_platform

# Useful queries:
SELECT o.name, COUNT(c.id) as customer_count
FROM organizations o
LEFT JOIN customers c ON c.organization_id = o.id
GROUP BY o.id, o.name;

SELECT c.company_name, COUNT(o.id) as order_count, SUM(o.total_amount) as revenue
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.company_name
ORDER BY revenue DESC NULLS LAST
LIMIT 10;

# Vector search
SELECT name, description
FROM products
WHERE embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM products LIMIT 1)
LIMIT 5;
```

### Claude Skills

Use the Claude Skills for working with PydanticAI:

```
.claude/skills/pydantic-ai.md     - Complete agent development guide
.claude/skills/pydantic-evals.md  - Evaluation framework guide
```

In Claude Code, these skills provide context-aware help for:
- Building agents with tool calling
- Implementing dependency injection
- Creating evaluation datasets
- Testing with VCR caching

### Read the Docs

- `README.md` - Overview and quick reference
- `ARCHITECTURE.md` - Detailed system architecture
- `docs/RESEARCH_SUMMARY.md` - Complete research findings

## Common Issues

### "pgvector extension not found"

```bash
# Install pgvector
# See: https://github.com/pgvector/pgvector#installation

# Then re-run setup
python scripts/setup_db.py
```

### "OpenAI API key not set"

```bash
# Add to .env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Or export temporarily
export OPENAI_API_KEY=sk-your-key-here
```

### "Database connection failed"

```bash
# Check PostgreSQL is running
pg_isready

# Check connection string in .env
cat .env | grep DATABASE_URL

# Test connection
psql postgresql://postgres:postgres@localhost:5432/research_platform
```

### "Seed data fails with embedding errors"

```bash
# Check API key
echo $OPENAI_API_KEY

# Try with fewer items first (edit scripts/seed_data.py)
# Reduce counts in seed_organizations(count=1)

# Or use a different embedding model
# Edit .env:
EMBEDDING_MODEL=openai:text-embedding-3-small
```

## Development Workflow

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests (when implemented)
pytest

# Database migrations
alembic revision -m "Add new feature"
alembic upgrade head

# Reset database
dropdb research_platform
python scripts/setup_db.py
python scripts/seed_data.py

# Interactive Python
python
>>> from research_platform.db import models
>>> # Explore models
```

## What's Next?

The platform is ready for agent implementation. Follow the architecture in `ARCHITECTURE.md` to build:

1. **SQL Agent** - Natural language to SQL with validation
2. **RAG Agent** - Semantic search + generation
3. **Analysis Agent** - Multi-step reasoning
4. **Support Agent** - Ticket automation

All the infrastructure is in place:
- ✅ Database with multi-tenant data
- ✅ Vector search with pgvector
- ✅ Embedding service
- ✅ Configuration management
- ✅ Migration system
- ✅ Seed data

Ready to implement the agents using patterns from `.claude/skills/pydantic-ai.md`!

## Help

For issues:
1. Check error messages carefully
2. Verify prerequisites (Python version, PostgreSQL, pgvector)
3. Check `.env` configuration
4. Review `ARCHITECTURE.md` for design details
5. See research in `docs/RESEARCH_SUMMARY.md`

For questions about PydanticAI patterns:
- Read `.claude/skills/pydantic-ai.md`
- Check official docs: https://ai.pydantic.dev/

Happy researching! 🚀
