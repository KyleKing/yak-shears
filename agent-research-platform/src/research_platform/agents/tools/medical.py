"""Medical record tools for agents.

IMPORTANT: This is a demonstration/research platform.
For production medical systems, ensure full HIPAA compliance.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from research_platform.db.models_medical import (
    Patient,
    Encounter,
    Diagnosis,
    Medication,
    LabResult,
    AuditLog,
)


# Dependency types


@dataclass
class MedicalDeps:
    """Dependencies for medical agents."""

    db: AsyncEngine
    institution_id: int  # Tenant isolation
    user_email: str  # For audit logging
    user_id: int


# Response models


class PatientInfo(BaseModel):
    """Patient information (de-identified where possible)."""

    mrn: str
    age: int
    gender: str
    blood_type: str | None


class DiagnosisInfo(BaseModel):
    """Diagnosis information."""

    icd10_code: str
    description: str
    diagnosis_type: str
    status: str
    onset_date: str | None


class MedicationInfo(BaseModel):
    """Medication information."""

    drug_name: str
    dosage: str
    frequency: str
    status: str
    start_date: str


class LabResultInfo(BaseModel):
    """Lab result information."""

    test_name: str
    result_value: str
    unit: str | None
    reference_range: str | None
    abnormal_flag: str | None
    collected_at: str


# Tools


async def find_patient(
    ctx: RunContext[MedicalDeps],
    mrn: Annotated[str, Field(description="Patient Medical Record Number")],
) -> PatientInfo | None:
    """Find patient by MRN.

    This tool retrieves basic patient information for the authenticated institution.
    All accesses are logged for HIPAA compliance.

    Args:
        mrn: Medical Record Number

    Returns:
        Patient info or None if not found
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Query with tenant filtering
        stmt = select(Patient).where(
            and_(Patient.mrn == mrn, Patient.institution_id == ctx.deps.institution_id)
        )

        result = await session.execute(stmt)
        patient = result.scalar_one_or_none()

        if not patient:
            return None

        # Log access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "view",
            "patient",
            patient.id,
        )

        # Calculate age (de-identified)
        today = datetime.now().date()
        age = (
            today.year
            - patient.date_of_birth.year
            - (
                (today.month, today.day)
                < (patient.date_of_birth.month, patient.date_of_birth.day)
            )
        )

        return PatientInfo(
            mrn=patient.mrn,
            age=age,
            gender=patient.gender,
            blood_type=patient.blood_type,
        )


async def get_patient_diagnoses(
    ctx: RunContext[MedicalDeps],
    mrn: Annotated[str, Field(description="Patient Medical Record Number")],
    active_only: Annotated[bool, Field(description="Only return active diagnoses")] = False,
) -> list[DiagnosisInfo]:
    """Get patient diagnoses.

    Args:
        mrn: Medical Record Number
        active_only: If True, only return active diagnoses

    Returns:
        List of diagnoses
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Find patient
        patient_stmt = select(Patient).where(
            and_(Patient.mrn == mrn, Patient.institution_id == ctx.deps.institution_id)
        )
        result = await session.execute(patient_stmt)
        patient = result.scalar_one_or_none()

        if not patient:
            return []

        # Query diagnoses
        diag_stmt = select(Diagnosis).where(Diagnosis.patient_id == patient.id)

        if active_only:
            diag_stmt = diag_stmt.where(Diagnosis.status == "active")

        result = await session.execute(diag_stmt.order_by(Diagnosis.diagnosed_at.desc()))
        diagnoses = result.scalars().all()

        # Log access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "view",
            "diagnosis",
            patient.id,
            details={"count": len(diagnoses), "active_only": active_only},
        )

        return [
            DiagnosisInfo(
                icd10_code=d.icd10_code,
                description=d.description,
                diagnosis_type=d.diagnosis_type,
                status=d.status,
                onset_date=d.onset_date.isoformat() if d.onset_date else None,
            )
            for d in diagnoses
        ]


async def get_patient_medications(
    ctx: RunContext[MedicalDeps],
    mrn: Annotated[str, Field(description="Patient Medical Record Number")],
    active_only: Annotated[bool, Field(description="Only return active medications")] = True,
) -> list[MedicationInfo]:
    """Get patient medications.

    Args:
        mrn: Medical Record Number
        active_only: If True, only return active medications

    Returns:
        List of medications
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Find patient
        patient_stmt = select(Patient).where(
            and_(Patient.mrn == mrn, Patient.institution_id == ctx.deps.institution_id)
        )
        result = await session.execute(patient_stmt)
        patient = result.scalar_one_or_none()

        if not patient:
            return []

        # Query medications
        med_stmt = select(Medication).where(Medication.patient_id == patient.id)

        if active_only:
            med_stmt = med_stmt.where(Medication.status == "active")

        result = await session.execute(med_stmt.order_by(Medication.start_date.desc()))
        medications = result.scalars().all()

        # Log access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "view",
            "medication",
            patient.id,
        )

        return [
            MedicationInfo(
                drug_name=m.drug_name,
                dosage=m.dosage,
                frequency=m.frequency,
                status=m.status,
                start_date=m.start_date.isoformat(),
            )
            for m in medications
        ]


async def get_lab_results(
    ctx: RunContext[MedicalDeps],
    mrn: Annotated[str, Field(description="Patient Medical Record Number")],
    test_name: Annotated[
        str | None, Field(description="Filter by test name (optional)")
    ] = None,
    days: Annotated[int, Field(description="Number of days to look back", ge=1, le=365)] = 30,
) -> list[LabResultInfo]:
    """Get patient lab results.

    Args:
        mrn: Medical Record Number
        test_name: Optional test name filter
        days: Number of days to look back (default 30)

    Returns:
        List of lab results
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Find patient
        patient_stmt = select(Patient).where(
            and_(Patient.mrn == mrn, Patient.institution_id == ctx.deps.institution_id)
        )
        result = await session.execute(patient_stmt)
        patient = result.scalar_one_or_none()

        if not patient:
            return []

        # Query lab results
        cutoff_date = datetime.now() - timedelta(days=days)

        lab_stmt = (
            select(LabResult)
            .where(LabResult.patient_id == patient.id)
            .where(LabResult.collected_at >= cutoff_date)
        )

        if test_name:
            lab_stmt = lab_stmt.where(LabResult.test_name.ilike(f"%{test_name}%"))

        result = await session.execute(lab_stmt.order_by(LabResult.collected_at.desc()))
        lab_results = result.scalars().all()

        # Log access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "view",
            "lab_result",
            patient.id,
        )

        return [
            LabResultInfo(
                test_name=lr.test_name,
                result_value=lr.result_value,
                unit=lr.unit,
                reference_range=lr.reference_range,
                abnormal_flag=lr.abnormal_flag,
                collected_at=lr.collected_at.isoformat(),
            )
            for lr in lab_results
        ]


async def search_patients_by_diagnosis(
    ctx: RunContext[MedicalDeps],
    icd10_code: Annotated[
        str, Field(description="ICD-10 code (can be partial, e.g., 'E11' for diabetes)")
    ],
    limit: Annotated[int, Field(description="Maximum results", ge=1, le=100)] = 10,
) -> list[dict]:
    """Search for patients with a specific diagnosis.

    Args:
        icd10_code: ICD-10 code or prefix
        limit: Maximum number of results

    Returns:
        List of patients with the diagnosis
    """
    async with AsyncSession(ctx.deps.db) as session:
        stmt = (
            select(Patient, Diagnosis)
            .join(Diagnosis)
            .where(Patient.institution_id == ctx.deps.institution_id)
            .where(Diagnosis.icd10_code.startswith(icd10_code))
            .where(Diagnosis.status == "active")
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.all()

        # Log bulk access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "search",
            "patient",
            0,
            details={"icd10_code": icd10_code, "count": len(rows)},
        )

        return [
            {
                "mrn": patient.mrn,
                "age": _calculate_age(patient.date_of_birth),
                "gender": patient.gender,
                "diagnosis": diagnosis.description,
                "icd10": diagnosis.icd10_code,
            }
            for patient, diagnosis in rows
        ]


async def get_encounter_summary(
    ctx: RunContext[MedicalDeps],
    mrn: Annotated[str, Field(description="Patient Medical Record Number")],
    limit: Annotated[int, Field(description="Number of recent encounters", ge=1, le=50)] = 5,
) -> list[dict]:
    """Get recent patient encounters.

    Args:
        mrn: Medical Record Number
        limit: Number of recent encounters to retrieve

    Returns:
        List of encounter summaries
    """
    async with AsyncSession(ctx.deps.db) as session:
        # Find patient
        patient_stmt = select(Patient).where(
            and_(Patient.mrn == mrn, Patient.institution_id == ctx.deps.institution_id)
        )
        result = await session.execute(patient_stmt)
        patient = result.scalar_one_or_none()

        if not patient:
            return []

        # Query encounters
        enc_stmt = (
            select(Encounter)
            .where(Encounter.patient_id == patient.id)
            .order_by(Encounter.admission_date.desc())
            .limit(limit)
        )

        result = await session.execute(enc_stmt)
        encounters = result.scalars().all()

        # Log access
        await _log_audit(
            session,
            ctx.deps.institution_id,
            ctx.deps.user_id,
            ctx.deps.user_email,
            "view",
            "encounter",
            patient.id,
        )

        return [
            {
                "encounter_type": enc.encounter_type,
                "admission_date": enc.admission_date.isoformat(),
                "discharge_date": enc.discharge_date.isoformat() if enc.discharge_date else None,
                "chief_complaint": enc.chief_complaint,
                "status": enc.status,
            }
            for enc in encounters
        ]


# Utility functions


async def _log_audit(
    session: AsyncSession,
    institution_id: int,
    user_id: int,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: int,
    details: dict | None = None,
):
    """Log access for HIPAA compliance."""
    log_entry = AuditLog(
        institution_id=institution_id,
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(log_entry)
    await session.commit()


def _calculate_age(date_of_birth: datetime.date) -> int:
    """Calculate age from date of birth."""
    today = datetime.now().date()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )
