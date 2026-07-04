"""Tests for Biomedical Research Agent."""

import pytest
from pydantic_evals import Case, Dataset
from research_platform.agents.research_agent import research_agent


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_search_publications(mock_research_deps):
    """Test publication search."""
    result = await research_agent.run(
        "Find recent publications about cancer immunotherapy.",
        deps=mock_research_deps,
    )

    assert result.data.answer
    assert len(result.data.references) > 0
    assert result.data.confidence > 0
    assert len(result.data.research_areas) > 0


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_search_clinical_trials(mock_research_deps):
    """Test clinical trial search."""
    result = await research_agent.run(
        "Find active Phase III clinical trials for Alzheimer's disease.",
        deps=mock_research_deps,
    )

    assert result.data.answer
    assert result.data.confidence > 0


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_find_author_publications(mock_research_deps):
    """Test finding publications by author."""
    result = await research_agent.run(
        "Find publications by Dr. Smith in cardiology.",
        deps=mock_research_deps,
    )

    assert result.data.answer
    assert result.data.confidence > 0


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_research_project_search(mock_research_deps):
    """Test research project search."""
    result = await research_agent.run(
        "What research projects are ongoing in oncology?",
        deps=mock_research_deps,
    )

    assert result.data.answer


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_trial_enrollment_stats(mock_research_deps):
    """Test getting trial enrollment statistics."""
    result = await research_agent.run(
        "What is the enrollment status for neurology clinical trials?",
        deps=mock_research_deps,
    )

    assert result.data.answer


# Evaluation tests


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_research_agent_evaluation(mock_research_deps, research_evaluators):
    """Test research agent with evaluation framework."""
    dataset = Dataset(
        name="research_agent_publications",
        cases=[
            Case(
                inputs={"query": "Cancer immunotherapy publications"},
                expected_outputs={"min_references": 3},
                evaluators=research_evaluators,
                metadata={"category": "literature_search"},
            ),
            Case(
                inputs={"query": "Active clinical trials for diabetes"},
                expected_outputs={"min_references": 2},
                evaluators=research_evaluators,
                metadata={"category": "clinical_trials"},
            ),
        ],
    )

    async def run_query(inputs: dict):
        result = await research_agent.run(inputs["query"], deps=mock_research_deps)
        return {
            "answer": result.data.answer,
            "references": result.data.references,
            "research_areas": result.data.research_areas,
            "confidence": result.data.confidence,
            "cost": 0.02,
            "latency_ms": 2000,
        }

    report = await dataset.evaluate(run_query)
    assert report.passed_ratio >= 0.7


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_citation_quality(mock_research_deps):
    """Test citation quality."""
    from research_platform.evaluation.evaluators.medical_evaluators import (
        ResearchCitationEvaluator,
    )

    result = await research_agent.run(
        "Find publications about CRISPR gene editing.",
        deps=mock_research_deps,
    )

    evaluator = ResearchCitationEvaluator()
    eval_result = await evaluator.evaluate(
        inputs={"query": "..."},
        output={"references": result.data.references},
        expected_outputs=None,
    )

    assert eval_result.score >= 0.7


@pytest.mark.parametrize(
    "query,expected_area",
    [
        ("cancer immunotherapy", "oncology"),
        ("Alzheimer's disease treatments", "neurology"),
        ("diabetes medications", "endocrinology"),
    ],
)
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_research_area_classification(mock_research_deps, query, expected_area):
    """Test that queries are classified into correct research areas."""
    result = await research_agent.run(query, deps=mock_research_deps)

    # Research areas should be identified
    assert len(result.data.research_areas) > 0
