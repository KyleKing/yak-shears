# Research Summary: PydanticAI, Evals, and Agentic Patterns

This document summarizes comprehensive research conducted on pydantic-ai, pydantic-evals, tool calling patterns, and related frameworks.

## Research Sources

### Official Documentation
- **Pydantic AI**: https://ai.pydantic.dev/
- **Pydantic Evals**: https://ai.pydantic.dev/evals/
- **SQL Generation Example**: https://ai.pydantic.dev/examples/sql-gen/
- **Tool Calling**: https://ai.pydantic.dev/tools/
- **Dependencies**: https://ai.pydantic.dev/dependencies/
- **Logfire**: https://logfire.pydantic.dev/

### GitHub & Community
- **Official Repo**: https://github.com/pydantic/pydantic-ai
- **Community Examples**: https://github.com/cloutprotocol/pydantic-ai
- **Temporal Integration**: https://github.com/pydantic/pydantic-ai-temporal-example
- **Real-world Examples**: GitHub Actions automation, DeepSeek integration

### HackerNews Discussions
Multiple active discussions found:
- "Agent Framework / shim to use Pydantic with LLMs" (Dec 2024)
- "PydanticAI: Model-Agnostic, Production-Ready Agent Framework for LLM"
- "Building Effective Agents with Pydantic AI"
- "Pydantic AI reaches V1"

**Key Community Feedback:**
- Positive: "Validation and dependency injection are great additions"
- Positive: "Neither tool 'gets in the way' of what you're trying to do"
- Mixed: Some prefer minimal abstractions over frameworks
- Critical: Debate about framework complexity vs. simple control flow

### Blog Posts & Tutorials (2024-2025)
- Building CLI coding agents with PydanticAI
- EV Charging Growth CLI (production example)
- GitHub integration agents with DeepSeek V3
- Slack bot with Temporal workflows

## Key Findings

### 1. PydanticAI: Production-Ready Agent Framework

**Philosophy**: Schema-first, type-safe approach with Python's native syntax

**Core Strengths:**
- Type safety throughout (inputs, tools, outputs)
- Dependency injection via `RunContext[DepsType]`
- Built-in observability with Logfire/OpenTelemetry
- Multi-model support (15+ providers)
- Minimal abstractions - clear control flow

**Best Use Cases:**
- Production applications (not just demos)
- Teams that value type safety and IDE support
- Projects using Pydantic/FastAPI ecosystem
- Applications requiring observability

**When to Consider Alternatives:**
- Pure extraction tasks → Use Instructor
- Quick demos/prototypes → LangChain might be faster
- Specialized RAG features → LlamaIndex

### 2. Pydantic Evals: Code-First Evaluation

**Philosophy**: All evaluation components defined in Python, no web UI configuration

**Core Components:**
- **Dataset**: Collection of test cases
- **Case**: Single scenario with inputs, expected outputs, metadata
- **Evaluators**: Built-in and custom validation logic
- **Reports**: Aggregated results with metrics

**Built-in Evaluators:**
- Exact match
- Semantic similarity
- LLM as judge
- Custom domain-specific

**Key Features:**
- Span-based evaluation (internal agent behavior via OpenTelemetry)
- Logfire integration (visual debugging)
- pytest integration (CI/CD friendly)
- Independent of PydanticAI (works with any framework)

### 3. Framework Comparison

#### PydanticAI vs LangChain

**PydanticAI:**
- ✅ Simpler, cleaner API
- ✅ Type-safe with excellent IDE support
- ✅ Production-focused
- ✅ Minimal legacy code
- ❌ Less mature ecosystem
- ❌ Fewer pre-built components

**LangChain:**
- ✅ Rich feature set
- ✅ Large ecosystem
- ✅ Good for rapid prototyping
- ❌ Complex, many deprecated patterns
- ❌ "Bloat" for production use
- ❌ Steeper learning curve

**Verdict**: "LangChain for demos, PydanticAI for products"

#### PydanticAI vs Instructor

**PydanticAI:**
- Full agent framework
- Tool calling, validation, retries
- Observability built-in
- For agentic applications

**Instructor:**
- Structured extraction only
- Fast, schema-first
- 3M+ monthly downloads
- For data extraction tasks

**Verdict**: "Instructor for extraction, PydanticAI for agents"

### 4. Tool Calling Best Practices

Based on official examples and community patterns:

**1. Comprehensive Docstrings**
```python
@agent.tool
def search_database(query: str, limit: int = 10) -> list[dict]:
    """Search the database for relevant records.

    Use this when you need to find records matching specific criteria.
    The search is fuzzy and returns approximate matches.

    Args:
        query: Natural language search query
        limit: Maximum number of results (1-100)

    Returns:
        List of matching records with all fields
    """
```

**2. Dependency Injection**
```python
@agent.tool
async def query_db(
    ctx: RunContext[Deps],
    sql: str
) -> list[dict]:
    # Access dependencies via ctx.deps
    return await ctx.deps.db.execute(sql)
```

**3. Type Hints + Pydantic**
```python
from typing import Annotated
from pydantic import Field

@agent.tool
def search(
    query: Annotated[str, Field(description='Search query')],
    max_results: Annotated[int, Field(ge=1, le=100)] = 10
) -> list[dict]:
    pass
```

**4. Validation**
```python
@agent.result_validator
async def validate_sql(
    ctx: RunContext[Deps],
    result: str
) -> str:
    # Validate SQL
    try:
        await ctx.deps.db.execute(f'EXPLAIN {result}')
        return result
    except Exception as e:
        # Ask LLM to fix
        raise ModelRetry(f'Invalid SQL: {e}')
```

### 5. SQL Agent Pattern

From official example (https://ai.pydantic.dev/examples/sql-gen/):

**Key Insights:**
- Use Gemini 2.5 Flash (good at single-shot SQL)
- Return `Union[Success, InvalidRequest]` for error handling
- Validate with `EXPLAIN` query
- Self-healing with `ModelRetry`
- Include schema in system prompt

**Pattern:**
```python
class Success(BaseModel):
    sql: str
    explanation: str

class InvalidRequest(BaseModel):
    error_message: str

sql_agent = Agent(
    'gemini-2.5-flash',
    result_type=Union[Success, InvalidRequest],
)

@sql_agent.result_validator
async def validate_sql(ctx, result):
    if isinstance(result, InvalidRequest):
        return result
    # Validate with EXPLAIN...
```

### 6. Testing & Caching Patterns

**pytest-vcr / pytest-recording:**

Benefits for LLM testing:
- Deterministic outputs
- Fast execution (no API calls)
- No secrets in CI
- Cost savings

**Pattern:**
```python
@pytest.fixture(scope='module')
def vcr_config():
    return {'filter_headers': ['authorization']}

@pytest.mark.vcr()
async def test_agent():
    # First run: records to cassette
    # Subsequent runs: replays from cassette
    result = await agent.run('test query')
    assert result.valid
```

**Record Modes:**
- `once`: Record if cassette missing
- `rewrite`: Always re-record
- `new_episodes`: Append new interactions
- `none`: Fail if cassette missing (CI mode)

### 7. Cost Tracking

**Multiple Approaches:**

1. **OpenTelemetry** (Logfire, Langfuse)
   - Automatic span tracking
   - Token counts from model responses
   - Cost calculated from pricing tables

2. **litellm**
   - Unified API across 100+ models
   - Automatic cost tracking
   - Budget limits and alerting

3. **Custom Tracking**
   - Parse token counts from responses
   - Maintain pricing table
   - Store in database

**Best Practice**: Use OpenTelemetry/Logfire for automatic tracking

### 8. pgvector + SQLAlchemy

**Integration Pattern:**
```python
from pgvector.sqlalchemy import Vector

class Product(Base):
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))

    __table_args__ = (
        Index(
            'idx_product_embedding',
            'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
        ),
    )
```

**Search Pattern:**
```python
stmt = (
    select(Product)
    .filter(Product.organization_id == org_id)
    .order_by(Product.embedding.cosine_distance(query_embedding))
    .limit(10)
)
```

**Index Types:**
- **HNSW**: Fast approximate search (recommended)
- **IVFFlat**: Good for smaller datasets
- Parameters: `m` (connections), `ef_construction` (build quality)

### 9. Observability with Logfire

**Key Features:**
- Built on OpenTelemetry
- Native PydanticAI integration
- Complete traces (tools, retries, validation)
- Token usage and cost tracking
- Visual debugging

**Setup:**
```python
import logfire

logfire.configure()
logfire.instrument_pydantic_ai()

# All runs automatically traced
```

**What's Traced:**
- Agent execution start/end
- System prompt evaluation
- Tool calls with arguments and results
- Validation attempts
- Retries and errors
- Token counts and costs

### 10. Multi-Tenant Patterns

**Row-Level Security via Dependencies:**
```python
@dataclass
class TenantDeps:
    db: AsyncEngine
    organization_id: int

@agent.tool
async def get_data(ctx: RunContext[TenantDeps]) -> list[Data]:
    # Automatic tenant filtering
    return await db.query(
        Data,
        organization_id=ctx.deps.organization_id
    )
```

**Benefits:**
- Type-safe tenant isolation
- No global state
- Easy testing (inject different org_id)
- Audit trail (track which org made request)

## Recommendations

### For Production Applications

1. **Use PydanticAI**
   - Type safety prevents bugs
   - Observability is critical
   - Minimal abstractions = maintainable

2. **Implement Comprehensive Evaluations**
   - Use Pydantic Evals
   - VCR caching for deterministic tests
   - Track metrics over time

3. **Version Everything**
   - Prompts (git or database)
   - Datasets (JSON files)
   - Models (track in experiments)
   - Code (git commit hash)

4. **Cost Awareness**
   - Budget constraints as evaluators
   - Monitor token usage
   - Optimize expensive queries

5. **Multi-Tenancy First**
   - Use dependency injection
   - Never use global state
   - Enforce RLS in tools

### For Research Platforms

1. **Experiment Tracking**
   - Store all runs in database
   - Easy comparison between runs
   - Regression detection

2. **A/B Testing Infrastructure**
   - Same dataset, different approaches
   - Statistical significance
   - Cost/quality trade-offs

3. **Pipeline Versioning**
   - Re-run experiments with new models
   - Compare prompt variants
   - Dataset evolution tracking

4. **Observability**
   - Logfire for debugging
   - Export to other tools (OpenTelemetry)
   - Anonymous metrics for trends

## Common Pitfalls

1. **❌ Not Using Type Hints**
   - Makes debugging harder
   - LLM gets worse tool schema
   - No IDE support

2. **❌ Skipping Evaluations**
   - Can't detect regressions
   - No baseline for improvements
   - Hard to compare approaches

3. **❌ Global State**
   - Testing becomes difficult
   - Multi-tenancy risks
   - Concurrency issues

4. **❌ Ignoring Costs**
   - Development can get expensive
   - Production costs scale unexpectedly
   - No optimization targets

5. **❌ Not Versioning Prompts**
   - Can't reproduce results
   - Hard to track improvements
   - Debugging failures is difficult

## Future Research Areas

1. **Advanced RAG Patterns**
   - Hybrid search (keyword + vector)
   - Re-ranking strategies
   - Context window management

2. **Multi-Agent Systems**
   - Agent coordination
   - Shared state management
   - Error recovery patterns

3. **Evaluation Methodologies**
   - Human-in-the-loop feedback
   - Automated quality metrics
   - Long-term performance tracking

4. **Cost Optimization**
   - Model selection strategies
   - Caching and deduplication
   - Prompt compression

5. **Security & Privacy**
   - PII detection and redaction
   - Prompt injection prevention
   - Audit logging

## Conclusion

PydanticAI and Pydantic Evals provide a solid foundation for building production-ready agentic applications. Key differentiators:

- **Type Safety**: Catch bugs at development time
- **Observability**: Built-in, not bolted-on
- **Simplicity**: Minimal abstractions, clear control flow
- **Testing**: First-class evaluation framework

For B2B applications with multi-tenancy, vector search, and complex data models, this stack offers production-ready patterns that scale.

The research platform architecture demonstrates how to combine these technologies effectively for systematic agent development and evaluation.

## Resources

All URLs from research:

**PydanticAI:**
- https://ai.pydantic.dev/
- https://github.com/pydantic/pydantic-ai
- https://ai.pydantic.dev/examples/sql-gen/
- https://christophergs.com/blog/pydantic-ai-example-github-actions

**Pydantic Evals:**
- https://ai.pydantic.dev/evals/
- https://ai.pydantic.dev/evals/evaluators/overview/

**Comparisons:**
- https://medium.com/@finndersen/langchain-vs-pydanticai-for-building-an-ai-agent-e0a059435e9d
- https://medium.com/@mahadevan.varadhan/pydanticai-vs-instructor-structured-llm-ai-outputs-with-python-tools-c7b7b202eb23

**Testing:**
- https://anaynayak.medium.com/eliminating-flaky-tests-using-vcr-tests-for-llms-a3feabf90bc5
- https://til.simonwillison.net/pytest/pytest-recording-vcr

**Observability:**
- https://logfire.pydantic.dev/
- https://opentelemetry.io/blog/2024/llm-observability/

**pgvector:**
- https://github.com/pgvector/pgvector
- https://github.com/pgvector/pgvector-python
- https://www.tanyongsheng.com/note/building-vector-search-for-financial-news-with-sqlalchemy-and-postgresql/
