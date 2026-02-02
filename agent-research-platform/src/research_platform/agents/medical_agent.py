"""Medical Records Agent for querying patient data.

IMPORTANT: This is a demonstration/research platform.
For production medical systems, ensure full HIPAA compliance.
"""

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from research_platform.agents.tools.medical import (
    MedicalDeps,
    find_patient,
    get_patient_diagnoses,
    get_patient_medications,
    get_lab_results,
    search_patients_by_diagnosis,
    get_encounter_summary,
)
from research_platform.config import settings


# Response models


class MedicalQueryResponse(BaseModel):
    """Structured response from medical agent."""

    answer: str
    sources: list[str]  # MRNs or data types accessed
    confidence: float  # 0-1
    phi_accessed: bool  # Was PHI accessed?


# Agent definition

medical_agent = Agent(
    settings.default_model,
    deps_type=MedicalDeps,
    result_type=MedicalQueryResponse,
    system_prompt="""You are a HIPAA-compliant medical records assistant.

Your role is to help healthcare providers access and understand patient medical records.

IMPORTANT GUIDELINES:
1. Always verify patient identity using MRN (Medical Record Number)
2. Only access patient data for the authenticated institution
3. All data access is logged for compliance
4. Provide accurate, clinically relevant information
5. Use medical terminology appropriately
6. Cite your sources (which data you accessed)
7. Flag if PHI (Protected Health Information) was accessed

Available data:
- Patient demographics (age, gender, blood type)
- Diagnoses with ICD-10 codes
- Medications (active and historical)
- Lab results
- Encounter summaries

PRIVACY:
- Never share PHI outside proper context
- Always log which patient data was accessed
- Use MRN for patient identification, not names

When answering:
1. Use the appropriate tools to gather information
2. Provide clinically relevant summaries
3. Include ICD-10 codes when discussing diagnoses
4. Note any abnormal lab values
5. Highlight active medications and potential interactions
6. Set confidence based on data completeness
""",
)


# Register tools


@medical_agent.tool
async def find_patient_tool(
    ctx: RunContext[MedicalDeps],
    mrn: str,
):
    """Find patient by MRN."""
    return await find_patient(ctx, mrn)


@medical_agent.tool
async def get_diagnoses_tool(
    ctx: RunContext[MedicalDeps],
    mrn: str,
    active_only: bool = False,
):
    """Get patient diagnoses."""
    return await get_patient_diagnoses(ctx, mrn, active_only)


@medical_agent.tool
async def get_medications_tool(
    ctx: RunContext[MedicalDeps],
    mrn: str,
    active_only: bool = True,
):
    """Get patient medications."""
    return await get_patient_medications(ctx, mrn, active_only)


@medical_agent.tool
async def get_labs_tool(
    ctx: RunContext[MedicalDeps],
    mrn: str,
    test_name: str | None = None,
    days: int = 30,
):
    """Get patient lab results."""
    return await get_lab_results(ctx, mrn, test_name, days)


@medical_agent.tool
async def search_by_diagnosis_tool(
    ctx: RunContext[MedicalDeps],
    icd10_code: str,
    limit: int = 10,
):
    """Search patients by diagnosis (ICD-10 code)."""
    return await search_patients_by_diagnosis(ctx, icd10_code, limit)


@medical_agent.tool
async def get_encounters_tool(
    ctx: RunContext[MedicalDeps],
    mrn: str,
    limit: int = 5,
):
    """Get patient encounter history."""
    return await get_encounter_summary(ctx, mrn, limit)


# Validators


@medical_agent.result_validator
async def validate_medical_response(
    ctx: RunContext[MedicalDeps], result: MedicalQueryResponse
) -> MedicalQueryResponse:
    """Validate medical query responses."""

    # Ensure confidence is in valid range
    if not (0 <= result.confidence <= 1):
        result.confidence = max(0, min(1, result.confidence))

    # Ensure answer is not empty
    if not result.answer.strip():
        from pydantic_ai import ModelRetry

        raise ModelRetry("Answer cannot be empty. Please provide a meaningful response.")

    return result
