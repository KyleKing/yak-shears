"""Pytest configuration and fixtures for medical agent tests."""

import pytest
import asyncio
from pathlib import Path

from research_platform.config import settings


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def vcr_config():
    """Configuration for pytest-recording (VCR)."""
    return {
        # Filter sensitive headers
        "filter_headers": [
            "authorization",
            "api-key",
            "x-api-key",
            "openai-api-key",
            "anthropic-api-key",
        ],
        # Filter sensitive POST data
        "filter_post_data_parameters": [
            "api_key",
            "password",
        ],
        # Record mode
        "record_mode": settings.eval_record_mode,
        # Match on method and path
        "match_on": ["method", "scheme", "host", "port", "path"],
        # Custom cassette library dir
        "cassette_library_dir": str(Path(__file__).parent / "cassettes"),
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    """Cassette directory per test module."""
    return Path(request.fspath).parent / "cassettes" / request.module.__name__


# Mock dependencies for testing


@pytest.fixture
def mock_medical_deps():
    """Mock medical agent dependencies."""
    from research_platform.agents.tools.medical import MedicalDeps
    from research_platform.db.session import get_engine

    return MedicalDeps(
        db=get_engine(),
        institution_id=1,  # Test institution
        user_email="test@example.com",
        user_id=1,
    )


@pytest.fixture
def mock_research_deps():
    """Mock research agent dependencies."""
    from research_platform.agents.tools.research import ResearchDeps
    from research_platform.db.session import get_engine
    from research_platform.db.embeddings import EmbeddingService

    return ResearchDeps(
        db=get_engine(),
        embeddings=EmbeddingService(),
        institution_id=1,
        user_email="researcher@example.com",
    )


# Test data fixtures


@pytest.fixture
def sample_mrn():
    """Sample MRN for testing."""
    return "MRN-001"


@pytest.fixture
def sample_icd10_codes():
    """Sample ICD-10 codes."""
    return {
        "diabetes_type2": "E11",
        "hypertension": "I10",
        "asthma": "J45",
        "depression": "F32",
    }


@pytest.fixture
def sample_medications():
    """Sample medication names."""
    return [
        "Metformin",
        "Lisinopril",
        "Atorvastatin",
        "Albuterol",
    ]


# Database fixtures (for integration tests)


@pytest.fixture(scope="module")
async def test_db_session():
    """Create test database session."""
    from research_platform.db.session import get_session

    async with get_session() as session:
        yield session


# Evaluation fixtures


@pytest.fixture
def medical_evaluators():
    """Standard medical evaluators."""
    from research_platform.evaluation.evaluators.medical_evaluators import (
        PHILeakageEvaluator,
        MedicalAccuracyEvaluator,
        ResponseCompletenessEvaluator,
        CostBudgetEvaluator,
        LatencyEvaluator,
    )

    return [
        PHILeakageEvaluator(),
        MedicalAccuracyEvaluator(),
        ResponseCompletenessEvaluator(min_answer_length=50),
        CostBudgetEvaluator(max_cost=0.05),
        LatencyEvaluator(max_latency_ms=3000),
    ]


@pytest.fixture
def research_evaluators():
    """Standard research evaluators."""
    from research_platform.evaluation.evaluators.medical_evaluators import (
        ResponseCompletenessEvaluator,
        CostBudgetEvaluator,
        LatencyEvaluator,
        ResearchCitationEvaluator,
    )

    return [
        ResearchCitationEvaluator(),
        ResponseCompletenessEvaluator(min_answer_length=100),
        CostBudgetEvaluator(max_cost=0.10),  # Research queries may cost more
        LatencyEvaluator(max_latency_ms=5000),
    ]
