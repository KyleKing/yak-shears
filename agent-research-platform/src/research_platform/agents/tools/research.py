"""Biomedical research tools for agents."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from research_platform.db.embeddings import EmbeddingService
from research_platform.db.models_medical import (
    ClinicalTrial,
    Publication,
    ResearchProject,
)

# Dependency types


@dataclass
class ResearchDeps:
    """Dependencies for research agents."""

    db: AsyncEngine
    embeddings: EmbeddingService
    institution_id: int
    user_email: str


# Response models


class PublicationInfo(BaseModel):
    """Publication information."""

    title: str
    authors: list[str]
    journal: str
    publication_date: str
    abstract: str
    pubmed_id: str | None
    doi: str | None
    citation_count: int


class ClinicalTrialInfo(BaseModel):
    """Clinical trial information."""

    title: str
    nct_id: str | None
    phase: str
    status: str
    brief_summary: str
    target_enrollment: int | None
    conditions: list[str]


class ResearchProjectInfo(BaseModel):
    """Research project information."""

    title: str
    research_area: str
    status: str
    pi_name: str
    description: str
    start_date: str


# Tools


async def search_publications(
    ctx: RunContext[ResearchDeps],
    query: Annotated[
        str, Field(description="Search query for publications (semantic search)")
    ],
    research_area: Annotated[
        str | None, Field(description="Filter by research area (optional)")
    ] = None,
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=20)] = 5,
) -> list[PublicationInfo]:
    """Search biomedical publications using semantic similarity.

    This tool performs vector similarity search across publication titles and abstracts
    to find relevant research papers.

    Args:
        query: Natural language search query
        research_area: Optional filter by research area
        limit: Maximum number of results

    Returns:
        List of relevant publications
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Generate query embedding
        query_embedding = await ctx.deps.embeddings.embed(query)

        # Build query
        stmt = (
            select(Publication)
            .where(Publication.institution_id == ctx.deps.institution_id)
            .order_by(Publication.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        if research_area:
            stmt = stmt.where(Publication.research_area == research_area)

        result = await session.execute(stmt)
        publications = result.scalars().all()

        return [
            PublicationInfo(
                title=pub.title,
                authors=pub.authors.get("authors", []) if pub.authors else [],
                journal=pub.journal,
                publication_date=pub.publication_date.isoformat(),
                abstract=pub.abstract[:500] + "..."
                if len(pub.abstract) > 500
                else pub.abstract,
                pubmed_id=pub.pubmed_id,
                doi=pub.doi,
                citation_count=pub.citation_count,
            )
            for pub in publications
        ]


async def search_clinical_trials(
    ctx: RunContext[ResearchDeps],
    query: Annotated[str, Field(description="Search query for clinical trials")],
    status: Annotated[
        str | None,
        Field(description="Filter by status: recruiting, active, completed, terminated"),
    ] = None,
    phase: Annotated[str | None, Field(description="Filter by phase: I, II, III, IV")] = None,
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=20)] = 5,
) -> list[ClinicalTrialInfo]:
    """Search clinical trials using semantic similarity.

    Args:
        query: Natural language search query
        status: Optional status filter
        phase: Optional phase filter
        limit: Maximum number of results

    Returns:
        List of relevant clinical trials
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Generate query embedding
        query_embedding = await ctx.deps.embeddings.embed(query)

        # Build query
        stmt = (
            select(ClinicalTrial)
            .where(ClinicalTrial.embedding.isnot(None))
            .order_by(ClinicalTrial.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        if status:
            stmt = stmt.where(ClinicalTrial.status == status)

        if phase:
            stmt = stmt.where(ClinicalTrial.phase == f"Phase {phase}")

        result = await session.execute(stmt)
        trials = result.scalars().all()

        return [
            ClinicalTrialInfo(
                title=trial.title,
                nct_id=trial.nct_id,
                phase=trial.phase,
                status=trial.status,
                brief_summary=trial.brief_summary[:300] + "..."
                if len(trial.brief_summary) > 300
                else trial.brief_summary,
                target_enrollment=trial.target_enrollment,
                conditions=trial.conditions.get("conditions", []) if trial.conditions else [],
            )
            for trial in trials
        ]


async def find_publications_by_author(
    ctx: RunContext[ResearchDeps],
    author_name: Annotated[str, Field(description="Author name to search for")],
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=50)] = 10,
) -> list[PublicationInfo]:
    """Find publications by author name.

    Args:
        author_name: Name of the author
        limit: Maximum number of results

    Returns:
        List of publications by the author
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Query publications where author name appears in authors JSONB
        # This is a simplified search - production would use full-text search
        stmt = (
            select(Publication)
            .where(Publication.institution_id == ctx.deps.institution_id)
            .where(Publication.authors.op("@>")(f'["{author_name}"]'))
            .order_by(Publication.publication_date.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        publications = result.scalars().all()

        return [
            PublicationInfo(
                title=pub.title,
                authors=pub.authors.get("authors", []) if pub.authors else [],
                journal=pub.journal,
                publication_date=pub.publication_date.isoformat(),
                abstract=pub.abstract[:500] + "..."
                if len(pub.abstract) > 500
                else pub.abstract,
                pubmed_id=pub.pubmed_id,
                doi=pub.doi,
                citation_count=pub.citation_count,
            )
            for pub in publications
        ]


async def get_research_projects(
    ctx: RunContext[ResearchDeps],
    research_area: Annotated[str | None, Field(description="Filter by research area")] = None,
    status: Annotated[
        str | None,
        Field(description="Filter by status: planning, active, completed, published"),
    ] = None,
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=50)] = 10,
) -> list[ResearchProjectInfo]:
    """Get research projects for the institution.

    Args:
        research_area: Optional research area filter
        status: Optional status filter
        limit: Maximum number of results

    Returns:
        List of research projects
    """
    async with AsyncSession(ctx.deps.db) as session:
        stmt = (
            select(ResearchProject)
            .where(ResearchProject.institution_id == ctx.deps.institution_id)
            .order_by(ResearchProject.start_date.desc())
            .limit(limit)
        )

        if research_area:
            stmt = stmt.where(ResearchProject.research_area == research_area)

        if status:
            stmt = stmt.where(ResearchProject.status == status)

        result = await session.execute(stmt)
        projects = result.scalars().all()

        return [
            ResearchProjectInfo(
                title=proj.title,
                research_area=proj.research_area,
                status=proj.status,
                pi_name=proj.pi_name,
                description=proj.description[:300] + "..."
                if len(proj.description) > 300
                else proj.description,
                start_date=proj.start_date.isoformat(),
            )
            for proj in projects
        ]


async def search_research_projects(
    ctx: RunContext[ResearchDeps],
    query: Annotated[str, Field(description="Search query for research projects")],
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=20)] = 5,
) -> list[ResearchProjectInfo]:
    """Search research projects using semantic similarity.

    Args:
        query: Natural language search query
        limit: Maximum number of results

    Returns:
        List of relevant research projects
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Generate query embedding
        query_embedding = await ctx.deps.embeddings.embed(query)

        # Build query
        stmt = (
            select(ResearchProject)
            .where(ResearchProject.institution_id == ctx.deps.institution_id)
            .where(ResearchProject.embedding.isnot(None))
            .order_by(ResearchProject.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        result = await session.execute(stmt)
        projects = result.scalars().all()

        return [
            ResearchProjectInfo(
                title=proj.title,
                research_area=proj.research_area,
                status=proj.status,
                pi_name=proj.pi_name,
                description=proj.description[:300] + "..."
                if len(proj.description) > 300
                else proj.description,
                start_date=proj.start_date.isoformat(),
            )
            for proj in projects
        ]


async def get_trial_enrollment_stats(
    ctx: RunContext[ResearchDeps],
    research_area: Annotated[
        str | None, Field(description="Filter by research area (optional)")
    ] = None,
) -> dict:
    """Get clinical trial enrollment statistics.

    Args:
        research_area: Optional research area filter

    Returns:
        Enrollment statistics
    """
    async with AsyncSession(ctx.deps.db) as session:
        stmt = select(ClinicalTrial)

        if research_area:
            # Join with research project if available
            stmt = stmt.join(
                ResearchProject,
                ClinicalTrial.research_project_id == ResearchProject.id,
                isouter=True,
            ).where(ResearchProject.research_area == research_area)

        result = await session.execute(stmt)
        trials = result.scalars().all()

        recruiting = sum(1 for t in trials if t.status == "recruiting")
        active = sum(1 for t in trials if t.status == "active")
        completed = sum(1 for t in trials if t.status == "completed")

        total_enrolled = sum(t.current_enrollment for t in trials)
        total_target = sum(t.target_enrollment for t in trials if t.target_enrollment)

        return {
            "total_trials": len(trials),
            "recruiting": recruiting,
            "active": active,
            "completed": completed,
            "total_enrolled": total_enrolled,
            "total_target": total_target,
            "enrollment_rate": (total_enrolled / total_target * 100) if total_target > 0 else 0,
        }
