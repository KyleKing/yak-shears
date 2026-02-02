"""Embedding generation and vector search utilities."""

from typing import Optional

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from research_platform.config import settings
from research_platform.db.models import Document, Product, SupportTicket


class EmbeddingService:
    """Service for generating embeddings and performing vector search."""

    def __init__(
        self,
        model: str = settings.embedding_model,
        dimensions: int = settings.embedding_dimensions,
    ):
        self.model = model
        self.dimensions = dimensions
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set for embedding generation")
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        client = self._get_client()

        # Extract model name (remove provider prefix)
        model_name = self.model.split(":")[-1]

        response = await client.embeddings.create(input=text, model=model_name)

        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        client = self._get_client()
        model_name = self.model.split(":")[-1]

        response = await client.embeddings.create(input=texts, model=model_name)

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    async def search_documents(
        self,
        session: AsyncSession,
        query: str,
        organization_id: int,
        limit: int = 5,
        min_score: float = 0.7,
    ) -> list[Document]:
        """Semantic search for documents using vector similarity.

        Args:
            session: Database session
            query: Search query
            organization_id: Organization ID for tenant filtering
            limit: Maximum number of results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of matching documents ordered by relevance
        """
        # Generate query embedding
        query_embedding = await self.embed(query)

        # Vector similarity search with cosine distance
        # pgvector: 0 = identical, 2 = opposite
        # Convert to similarity score: 1 - (distance / 2)
        stmt = (
            select(Document)
            .filter(Document.organization_id == organization_id)
            .order_by(Document.embedding.cosine_distance(query_embedding))
            .limit(limit * 2)  # Get more to filter by score
        )

        result = await session.execute(stmt)
        documents = list(result.scalars().all())

        # Filter by minimum score
        # Calculate similarity: 1 - (cosine_distance / 2)
        filtered = []
        for doc in documents:
            if doc.embedding:
                # Approximate similarity score
                distance = self._cosine_distance(query_embedding, doc.embedding)
                similarity = 1 - (distance / 2)

                if similarity >= min_score:
                    filtered.append(doc)

            if len(filtered) >= limit:
                break

        return filtered

    async def search_products(
        self,
        session: AsyncSession,
        query: str,
        organization_id: int,
        limit: int = 5,
    ) -> list[Product]:
        """Semantic search for products.

        Args:
            session: Database session
            query: Search query
            organization_id: Organization ID for tenant filtering
            limit: Maximum number of results

        Returns:
            List of matching products ordered by relevance
        """
        query_embedding = await self.embed(query)

        stmt = (
            select(Product)
            .filter(Product.organization_id == organization_id)
            .filter(Product.is_active == True)
            .filter(Product.embedding.isnot(None))
            .order_by(Product.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search_tickets(
        self,
        session: AsyncSession,
        query: str,
        organization_id: int,
        limit: int = 5,
    ) -> list[SupportTicket]:
        """Semantic search for support tickets.

        Args:
            session: Database session
            query: Search query
            organization_id: Organization ID for tenant filtering
            limit: Maximum number of results

        Returns:
            List of matching tickets ordered by relevance
        """
        query_embedding = await self.embed(query)

        # Join to customer to filter by organization
        stmt = (
            select(SupportTicket)
            .join(SupportTicket.customer)
            .filter(SupportTicket.embedding.isnot(None))
            .filter(SupportTicket.customer.has(organization_id=organization_id))
            .order_by(SupportTicket.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _cosine_distance(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine distance between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine distance (0 = identical, 2 = opposite)
        """
        import math

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        # Cosine similarity
        similarity = dot_product / (mag1 * mag2)

        # Convert to distance
        return 1 - similarity
