"""SQLAlchemy models for B2B SaaS platform with pgvector support."""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""


class Organization(Base):
    """Tenant organization in multi-tenant B2B system."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="free")  # free, pro, enterprise
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization")
    products: Mapped[list["Product"]] = relationship(back_populates="organization")
    customers: Mapped[list["Customer"]] = relationship(back_populates="organization")
    documents: Mapped[list["Document"]] = relationship(back_populates="organization")


class User(Base):
    """User within an organization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="member")  # admin, member, viewer
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")


class Product(Base):
    """Product in organization's catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[float] = mapped_column(Float)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Vector embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )  # Dimension depends on embedding model

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")

    __table_args__ = (
        Index(
            "idx_product_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Customer(Base):
    """Organization's customer (their client)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(50), default="standard")  # standard, premium, vip
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="customers")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    support_tickets: Mapped[list["SupportTicket"]] = relationship(back_populates="customer")


class Order(Base):
    """Customer order."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )  # pending, processing, shipped, delivered, cancelled
    total_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    """Line item in an order."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    total_price: Mapped[float] = mapped_column(Float)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")


class SupportTicket(Base):
    """Customer support ticket."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(50), default="open", index=True
    )  # open, in_progress, resolved, closed
    priority: Mapped[str] = mapped_column(
        String(50), default="medium", index=True
    )  # low, medium, high, urgent
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Vector embedding for semantic search on subject+first message
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="support_tickets")
    messages: Mapped[list["TicketMessage"]] = relationship(back_populates="ticket")

    __table_args__ = (
        Index(
            "idx_ticket_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class TicketMessage(Base):
    """Message in a support ticket thread."""

    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(50))  # customer, agent, system
    sender_name: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages")


class Document(Base):
    """Document with vector embeddings for RAG."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # article, faq, manual, policy
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Vector embedding for semantic search
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="documents")

    __table_args__ = (
        Index(
            "idx_document_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# Experiment tracking models for evaluation


class ExperimentRun(Base):
    """Track evaluation experiment runs."""

    __tablename__ = "experiment_runs"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    agent_version: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    dataset_version: Mapped[str] = mapped_column(String(50))
    evaluator_version: Mapped[str] = mapped_column(String(50))

    # Results summary
    passed_ratio: Mapped[float] = mapped_column(Float)
    avg_score: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    avg_latency: Mapped[float] = mapped_column(Float)
    token_usage: Mapped[dict] = mapped_column(JSONB)  # {input: X, output: Y, total: Z}

    # Metadata
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="completed")  # running, completed, failed
    parent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID, ForeignKey("experiment_runs.id"), nullable=True
    )

    # Relationships
    case_results: Mapped[list["CaseResult"]] = relationship(back_populates="experiment")


class CaseResult(Base):
    """Individual evaluation case result."""

    __tablename__ = "case_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(255), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)

    # Metrics
    cost: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    tokens_input: Mapped[int] = mapped_column(Integer)
    tokens_output: Mapped[int] = mapped_column(Integer)
    tool_calls: Mapped[int] = mapped_column(Integer)
    retries: Mapped[int] = mapped_column(Integer)

    # Data
    inputs: Mapped[dict] = mapped_column(JSONB)
    output: Mapped[dict] = mapped_column(JSONB)
    expected_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evaluator_results: Mapped[dict] = mapped_column(JSONB)  # Results from each evaluator

    # Tracing
    trace_id: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    experiment: Mapped["ExperimentRun"] = relationship(back_populates="case_results")
