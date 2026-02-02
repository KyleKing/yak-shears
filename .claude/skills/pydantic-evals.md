# PydanticAI Evals - Testing & Evaluation Framework

## Overview

Pydantic Evals is a powerful evaluation framework for systematically testing and evaluating AI systems, from simple LLM calls to complex multi-agent applications. It follows a code-first philosophy where all evaluation components are defined in Python.

**Official Docs**: https://ai.pydantic.dev/evals/

## Core Concepts

### Dataset and Cases

Everything starts with `Dataset` and `Case`:

```python
from pydantic_evals import Dataset, Case, evaluate_sync
from pydantic import BaseModel

class CustomerQuery(BaseModel):
    query: str
    customer_id: int

class Response(BaseModel):
    answer: str
    confidence: float

# Define test cases
dataset = Dataset(
    name='customer_support_qa',
    cases=[
        Case(
            inputs=CustomerQuery(
                query='What is my order status?',
                customer_id=12345
            ),
            expected_outputs={'answer': 'Your order is shipped'},
            metadata={'category': 'order_tracking'}
        ),
        Case(
            inputs=CustomerQuery(
                query='How do I return an item?',
                customer_id=67890
            ),
            expected_outputs={'answer': 'Returns are free within 30 days'},
            metadata={'category': 'returns'}
        ),
    ]
)
```

**Key Components**:
- **Dataset**: Collection of test Cases for a specific task
- **Case**: Single test scenario with inputs, optional expected outputs, metadata
- **Inputs**: Arguments passed to the function being evaluated
- **Expected Outputs**: Ground truth for comparison (optional)
- **Metadata**: Additional context for filtering/analysis

### Running Evaluations

```python
# Define the function to evaluate
async def answer_query(query: CustomerQuery) -> Response:
    result = await agent.run(
        f"Customer {query.customer_id} asks: {query.query}"
    )
    return Response(
        answer=result.data.answer,
        confidence=result.data.confidence
    )

# Run evaluation
report = await dataset.evaluate(answer_query)

# Print results
print(report)
# Shows pass/fail per case, metrics, timing
```

## Built-in Evaluators

### 1. Exact Match
```python
from pydantic_evals import exact_match

Case(
    inputs={'query': 'What is 2+2?'},
    expected_outputs={'answer': '4'},
    evaluators=[exact_match]
)
```

### 2. LLM as Judge
```python
from pydantic_evals import llm_judge

Case(
    inputs={'query': 'Explain quantum computing'},
    expected_outputs={'answer': 'Quantum computing uses...'},
    evaluators=[
        llm_judge(
            prompt='''Compare the actual answer to the expected answer.
Grade on accuracy and clarity (0-1 score).''',
            model='openai:gpt-4'
        )
    ]
)
```

### 3. Semantic Similarity
```python
from pydantic_evals import semantic_similarity

Case(
    inputs={'query': 'How to reset password?'},
    expected_outputs={'answer': 'Click forgot password link'},
    evaluators=[
        semantic_similarity(threshold=0.85)
    ]
)
```

## Custom Evaluators

Create domain-specific evaluators:

```python
from pydantic_evals import Evaluator, EvaluationResult

class ResponseTimeEvaluator(Evaluator):
    """Fail if response takes too long."""

    max_seconds: float = 2.0

    async def evaluate(
        self,
        inputs: dict,
        output: dict,
        expected_outputs: dict | None = None
    ) -> EvaluationResult:
        duration = output.get('duration_ms', 0) / 1000

        return EvaluationResult(
            passed=duration <= self.max_seconds,
            score=1.0 if duration <= self.max_seconds else 0.0,
            metadata={
                'duration_seconds': duration,
                'threshold': self.max_seconds
            }
        )

# Usage
Case(
    inputs={'query': 'Fast response please'},
    evaluators=[ResponseTimeEvaluator(max_seconds=1.5)]
)
```

### SQL Validation Evaluator
```python
class SQLValidityEvaluator(Evaluator):
    """Validate SQL can be parsed and executed."""

    async def evaluate(
        self,
        inputs: dict,
        output: dict,
        expected_outputs: dict | None = None
    ) -> EvaluationResult:
        sql = output.get('sql', '')

        try:
            # Test with EXPLAIN
            await db.execute(f'EXPLAIN {sql}')
            return EvaluationResult(
                passed=True,
                score=1.0,
                metadata={'sql_valid': True}
            )
        except Exception as e:
            return EvaluationResult(
                passed=False,
                score=0.0,
                metadata={
                    'sql_valid': False,
                    'error': str(e)
                }
            )
```

### Cost/Token Evaluator
```python
class CostEvaluator(Evaluator):
    """Fail if cost exceeds budget."""

    max_cost: float = 0.05  # $0.05 per query

    async def evaluate(self, inputs, output, expected_outputs=None):
        cost = output.get('cost', 0)

        return EvaluationResult(
            passed=cost <= self.max_cost,
            score=1.0 - (cost / (self.max_cost * 2)),  # Scaled score
            metadata={
                'cost_usd': cost,
                'budget_usd': self.max_cost,
                'tokens_used': output.get('tokens', 0)
            }
        )
```

## Span-Based Evaluation

Evaluate internal agent behavior using OpenTelemetry traces:

```python
from pydantic_evals import span_evaluator

@span_evaluator
async def check_tool_usage(span_data: dict) -> EvaluationResult:
    """Verify agent used the database tool."""

    tools_called = [
        span['name']
        for span in span_data['children']
        if span['type'] == 'tool_call'
    ]

    used_db = 'search_database' in tools_called

    return EvaluationResult(
        passed=used_db,
        score=1.0 if used_db else 0.0,
        metadata={
            'tools_called': tools_called,
            'expected_tool': 'search_database'
        }
    )

Case(
    inputs={'query': 'Find customer data'},
    evaluators=[check_tool_usage]
)
```

## Integration with Logfire

View evaluation results in Pydantic Logfire:

```python
import logfire

# Configure Logfire
logfire.configure()

# Evaluations automatically appear in Logfire
report = await dataset.evaluate(my_function)

# View in Logfire dashboard:
# - Per-case results
# - Aggregate metrics
# - Trace of each evaluation
# - Cost and latency data
```

**Logfire Benefits**:
- Visual debugging of failures
- Compare evaluation runs over time
- Filter by metadata/tags
- Export results for analysis

## Testing Patterns with pytest

### Basic Integration
```python
import pytest
from pydantic_evals import Dataset, Case

@pytest.fixture
def support_dataset():
    return Dataset(
        name='support_qa',
        cases=[
            Case(inputs={'q': 'refund?'}, expected_outputs={'a': 'yes'}),
            Case(inputs={'q': 'shipping?'}, expected_outputs={'a': '2-3 days'}),
        ]
    )

@pytest.mark.asyncio
async def test_support_agent(support_dataset):
    report = await support_dataset.evaluate(answer_question)
    assert report.passed_ratio >= 0.9, f'Only {report.passed_ratio:.0%} passed'
```

### Parametrized Tests
```python
@pytest.mark.parametrize('case', dataset.cases, ids=lambda c: c.metadata.get('id'))
async def test_individual_case(case):
    """Run each case as separate test for better failure visibility."""
    result = await my_function(**case.inputs)

    for evaluator in case.evaluators:
        eval_result = await evaluator.evaluate(
            case.inputs,
            result,
            case.expected_outputs
        )
        assert eval_result.passed, f'Evaluator {evaluator} failed'
```

## Caching with pytest-vcr

Record LLM responses to make tests deterministic and fast:

```python
import pytest
from pytest_recording import vcr

@pytest.fixture(scope='module')
def vcr_config():
    """Redact API keys from cassettes."""
    return {
        'filter_headers': ['authorization', 'api-key'],
        'filter_post_data_parameters': ['api_key'],
    }

@pytest.mark.vcr()
async def test_with_cache(support_dataset):
    """First run hits LLM, subsequent runs use cassette."""
    report = await support_dataset.evaluate(answer_question)
    assert report.passed_ratio >= 0.9

# Run tests
# First time: pytest --record-mode=once
# Subsequent: pytest (uses cached responses)
```

### Advanced VCR Pattern
```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture(scope='module')
def vcr_cassette_dir(request):
    """Store cassettes next to test file."""
    return Path(request.fspath).parent / 'cassettes'

# test_agent.py
@pytest.mark.vcr(cassette_library_dir='cassettes/agent')
async def test_agent_version_1():
    """Separate cassettes per test/version."""
    result = await agent_v1.run('test query')
    assert result.valid

@pytest.mark.vcr(cassette_library_dir='cassettes/agent')
async def test_agent_version_2():
    """Can compare v1 vs v2 with separate caches."""
    result = await agent_v2.run('test query')
    assert result.valid
```

## Regression Testing

Detect unintended changes:

```python
from pydantic_evals import Dataset, Case
import json
from pathlib import Path

# Store baseline results
baseline_file = Path('evals/baselines/agent_v1.json')

async def create_baseline(dataset: Dataset):
    """Generate and save baseline results."""
    report = await dataset.evaluate(my_function)

    baseline = {
        'cases': [
            {
                'inputs': case.inputs,
                'output': result.output,
                'score': result.score,
            }
            for case, result in zip(dataset.cases, report.results)
        ],
        'metrics': {
            'passed_ratio': report.passed_ratio,
            'avg_score': report.average_score,
        }
    }

    baseline_file.write_text(json.dumps(baseline, indent=2))

async def test_against_baseline(dataset: Dataset):
    """Ensure new version matches baseline."""
    baseline = json.loads(baseline_file.read_text())

    report = await dataset.evaluate(my_function)

    # Check metrics didn't regress
    assert report.passed_ratio >= baseline['metrics']['passed_ratio']
    assert report.average_score >= baseline['metrics']['avg_score'] * 0.95

    # Check specific critical cases
    critical_cases = [i for i, c in enumerate(dataset.cases) if c.metadata.get('critical')]
    for i in critical_cases:
        assert report.results[i].passed, f'Critical case {i} failed'
```

## Dataset Versioning

Track evaluation datasets over time:

```python
from datetime import datetime
from pydantic_evals import Dataset

class VersionedDataset:
    """Manage dataset versions."""

    def __init__(self, name: str, base_path: Path):
        self.name = name
        self.base_path = base_path

    def save(self, dataset: Dataset, version: str | None = None):
        """Save dataset with version."""
        version = version or datetime.now().isoformat()
        path = self.base_path / f'{self.name}-{version}.json'

        data = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'cases': [c.model_dump() for c in dataset.cases],
        }

        path.write_text(json.dumps(data, indent=2))
        return version

    def load(self, version: str) -> Dataset:
        """Load specific version."""
        path = self.base_path / f'{self.name}-{version}.json'
        data = json.loads(path.read_text())

        return Dataset(
            name=self.name,
            cases=[Case(**c) for c in data['cases']]
        )

# Usage
vds = VersionedDataset('support_qa', Path('evals/datasets'))
vds.save(dataset, version='v1.0')

# Later
dataset_v1 = vds.load('v1.0')
```

## A/B Testing Patterns

Compare different approaches:

```python
async def compare_agents():
    """Compare two agent implementations."""

    results = {}

    for name, agent in [('baseline', agent_v1), ('new', agent_v2)]:
        report = await dataset.evaluate(
            lambda inputs: agent.run(**inputs)
        )

        results[name] = {
            'passed_ratio': report.passed_ratio,
            'avg_score': report.average_score,
            'avg_cost': report.average_cost,
            'avg_latency': report.average_latency,
        }

    print(f"Baseline: {results['baseline']}")
    print(f"New: {results['new']}")

    # Statistical comparison
    improvement = (
        results['new']['avg_score'] - results['baseline']['avg_score']
    ) / results['baseline']['avg_score']

    print(f"Score improvement: {improvement:.1%}")
```

## Cost Tracking

Monitor evaluation costs:

```python
class CostTracker:
    """Track cumulative costs across evaluations."""

    def __init__(self):
        self.costs: list[dict] = []

    async def evaluate_with_tracking(
        self,
        dataset: Dataset,
        func,
        version: str
    ):
        """Run evaluation and track costs."""
        report = await dataset.evaluate(func)

        cost_data = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'total_cost': report.total_cost,
            'avg_cost_per_case': report.average_cost,
            'num_cases': len(dataset.cases),
            'passed_ratio': report.passed_ratio,
        }

        self.costs.append(cost_data)
        return report

    def cost_summary(self):
        """Analyze cost trends."""
        return pd.DataFrame(self.costs).describe()

# Usage
tracker = CostTracker()
await tracker.evaluate_with_tracking(dataset, agent.run, 'v1.0')
await tracker.evaluate_with_tracking(dataset, agent_v2.run, 'v2.0')
print(tracker.cost_summary())
```

## Best Practices

### 1. Start with Small, Focused Datasets
```python
# ❌ Too broad
dataset = Dataset(
    name='everything',
    cases=[...1000 diverse cases...]
)

# ✅ Focused datasets
datasets = {
    'order_status': Dataset(cases=[...20 order cases...]),
    'returns': Dataset(cases=[...15 return cases...]),
    'shipping': Dataset(cases=[...10 shipping cases...]),
}
```

### 2. Use Metadata for Organization
```python
Case(
    inputs={'query': 'Where is my order?'},
    expected_outputs={'answer': '...'},
    metadata={
        'category': 'order_tracking',
        'difficulty': 'easy',
        'critical': True,
        'added_date': '2025-01-15',
        'ticket_id': 'SUP-1234'
    }
)

# Filter during analysis
critical_results = [
    r for r, c in zip(report.results, dataset.cases)
    if c.metadata.get('critical')
]
```

### 3. Combine Multiple Evaluators
```python
Case(
    inputs={'query': 'SQL for top customers'},
    expected_outputs={'sql': 'SELECT...'},
    evaluators=[
        SQLValidityEvaluator(),
        CostEvaluator(max_cost=0.02),
        ResponseTimeEvaluator(max_seconds=3.0),
        llm_judge(prompt='Grade SQL quality 0-1'),
    ]
)
```

### 4. Version Control Your Datasets
```python
# Store datasets in git
# evals/
#   datasets/
#     support_qa_v1.json
#     support_qa_v2.json
#   baselines/
#     agent_v1_results.json
#   cassettes/  # gitignored if contains sensitive data
#     test_agent/
```

### 5. Continuous Evaluation
```python
# Run in CI/CD
@pytest.mark.slow
@pytest.mark.vcr()
async def test_regression_suite():
    """Run full eval suite (cached with VCR)."""
    for dataset_name, dataset in datasets.items():
        report = await dataset.evaluate(agent.run)

        # Must pass critical cases
        critical_passed = sum(
            1 for r, c in zip(report.results, dataset.cases)
            if c.metadata.get('critical') and r.passed
        )
        critical_total = sum(
            1 for c in dataset.cases
            if c.metadata.get('critical')
        )

        assert critical_passed == critical_total, \
            f'{dataset_name}: {critical_passed}/{critical_total} critical cases passed'
```

## Common Patterns

### Golden Dataset Creation
```python
async def create_golden_dataset_from_logs():
    """Build evaluation dataset from production logs."""

    # Query production logs
    queries = await db.query('''
        SELECT user_query, agent_response, user_feedback
        FROM production_logs
        WHERE user_feedback = 'positive'
        AND timestamp > NOW() - INTERVAL '30 days'
        LIMIT 50
    ''')

    cases = [
        Case(
            inputs={'query': q['user_query']},
            expected_outputs={'response': q['agent_response']},
            metadata={
                'source': 'production',
                'feedback': 'positive'
            }
        )
        for q in queries
    ]

    return Dataset(name='golden_set', cases=cases)
```

### Multi-Model Comparison
```python
async def compare_models():
    """Evaluate same dataset across multiple models."""

    models = ['gpt-4', 'claude-sonnet-4-5', 'gemini-2.5-pro']
    results = {}

    for model in models:
        agent = Agent(model)
        report = await dataset.evaluate(agent.run)

        results[model] = {
            'score': report.average_score,
            'cost': report.total_cost,
            'latency': report.average_latency,
        }

    # Find best value
    best_score = max(results.items(), key=lambda x: x[1]['score'])
    best_cost = min(results.items(), key=lambda x: x[1]['cost'])

    print(f'Best score: {best_score}')
    print(f'Best cost: {best_cost}')
```

## Resources

- **Official Evals Docs**: https://ai.pydantic.dev/evals/
- **Evaluators Guide**: https://ai.pydantic.dev/evals/evaluators/
- **pytest-vcr**: https://pytest-vcr.readthedocs.io/
- **pytest-recording**: https://pypi.org/project/pytest-recording/
- **Logfire**: https://logfire.pydantic.dev/

## Summary

Pydantic Evals provides:
- **Code-first** evaluation framework
- **Built-in evaluators** (exact match, LLM judge, semantic similarity)
- **Custom evaluators** for domain-specific requirements
- **Span-based evaluation** for internal agent behavior
- **pytest integration** for CI/CD
- **VCR caching** for deterministic, fast tests
- **Logfire integration** for visual debugging and analysis
- **Versioning and tracking** for long-term monitoring
