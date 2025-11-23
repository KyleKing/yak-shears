# PydanticAI Agent Framework

## Overview

PydanticAI is a production-ready agent framework from the Pydantic team that brings type safety and ergonomic developer experience to GenAI applications. It provides a FastAPI-style DX for building LLM-powered agents with automatic validation, observability, and structured outputs.

**Key Philosophy**: Schema-first, type-safe approach with Python's native syntax and familiar control flow.

## Core Concepts

### Agent Definition

```python
from pydantic_ai import Agent
from pydantic import BaseModel

# Simple agent
agent = Agent(
    'openai:gpt-4',
    system_prompt='You are a helpful assistant',
)

# Agent with structured output
class FlightBooking(BaseModel):
    origin: str
    destination: str
    departure_date: str

booking_agent = Agent(
    'openai:gpt-4',
    result_type=FlightBooking,
)
```

### Running Agents

Three execution modes:

```python
# Async execution (recommended)
result = await agent.run('User message')

# Synchronous execution
result = agent.run_sync('User message')

# Streaming responses
async for message in agent.run_stream('User message'):
    print(message)
```

## Dependency Injection with RunContext

**Core Pattern**: Use `RunContext[DepsType]` for type-safe dependency injection without global state.

```python
from pydantic_ai import RunContext
from dataclasses import dataclass
import httpx

@dataclass
class MyDeps:
    api_key: str
    http_client: httpx.AsyncClient
    database: Database

agent = Agent('openai:gpt-4', deps_type=MyDeps)

# Dynamic system prompt with dependencies
@agent.system_prompt
async def get_system_prompt(ctx: RunContext[MyDeps]) -> str:
    response = await ctx.deps.http_client.get(
        'https://api.example.com/config',
        headers={'Authorization': f'Bearer {ctx.deps.api_key}'}
    )
    return f'System config: {response.json()}'

# Run with dependencies
deps = MyDeps(
    api_key='secret',
    http_client=httpx.AsyncClient(),
    database=db_conn
)
result = await agent.run('Query', deps=deps)
```

### Dynamic System Prompts

Three types:

1. **Static** (evaluated once at agent construction):
```python
agent = Agent('openai:gpt-4', system_prompt='Fixed prompt')
```

2. **Dynamic non-dynamic** (evaluated once per run):
```python
@agent.system_prompt
async def dynamic_prompt(ctx: RunContext[MyDeps]) -> str:
    return f'User preferences: {await ctx.deps.database.get_preferences()}'
```

3. **Dynamic with dynamic=True** (re-evaluated every step):
```python
@agent.system_prompt(dynamic=True)
async def adaptive_prompt(ctx: RunContext[MyDeps]) -> str:
    # Access retry count, messages history, etc.
    return f'Attempt {ctx.retry}, messages: {len(ctx.messages)}'
```

## Tool Calling

Register functions the LLM can call using `@agent.tool`:

```python
@agent.tool
async def search_database(
    ctx: RunContext[MyDeps],
    query: str,
    limit: int = 10
) -> list[dict]:
    """Search the database for relevant records.

    Args:
        query: Search query string
        limit: Maximum number of results (default: 10)
    """
    # RunContext provides dependencies
    results = await ctx.deps.database.search(query, limit=limit)
    return [r.to_dict() for r in results]

@agent.tool
def calculate_price(
    quantity: int,
    unit_price: float,
    discount_percent: float = 0
) -> float:
    """Calculate total price with optional discount.

    Args:
        quantity: Number of items
        unit_price: Price per item
        discount_percent: Discount percentage (0-100)
    """
    subtotal = quantity * unit_price
    discount = subtotal * (discount_percent / 100)
    return subtotal - discount
```

**Key Points**:
- First parameter can be `RunContext[DepsType]` for dependency access
- All other parameters become the tool schema passed to LLM
- Docstrings are critical - LLM uses them to understand tool purpose
- Return types should be JSON-serializable or Pydantic models

## Output Validation

Validate agent outputs before returning to user:

```python
from pydantic_ai import ModelRetry

@agent.result_validator
async def validate_sql(ctx: RunContext[MyDeps], result: str) -> str:
    """Validate SQL by running EXPLAIN query."""
    try:
        await ctx.deps.database.execute(f'EXPLAIN {result}')
        return result
    except Exception as e:
        # Raise ModelRetry to ask LLM to try again
        raise ModelRetry(f'Invalid SQL: {e}') from e
```

## SQL Generation Pattern

Based on official pydantic-ai SQL example:

```python
from pydantic import BaseModel
from typing import Union

class Success(BaseModel):
    sql: str
    explanation: str

class InvalidRequest(BaseModel):
    error_message: str

sql_agent = Agent(
    'gemini-2.5-flash',  # Good for single-shot SQL
    result_type=Union[Success, InvalidRequest],
    system_prompt='''Generate PostgreSQL queries.
Return Success with valid SQL or InvalidRequest if impossible.'''
)

@sql_agent.result_validator
async def validate_sql(ctx: RunContext[DatabaseDeps], result: Union[Success, InvalidRequest]) -> Union[Success, InvalidRequest]:
    if isinstance(result, InvalidRequest):
        return result

    # Validate with EXPLAIN
    try:
        await ctx.deps.db.execute(f'EXPLAIN {result.sql}')
        return result
    except Exception as e:
        raise ModelRetry(f'Invalid SQL: {e}')

# Usage
result = await sql_agent.run(
    'Show me top 10 customers by revenue',
    deps=DatabaseDeps(db=db_connection)
)
```

## Observability with Logfire

PydanticAI integrates natively with Pydantic Logfire (built on OpenTelemetry):

```python
import logfire
from pydantic_ai import Agent

# Configure Logfire
logfire.configure()

# Instrument PydanticAI
logfire.instrument_pydantic_ai()

agent = Agent('openai:gpt-4')

# All runs automatically traced
result = await agent.run('Hello')
# View traces in Logfire dashboard
```

**Logfire provides**:
- Complete trace of agent execution (tools, retries, validation)
- Token usage and cost tracking
- Latency metrics
- Error tracking and debugging

## Multi-Model Support

PydanticAI works with 15+ LLM providers:

```python
# OpenAI
agent = Agent('openai:gpt-4')
agent = Agent('openai:gpt-4o-mini')

# Anthropic
agent = Agent('anthropic:claude-sonnet-4-5')

# Google
agent = Agent('gemini-2.5-flash')
agent = Agent('gemini-2.5-pro')

# Groq
agent = Agent('groq:llama-3.3-70b')

# Local with Ollama
agent = Agent('ollama:qwen2.5-coder')
```

## Best Practices

### 1. Use Type Hints Everywhere
```python
from typing import Annotated
from pydantic import Field

@agent.tool
def search(
    query: Annotated[str, Field(description='Search query')],
    max_results: Annotated[int, Field(ge=1, le=100)] = 10
) -> list[dict]:
    """Type hints + Field constraints = better tool calling."""
    pass
```

### 2. Dependency Injection Over Global State
```python
# ❌ Bad - global state
db = connect_database()

@agent.tool
def query_db(sql: str):
    return db.execute(sql)

# ✅ Good - dependency injection
@dataclass
class Deps:
    db: Database

@agent.tool
async def query_db(ctx: RunContext[Deps], sql: str):
    return await ctx.deps.db.execute(sql)
```

### 3. Comprehensive Tool Docstrings
```python
@agent.tool
async def fetch_customer(
    ctx: RunContext[Deps],
    customer_id: int
) -> dict:
    """Fetch customer details from the database.

    Use this when you need customer information like:
    - Contact details (email, phone)
    - Order history
    - Account status

    Args:
        customer_id: Unique customer identifier

    Returns:
        Customer record with all fields, or empty dict if not found
    """
    pass
```

### 4. Structured Outputs for Complex Results
```python
class AnalysisResult(BaseModel):
    summary: str
    key_findings: list[str]
    confidence_score: float = Field(ge=0, le=1)
    recommendations: list[str]

agent = Agent('openai:gpt-4', result_type=AnalysisResult)
```

### 5. Validation and Error Handling
```python
@agent.result_validator
async def validate_result(ctx: RunContext[Deps], result: MyResult) -> MyResult:
    # Check business logic
    if result.total_price < 0:
        raise ModelRetry('Price cannot be negative')

    # Validate against external system
    if not await ctx.deps.api.validate(result):
        raise ModelRetry('External validation failed')

    return result
```

## Comparison with Alternatives

### vs LangChain
- **PydanticAI**: Simpler, type-safe, production-focused, minimal abstractions
- **LangChain**: Feature-rich, complex, many deprecated patterns, good for demos

### vs Instructor
- **PydanticAI**: Full agent framework (tools, validation, retries, observability)
- **Instructor**: Focused on structured data extraction, no agent capabilities

### vs LlamaIndex
- **PydanticAI**: General-purpose agents, bring your own RAG
- **LlamaIndex**: Specialized for RAG and document search

## Common Patterns

### Database Agent with RAG
```python
@dataclass
class RAGDeps:
    db: Database
    embeddings: EmbeddingService

agent = Agent('openai:gpt-4', deps_type=RAGDeps)

@agent.tool
async def semantic_search(
    ctx: RunContext[RAGDeps],
    query: str,
    limit: int = 5
) -> list[str]:
    """Search documents using semantic similarity."""
    embedding = await ctx.deps.embeddings.embed(query)
    results = await ctx.deps.db.vector_search(embedding, limit=limit)
    return [r['content'] for r in results]

@agent.system_prompt
async def context_prompt(ctx: RunContext[RAGDeps]) -> str:
    return """You are a helpful assistant with access to our document database.
Use semantic_search to find relevant information before answering."""
```

### Multi-Step Workflow
```python
class WorkflowState(BaseModel):
    step: int = 0
    data_collected: dict = {}

@agent.tool
async def save_data(
    ctx: RunContext[Deps],
    key: str,
    value: str
) -> str:
    """Save data for later steps."""
    # Access workflow state via dependencies
    ctx.deps.state.data_collected[key] = value
    ctx.deps.state.step += 1
    return f'Saved {key}, now on step {ctx.deps.state.step}'
```

### Self-Healing SQL
```python
@sql_agent.result_validator
async def validate_and_fix(
    ctx: RunContext[Deps],
    result: Success
) -> Success:
    try:
        await ctx.deps.db.execute(f'EXPLAIN {result.sql}')
        return result
    except Exception as e:
        # Let the LLM try to fix it
        raise ModelRetry(
            f'SQL error: {e}. Please fix the query. '
            f'Schema: {await ctx.deps.db.get_schema()}'
        )
```

## Resources

- **Official Docs**: https://ai.pydantic.dev/
- **GitHub**: https://github.com/pydantic/pydantic-ai
- **Examples**: https://ai.pydantic.dev/examples/
- **Logfire**: https://logfire.pydantic.dev/

## When to Use PydanticAI

**Use PydanticAI when**:
- Building production applications (not just demos)
- You value type safety and IDE support
- You need observability and monitoring
- You want minimal abstractions and clear control flow
- You're already using Pydantic/FastAPI

**Consider alternatives when**:
- You only need structured extraction (use Instructor)
- You're building quick demos/prototypes (LangChain might be faster)
- You need specialized RAG features (LlamaIndex)
