# Agent Research Platform Architecture

## Overview

A comprehensive research platform for building, testing, and evaluating agentic LLM applications with PostgreSQL/pgvector for B2B use cases.

## Goals

1. **Demonstrate Production-Ready Patterns** for agent development
2. **Solve Real B2B Problems** - large databases with selective retrieval
3. **Comprehensive Evaluation** with caching and versioning
4. **Cost/Quality Monitoring** across experiments
5. **Research Infrastructure** for comparing models, prompts, and approaches

## Technology Stack

### Core
- **Python 3.12** with modern async patterns
- **uv** - Fast dependency management
- **PostgreSQL 16** with pgvector extension
- **SQLAlchemy 2.0** - ORM with async support
- **Alembic** - Database migrations

### Agent Framework
- **PydanticAI** - Type-safe agent framework
- **Pydantic 2.x** - Validation and structured outputs
- **Logfire** - Observability and tracing

### Evaluation & Testing
- **Pydantic Evals** - Evaluation framework
- **pytest** - Testing framework
- **pytest-recording** - VCR cassette caching for LLMs
- **pytest-asyncio** - Async test support

### Observability & Metrics
- **OpenTelemetry** - Tracing and spans
- **Logfire** - Dashboard and analysis
- **litellm** (optional) - Multi-provider cost tracking

## Architecture Components

### 1. Database Layer (PostgreSQL + pgvector)

**Schema Design** - B2B SaaS use case:

```
Organizations (tenants)
├── Users (employees)
├── Products (catalog items)
├── Customers (their customers)
│   ├── Orders
│   │   └── OrderItems
│   └── SupportTickets
│       └── TicketMessages
└── Documents (embeddings for RAG)
```

**Key Features**:
- Multi-tenant data isolation
- pgvector for semantic search on documents, products, tickets
- Complex joins for realistic queries
- Indexes for performance (HNSW, B-tree)

**Sample Queries**:
- "Show me top 10 customers by revenue for Organization X"
- "Find all unresolved tickets with sentiment analysis"
- "Semantic search: products similar to 'enterprise CRM software'"

### 2. Agent Layer (PydanticAI)

**Agent Types**:

1. **SQL Agent** - Generates and validates SQL queries
   - Schema awareness via system prompts
   - Self-healing with EXPLAIN validation
   - Row-level security for multi-tenancy

2. **RAG Agent** - Semantic search + generation
   - pgvector similarity search
   - Embedding generation (OpenAI, local models)
   - Context window management

3. **Data Analysis Agent** - Multi-step reasoning
   - Tool chaining (SQL → aggregation → visualization)
   - Structured outputs (charts, tables, insights)

4. **Customer Support Agent** - B2B support automation
   - Ticket retrieval and search
   - Order status lookup
   - Product recommendations

**Tool Catalog**:
```python
@agent.tool
async def semantic_search_documents(
    ctx: RunContext[Deps],
    query: str,
    organization_id: int,
    limit: int = 5
) -> list[Document]:
    """Search documents using vector similarity."""

@agent.tool
async def execute_sql_query(
    ctx: RunContext[Deps],
    sql: str,
    organization_id: int
) -> list[dict]:
    """Execute SQL with RLS enforcement."""

@agent.tool
async def get_customer_orders(
    ctx: RunContext[Deps],
    customer_id: int,
    organization_id: int,
    limit: int = 10
) -> list[Order]:
    """Retrieve customer orders with details."""

@agent.tool
async def analyze_ticket_sentiment(
    ctx: RunContext[Deps],
    ticket_id: int,
    organization_id: int
) -> SentimentAnalysis:
    """Analyze support ticket sentiment."""
```

### 3. Evaluation Framework

**Dataset Categories**:

1. **SQL Generation**
   - Golden queries with expected results
   - Edge cases (empty results, complex joins)
   - Performance benchmarks

2. **RAG Quality**
   - Retrieval accuracy (precision@k, recall@k)
   - Answer relevance
   - Hallucination detection

3. **Multi-Step Reasoning**
   - Tool selection accuracy
   - Plan quality
   - Final result correctness

4. **Cost/Latency**
   - Token usage per query type
   - Response time SLAs
   - Cost per conversation

**Evaluator Examples**:
```python
class SQLValidityEvaluator(Evaluator):
    """Validates SQL executes successfully."""

class CostBudgetEvaluator(Evaluator):
    """Ensures query stays within budget."""

class LatencyEvaluator(Evaluator):
    """Checks response time < threshold."""

class TenantIsolationEvaluator(Evaluator):
    """Verifies RLS prevents data leakage."""

class RAGRelevanceEvaluator(Evaluator):
    """LLM-as-judge for answer quality."""
```

### 4. Caching & Reproducibility

**pytest-recording Integration**:
- Cassette storage: `tests/cassettes/{test_module}/{test_name}.yaml`
- Automatic API key redaction
- Separate cassettes per model/version
- CI/CD friendly (no real API calls)

**Versioned Datasets**:
```
evals/
  datasets/
    sql_generation_v1.0.json
    sql_generation_v1.1.json
    rag_quality_v1.0.json
  baselines/
    agent_v1.0_results.json
    agent_v2.0_results.json
  cassettes/  # gitignored
    test_sql_agent/
    test_rag_agent/
```

### 5. Pipeline Versioning System

**Version Tracking**:
- Agent version (code changes)
- Prompt version (system prompt, tool descriptions)
- Model version (gpt-4 vs claude vs gemini)
- Dataset version
- Evaluator version

**Storage**:
```python
class ExperimentRun(Base):
    __tablename__ = 'experiment_runs'

    id: UUID
    name: str
    timestamp: datetime
    agent_version: str
    model: str
    prompt_version: str
    dataset_version: str

    # Results
    passed_ratio: float
    avg_score: float
    total_cost: float
    avg_latency: float
    token_usage: dict  # JSON

    # Relationships
    case_results: list[CaseResult]
```

**Comparison Queries**:
```sql
-- Compare two experiment runs
SELECT
    r1.name as baseline,
    r2.name as experiment,
    r2.passed_ratio - r1.passed_ratio as score_delta,
    r2.total_cost - r1.total_cost as cost_delta
FROM experiment_runs r1
JOIN experiment_runs r2 ON r1.dataset_version = r2.dataset_version
WHERE r1.id = :baseline_id AND r2.id = :experiment_id;
```

### 6. Cost & Quality Metrics

**Tracked Metrics**:

1. **Cost Metrics**
   - Total cost per run
   - Cost per case
   - Cost by model
   - Cost by tool/operation
   - Token usage (input/output breakdown)

2. **Quality Metrics**
   - Pass rate by category
   - Average evaluator scores
   - Critical case success rate
   - Regression detection

3. **Performance Metrics**
   - P50/P95/P99 latency
   - Time to first token
   - Tool call count per query
   - Retry rate

4. **Anonymous Quality Metrics** (production)
   - User satisfaction (thumbs up/down)
   - Task completion rate
   - Escalation to human rate
   - Query abandonment

**Implementation**:
```python
class MetricsCollector:
    """Collect anonymous metrics during eval runs."""

    async def record_run(
        self,
        experiment_id: UUID,
        case_id: str,
        result: EvaluationResult,
        trace_data: dict
    ):
        # Extract from OpenTelemetry spans
        metrics = {
            'cost': self._extract_cost(trace_data),
            'tokens': self._extract_tokens(trace_data),
            'latency_ms': self._extract_latency(trace_data),
            'tool_calls': self._extract_tool_calls(trace_data),
            'retries': self._extract_retries(trace_data),
        }

        await self.db.insert_metrics(
            experiment_id=experiment_id,
            case_id=case_id,
            metrics=metrics,
            score=result.score,
            passed=result.passed
        )
```

### 7. B2B Use Case: Multi-Tenant SaaS Analytics

**Scenario**: Customer Success team needs insights across multiple clients

**Sample Queries**:

1. "Which customers in the enterprise tier have submitted tickets in the last 7 days?"
   - Tool: SQL query with tenant filtering
   - Challenge: Multi-table join, date filtering, tier lookup

2. "Find documentation similar to 'API rate limiting'"
   - Tool: pgvector semantic search
   - Challenge: Embedding generation, similarity threshold tuning

3. "What are the top 3 product categories by revenue this quarter?"
   - Tool: SQL aggregation
   - Challenge: Date ranges, grouping, sorting

4. "Show me customers at risk of churning based on support ticket volume and sentiment"
   - Tool: Multi-step (SQL + sentiment analysis + scoring)
   - Challenge: Tool chaining, complex logic, result synthesis

**Agent Architecture**:
```python
@dataclass
class B2BDeps:
    db: AsyncEngine
    embeddings: EmbeddingService
    organization_id: int  # Tenant context
    user_id: int  # For audit logging

agent = Agent(
    'openai:gpt-4',
    deps_type=B2BDeps,
    result_type=AnalysisResult
)

@agent.system_prompt
async def b2b_context(ctx: RunContext[B2BDeps]) -> str:
    org = await get_organization(ctx.deps.organization_id)
    schema = await get_schema_for_org(ctx.deps.organization_id)

    return f'''You are a data analyst for {org.name}.

Available tables: {schema}

Important:
- All queries MUST filter by organization_id = {org.id}
- Use semantic_search for document questions
- Use SQL for structured data queries
- Always explain your reasoning
'''
```

### 8. Advanced Features

**Re-running with New Models**:
```python
async def rerun_experiment(
    experiment_id: UUID,
    new_model: str
) -> ExperimentRun:
    """Re-run previous experiment with different model."""

    original = await db.get_experiment(experiment_id)
    dataset = await load_dataset(original.dataset_version)

    # Create new agent with same prompts
    agent = Agent(
        new_model,
        system_prompt=original.system_prompt,
        # ... same tools, validators
    )

    # Run evaluation
    report = await dataset.evaluate(agent.run)

    # Save new run
    return await save_experiment(
        name=f'{original.name}_rerun_{new_model}',
        parent_id=experiment_id,
        results=report,
        model=new_model
    )
```

**Prompt Optimization**:
```python
class PromptVersion:
    """Track prompt variations."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def save_variant(self, name: str, prompt: str, metadata: dict):
        """Save prompt variant with metadata."""
        version_id = str(uuid.uuid4())[:8]
        path = self.base_path / f'{name}_v{version_id}.txt'

        data = {
            'version_id': version_id,
            'prompt': prompt,
            'created_at': datetime.now().isoformat(),
            **metadata
        }

        path.write_text(json.dumps(data, indent=2))
        return version_id

    async def test_variants(
        self,
        variants: list[str],
        dataset: Dataset
    ) -> dict:
        """Test multiple prompt variants."""
        results = {}

        for variant_id in variants:
            prompt = self.load_variant(variant_id)
            agent = Agent('openai:gpt-4', system_prompt=prompt['prompt'])

            report = await dataset.evaluate(agent.run)
            results[variant_id] = {
                'score': report.average_score,
                'cost': report.total_cost,
                'passed': report.passed_ratio,
            }

        return results
```

**Diff Analysis**:
```python
async def compare_experiments(
    baseline_id: UUID,
    experiment_id: UUID
) -> ComparisonReport:
    """Detailed diff between two experiment runs."""

    baseline = await db.get_experiment_with_results(baseline_id)
    experiment = await db.get_experiment_with_results(experiment_id)

    # Overall metrics diff
    metrics_diff = {
        'score_delta': experiment.avg_score - baseline.avg_score,
        'cost_delta': experiment.total_cost - baseline.total_cost,
        'latency_delta': experiment.avg_latency - baseline.avg_latency,
    }

    # Per-case diff
    case_diffs = []
    for b_result, e_result in zip(baseline.results, experiment.results):
        if b_result.passed != e_result.passed:
            case_diffs.append({
                'case_id': b_result.case_id,
                'regression': e_result.passed < b_result.passed,
                'baseline_score': b_result.score,
                'experiment_score': e_result.score,
            })

    return ComparisonReport(
        metrics=metrics_diff,
        regressions=[c for c in case_diffs if c['regression']],
        improvements=[c for c in case_diffs if not c['regression']],
    )
```

## Directory Structure

```
agent-research-platform/
├── pyproject.toml              # uv dependencies
├── uv.lock
├── README.md
├── ARCHITECTURE.md             # This file
│
├── src/
│   └── research_platform/
│       ├── __init__.py
│       ├── config.py           # Settings, env vars
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py       # SQLAlchemy models
│       │   ├── session.py      # DB session management
│       │   └── embeddings.py   # pgvector utilities
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── sql_agent.py
│       │   ├── rag_agent.py
│       │   ├── analysis_agent.py
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── database.py
│       │       ├── search.py
│       │       └── analysis.py
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── datasets.py     # Dataset loaders
│       │   ├── evaluators/
│       │   │   ├── __init__.py
│       │   │   ├── sql.py
│       │   │   ├── rag.py
│       │   │   ├── cost.py
│       │   │   └── security.py
│       │   └── runner.py       # Eval orchestration
│       │
│       ├── experiments/
│       │   ├── __init__.py
│       │   ├── versioning.py   # Version management
│       │   ├── comparison.py   # Diff and analysis
│       │   └── models.py       # Experiment SQLAlchemy models
│       │
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── collector.py    # Metrics collection
│       │   └── analysis.py     # Metrics analysis
│       │
│       └── cli/
│           ├── __init__.py
│           ├── run.py          # Run experiments
│           ├── eval.py         # Run evaluations
│           └── compare.py      # Compare runs
│
├── tests/
│   ├── conftest.py             # pytest fixtures
│   ├── cassettes/              # VCR cassettes (gitignored)
│   ├── test_agents/
│   │   ├── test_sql_agent.py
│   │   ├── test_rag_agent.py
│   │   └── test_analysis_agent.py
│   ├── test_evaluation/
│   │   └── test_evaluators.py
│   └── test_integration/
│       └── test_b2b_scenarios.py
│
├── evals/
│   ├── datasets/
│   │   ├── sql_generation_v1.0.json
│   │   └── rag_quality_v1.0.json
│   ├── baselines/
│   │   └── agent_v1_results.json
│   └── prompts/
│       ├── sql_agent_v1.txt
│       └── rag_agent_v1.txt
│
├── migrations/                  # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── scripts/
│   ├── setup_db.py             # Initial DB setup
│   ├── seed_data.py            # Generate B2B test data
│   └── generate_embeddings.py # Pre-compute embeddings
│
└── docs/
    ├── getting_started.md
    ├── b2b_scenarios.md
    └── evaluation_guide.md
```

## Development Workflow

1. **Setup**:
   ```bash
   uv sync
   ./scripts/setup_db.py
   ./scripts/seed_data.py
   ```

2. **Development**:
   ```bash
   # Run agent
   python -m research_platform.cli.run sql_agent --query "Top customers"

   # Run evaluation
   python -m research_platform.cli.eval sql_agent --dataset sql_v1

   # Compare experiments
   python -m research_platform.cli.compare baseline_id experiment_id
   ```

3. **Testing**:
   ```bash
   # First run - record cassettes
   pytest --record-mode=once

   # Subsequent runs - use cassettes
   pytest

   # Re-record specific test
   pytest tests/test_agents/test_sql_agent.py --record-mode=rewrite
   ```

4. **Evaluation**:
   ```bash
   # Run full eval suite
   pytest tests/test_evaluation/ -v

   # View in Logfire
   open https://logfire.pydantic.dev/
   ```

## Key Innovations

1. **Multi-Tenant Aware Agents** - RLS enforcement in tools
2. **Versioned Everything** - Prompts, datasets, models, experiments
3. **Cost-Aware Evaluation** - Budget constraints as first-class evaluators
4. **Reproducible Research** - VCR caching + version control
5. **Production-Ready Patterns** - Observability, error handling, security
6. **Comparative Analysis** - Easy A/B testing and regression detection

## Success Metrics

- **Developer Experience**: Time to add new agent < 30 min
- **Evaluation Speed**: Full test suite < 5 min (with caching)
- **Cost Efficiency**: Track cost per query type, optimize high-cost paths
- **Quality**: >95% pass rate on critical cases
- **Reproducibility**: Same inputs = same outputs (with VCR)
