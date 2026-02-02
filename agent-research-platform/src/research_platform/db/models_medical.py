"""SQLAlchemy models for medical records and biomedical research platform.

IMPORTANT: This is a demonstration/research platform.
For production medical systems, ensure full HIPAA compliance,
proper security audits, and regulatory approval.
"""

from datetime import datetime, date
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Institution(Base):
    """Healthcare institution or research organization (tenant)."""

    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # hospital, clinic, research_lab, university
    hipaa_certified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    staff: Mapped[list["Staff"]] = relationship(back_populates="institution")
    patients: Mapped[list["Patient"]] = relationship(back_populates="institution")
    research_projects: Mapped[list["ResearchProject"]] = relationship(back_populates="institution")
    publications: Mapped[list["Publication"]] = relationship(back_populates="institution")


class Staff(Base):
    """Healthcare staff or researchers."""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(50), index=True
    )  # physician, nurse, researcher, admin
    specialization: Mapped[Optional[str]] = mapped_column(String(255))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="staff")


class Patient(Base):
    """Patient records (PHI - Protected Health Information)."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)

    # Identifiers
    mrn: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # Medical Record Number

    # Demographics (PHI)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(20))  # male, female, other, unknown

    # Contact (PHI)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    # Clinical
    blood_type: Mapped[Optional[str]] = mapped_column(String(10))
    allergies: Mapped[Optional[dict]] = mapped_column(JSONB)  # List of allergies

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="patients")
    encounters: Mapped[list["Encounter"]] = relationship(back_populates="patient")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="patient")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient")
    lab_results: Mapped[list["LabResult"]] = relationship(back_populates="patient")


class Encounter(Base):
    """Patient encounter (visit, admission, etc.)."""

    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)

    encounter_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # outpatient, inpatient, emergency, telemedicine
    admission_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    discharge_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="active", index=True
    )  # active, completed, cancelled

    # Vector embedding for semantic search on notes
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="encounters")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="encounter")

    __table_args__ = (
        Index(
            "idx_encounter_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Diagnosis(Base):
    """Patient diagnosis with ICD-10 coding."""

    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("encounters.id"), index=True, nullable=True
    )

    # ICD-10 coding
    icd10_code: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(String(500))
    diagnosis_type: Mapped[str] = mapped_column(
        String(50)
    )  # primary, secondary, differential

    # Clinical details
    onset_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50))  # active, resolved, chronic
    notes: Mapped[Optional[str]] = mapped_column(Text)

    diagnosed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="diagnoses")
    encounter: Mapped[Optional["Encounter"]] = relationship(back_populates="diagnoses")


class Medication(Base):
    """Patient medications."""

    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)

    # Drug information
    drug_name: Mapped[str] = mapped_column(String(255), index=True)
    generic_name: Mapped[Optional[str]] = mapped_column(String(255))
    dosage: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100))
    route: Mapped[str] = mapped_column(String(50))  # oral, IV, topical, etc.

    # Prescription details
    prescribed_by: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(50), index=True
    )  # active, completed, discontinued

    # Additional info
    indication: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="medications")


class LabResult(Base):
    """Laboratory test results."""

    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)

    # Test information
    test_name: Mapped[str] = mapped_column(String(255), index=True)
    test_code: Mapped[Optional[str]] = mapped_column(String(50))  # LOINC code
    category: Mapped[str] = mapped_column(
        String(100), index=True
    )  # hematology, chemistry, microbiology, etc.

    # Results
    result_value: Mapped[str] = mapped_column(String(255))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    reference_range: Mapped[Optional[str]] = mapped_column(String(100))
    abnormal_flag: Mapped[Optional[str]] = mapped_column(String(20))  # H, L, normal

    # Metadata
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resulted_at: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="lab_results")


# Biomedical Research Models


class ResearchProject(Base):
    """Biomedical research project."""

    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    research_area: Mapped[str] = mapped_column(
        String(100), index=True
    )  # oncology, cardiology, neurology, etc.
    status: Mapped[str] = mapped_column(
        String(50), index=True
    )  # planning, active, completed, published

    # Funding
    funding_source: Mapped[Optional[str]] = mapped_column(String(255))
    budget: Mapped[Optional[float]] = mapped_column(Float)

    # Timeline
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)

    # Principal Investigator
    pi_name: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Vector embedding for semantic search
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="research_projects")
    clinical_trials: Mapped[list["ClinicalTrial"]] = relationship(
        back_populates="research_project"
    )

    __table_args__ = (
        Index(
            "idx_research_project_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ClinicalTrial(Base):
    """Clinical trial information."""

    __tablename__ = "clinical_trials"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    research_project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("research_projects.id"), index=True, nullable=True
    )

    # Trial identifiers
    nct_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True
    )  # ClinicalTrials.gov ID
    title: Mapped[str] = mapped_column(String(500))
    brief_summary: Mapped[str] = mapped_column(Text)

    # Trial details
    phase: Mapped[str] = mapped_column(String(50))  # Phase I, II, III, IV
    status: Mapped[str] = mapped_column(
        String(50), index=True
    )  # recruiting, active, completed, terminated
    intervention_type: Mapped[str] = mapped_column(String(100))  # drug, device, behavioral, etc.

    # Enrollment
    target_enrollment: Mapped[Optional[int]] = mapped_column(Integer)
    current_enrollment: Mapped[int] = mapped_column(Integer, default=0)

    # Conditions studied
    conditions: Mapped[dict] = mapped_column(JSONB)  # List of conditions

    # Timeline
    start_date: Mapped[date] = mapped_column(Date)
    completion_date: Mapped[Optional[date]] = mapped_column(Date)

    # Locations
    study_locations: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Vector embedding
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    research_project: Mapped[Optional["ResearchProject"]] = relationship(
        back_populates="clinical_trials"
    )

    __table_args__ = (
        Index(
            "idx_clinical_trial_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Publication(Base):
    """Biomedical research publications."""

    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(PGUUID, default=uuid4, unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)

    # Publication identifiers
    pubmed_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)

    # Publication details
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)
    authors: Mapped[dict] = mapped_column(JSONB)  # List of authors
    journal: Mapped[str] = mapped_column(String(255))
    publication_date: Mapped[date] = mapped_column(Date, index=True)

    # Classification
    keywords: Mapped[Optional[dict]] = mapped_column(JSONB)  # MeSH terms
    research_area: Mapped[str] = mapped_column(String(100), index=True)

    # Metrics
    citation_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Vector embedding for semantic search
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="publications")

    __table_args__ = (
        Index(
            "idx_publication_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# Audit and Compliance


class AuditLog(Base):
    """Audit log for HIPAA compliance and tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)

    # Who
    user_id: Mapped[Optional[int]] = mapped_column(Integer)  # Staff ID
    user_email: Mapped[str] = mapped_column(String(255))

    # What
    action: Mapped[str] = mapped_column(
        String(100), index=True
    )  # view, update, delete, export
    resource_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # patient, encounter, lab_result, etc.
    resource_id: Mapped[int] = mapped_column(Integer, index=True)

    # When
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    # Where (IP address, etc.)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    # Additional details
    details: Mapped[Optional[dict]] = mapped_column(JSONB)


# Keep experiment tracking models from original


class ExperimentRun(Base):
    """Track evaluation experiment runs."""

    __tablename__ = "experiment_runs"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
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
    token_usage: Mapped[dict] = mapped_column(JSONB)

    # Metadata
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    parent_run_id: Mapped[Optional[UUID]] = mapped_column(
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
    expected_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evaluator_results: Mapped[dict] = mapped_column(JSONB)

    # Tracing
    trace_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    experiment: Mapped["ExperimentRun"] = relationship(back_populates="case_results")
