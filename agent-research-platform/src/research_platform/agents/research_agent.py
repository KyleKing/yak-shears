"""Biomedical Research Agent for querying research data."""

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from research_platform.agents.tools.research import (
    ResearchDeps,
    find_publications_by_author,
    get_research_projects,
    get_trial_enrollment_stats,
    search_clinical_trials,
    search_publications,
    search_research_projects,
)
from research_platform.config import settings

# Response models


class ResearchQueryResponse(BaseModel):
    """Structured response from research agent."""

    answer: str
    references: list[dict]  # Publications, trials, or projects referenced
    research_areas: list[str]  # Relevant research areas
    confidence: float  # 0-1


# Agent definition

research_agent = Agent(
    settings.default_model,
    deps_type=ResearchDeps,
    result_type=ResearchQueryResponse,
    system_prompt="""You are a biomedical research assistant.

Your role is to help researchers find and understand biomedical research, including:
- Scientific publications
- Clinical trials
- Research projects

CAPABILITIES:
1. Semantic search across publications (titles and abstracts)
2. Clinical trial search with filters (phase, status, conditions)
3. Author-based publication search
4. Research project discovery
5. Trial enrollment statistics

GUIDELINES:
1. Use semantic search for natural language queries
2. Provide accurate bibliographic information
3. Cite DOIs and PubMed IDs when available
4. Explain research findings in context
5. Note clinical trial phases and statuses
6. Highlight relevant research areas

When answering:
1. Search for relevant publications, trials, or projects
2. Synthesize findings into coherent summary
3. Include proper citations in references
4. Note key research areas involved
5. Set confidence based on search results quality

For literature reviews:
- Use semantic search to find relevant papers
- Summarize key findings
- Note citation counts for impact
- Group by research area if applicable

For clinical trial queries:
- Filter by phase and status
- Explain enrollment criteria and status
- Note study locations if relevant
- Highlight conditions being studied
""",
)


# Register tools


@research_agent.tool
async def search_publications_tool(
    ctx: RunContext[ResearchDeps],
    query: str,
    research_area: str | None = None,
    limit: int = 5,
):
    """Search biomedical publications."""
    return await search_publications(ctx, query, research_area, limit)


@research_agent.tool
async def search_trials_tool(
    ctx: RunContext[ResearchDeps],
    query: str,
    status: str | None = None,
    phase: str | None = None,
    limit: int = 5,
):
    """Search clinical trials."""
    return await search_clinical_trials(ctx, query, status, phase, limit)


@research_agent.tool
async def find_author_pubs_tool(
    ctx: RunContext[ResearchDeps],
    author_name: str,
    limit: int = 10,
):
    """Find publications by author."""
    return await find_publications_by_author(ctx, author_name, limit)


@research_agent.tool
async def get_projects_tool(
    ctx: RunContext[ResearchDeps],
    research_area: str | None = None,
    status: str | None = None,
    limit: int = 10,
):
    """Get research projects."""
    return await get_research_projects(ctx, research_area, status, limit)


@research_agent.tool
async def search_projects_tool(
    ctx: RunContext[ResearchDeps],
    query: str,
    limit: int = 5,
):
    """Search research projects."""
    return await search_research_projects(ctx, query, limit)


@research_agent.tool
async def trial_stats_tool(
    ctx: RunContext[ResearchDeps],
    research_area: str | None = None,
):
    """Get trial enrollment statistics."""
    return await get_trial_enrollment_stats(ctx, research_area)


# Validators


@research_agent.result_validator
async def validate_research_response(
    ctx: RunContext[ResearchDeps], result: ResearchQueryResponse
) -> ResearchQueryResponse:
    """Validate research query responses."""
    # Ensure confidence is valid
    if not (0 <= result.confidence <= 1):
        result.confidence = max(0, min(1, result.confidence))

    # Ensure answer exists
    if not result.answer.strip():
        from pydantic_ai import ModelRetry

        raise ModelRetry("Answer cannot be empty. Please provide a meaningful response.")

    return result
