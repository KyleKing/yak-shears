# Agent Research Platform

> **Note**: This is a standalone pydantic-ai research sub-project, unrelated to the Yak Shears runtime. It originated on the `claude/research-pydantic-ai-tools` branch (PR #4; outstanding review items in [PR4_REVIEW.md](./PR4_REVIEW.md)). Long-term it may inform an agent/semantic-search CLI used by yak-shears, at which point it moves to its own repo. Its architecture doc is [ARCHITECTURE.md](./ARCHITECTURE.md).

A comprehensive research platform for building, testing, and evaluating agentic LLM applications with PostgreSQL/pgvector for B2B use cases.

## Overview

This platform demonstrates production-ready patterns for:

- **Type-safe agent development** with PydanticAI
- **Multi-tenant B2B data modeling** with PostgreSQL + pgvector
- **Semantic search** for products, documents, and support tickets
- **Comprehensive evaluation framework** with Pydantic Evals
- **Cost and quality monitoring** across experiments
- **Pipeline versioning** for comparing models, prompts, and approaches
- **VCR-style caching** for deterministic, fast tests

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ with pgvector extension
- OpenAI API key (or other LLM provider)

### Installation

```bash
# Install dependencies with uv
uv sync

# Copy environment file
cp .env.example .env
# Edit .env and add your API keys
```

### Database Setup

```bash
# Setup database and run migrations
python scripts/setup_db.py

# Seed with demo B2B data
python scripts/seed_data.py
```

## Architecture

See [ARCHITECTURE.md](../ARCHITECTURE.md) for complete architecture documentation.

**Key Components:**
- PostgreSQL + pgvector for multi-tenant B2B data
- PydanticAI agents with tool calling
- Pydantic Evals for systematic testing
- Logfire for observability
- pytest-recording for LLM response caching
- Experiment tracking and versioning

## Research Summary

This platform was created after thorough research of pydantic-ai, pydantic-evals, and related tooling. Key findings:

### PydanticAI vs Alternatives

**PydanticAI**: Best for production applications
- Type-safe, minimal abstractions
- Built-in observability (Logfire)
- FastAPI-style developer experience

**Instructor**: Best for structured extraction only
- No agent capabilities
- Focused on data extraction

**LangChain**: Best for demos and prototyping
- Feature-rich but complex
- Many deprecated patterns

### Evaluation Best Practices

- **Code-first**: Define evaluations in Python
- **VCR caching**: Use pytest-recording for deterministic tests
- **Versioning**: Track prompts, datasets, models, evaluators
- **Cost awareness**: Budget constraints as first-class evaluators

### Tool Calling Patterns

- Use `RunContext[DepsType]` for dependency injection
- Comprehensive docstrings (LLM reads them)
- Type hints + Pydantic Field for better schemas
- Validation with `@agent.result_validator`

## Claude Skills Created

This research produced two Claude Skills in `.claude/skills/`:

1. **pydantic-ai.md**: Complete guide to PydanticAI
   - Agent definition and execution
   - Dependency injection with RunContext
   - Tool calling patterns
   - Observability with Logfire
   - SQL generation patterns
   - Best practices and comparisons

2. **pydantic-evals.md**: Evaluation framework guide
   - Dataset and case management
   - Built-in and custom evaluators
   - pytest integration
   - VCR caching for LLMs
   - Versioning and regression testing
   - A/B testing patterns

Use these skills when working with PydanticAI or building evaluation frameworks.

## Project Status

This is a **research platform** demonstrating:

 **Completed:**
- Comprehensive research (official docs, GitHub, HackerNews, blogs)
- Architecture design for B2B agent platform
- Database models with pgvector support
- Configuration and session management
- Embedding service with semantic search
- Database setup scripts
- Seed data generation
- Claude Skills for pydantic-ai and pydantic-evals
- Complete documentation

=� **Ready to Implement** (following architecture):
- Agent implementations (SQL, RAG, Analysis, Support)
- Tool catalog (database tools, search tools, analysis tools)
- Evaluation framework with custom evaluators
- Experiment tracking and comparison system
- Cost/quality metrics collection
- Test suite with pytest-recording
- CLI for running experiments

## Key Innovation

**Multi-Tenant Aware Agents**: All tools enforce row-level security by requiring `organization_id` in dependencies, preventing data leakage between tenants.

```python
@dataclass
class B2BDeps:
    db: AsyncEngine
    embeddings: EmbeddingService
    organization_id: int  # Tenant context enforced

@agent.tool
async def search_products(
    ctx: RunContext[B2BDeps],
    query: str
) -> list[Product]:
    # Automatic tenant filtering
    return await ctx.deps.embeddings.search_products(
        session,
        query,
        organization_id=ctx.deps.organization_id  #  Enforced
    )
```

## Resources

### Research Sources

All research documented in `/ARCHITECTURE.md` and Claude Skills, including:

**Official Documentation:**
- [Pydantic AI](https://ai.pydantic.dev/)
- [Pydantic Evals](https://ai.pydantic.dev/evals/)
- [SQL Generation Example](https://ai.pydantic.dev/examples/sql-gen/)
- [Logfire](https://logfire.pydantic.dev/)

**Community Resources:**
- [PydanticAI GitHub](https://github.com/pydantic/pydantic-ai)
- HackerNews discussions and reviews
- Real-world usage examples from 2024-2025
- Blog posts on production usage

**Comparison Analysis:**
- PydanticAI vs LangChain vs Instructor
- Tool calling patterns across frameworks
- Cost tracking approaches (litellm, OpenTelemetry)
- Evaluation frameworks (pydantic-evals, alternatives)

### Database & Vectors

- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [SQLAlchemy with pgvector](https://github.com/pgvector/pgvector-python)
- RAG patterns with PostgreSQL

### Testing & Evaluation

- [pytest-recording](https://pypi.org/project/pytest-recording/)
- [VCR.py](https://vcrpy.readthedocs.io/)
- LLM testing patterns

## Next Steps

To complete implementation:

1. **Implement Agents**: Create SQL, RAG, and Analysis agents following patterns in `.claude/skills/pydantic-ai.md`

2. **Build Evaluation Framework**: Implement custom evaluators using patterns in `.claude/skills/pydantic-evals.md`

3. **Add Experiment Tracking**: Implement versioning and comparison system per architecture

4. **Create Test Suite**: Write comprehensive tests with pytest-recording

5. **Add CLI**: Build command-line interface for running experiments

6. **Deploy**: Add Docker configuration for easy deployment

## License

MIT

---

**Built with thorough research of modern agentic AI patterns**

For detailed research findings, see:
- `.claude/skills/pydantic-ai.md` - Complete PydanticAI guide
- `.claude/skills/pydantic-evals.md` - Evaluation framework guide
- `ARCHITECTURE.md` - Detailed system architecture
