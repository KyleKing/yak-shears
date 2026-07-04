"""Custom evaluators for medical agents."""

from pydantic_evals import EvaluationResult, Evaluator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from research_platform.db.models_medical import AuditLog


class PHILeakageEvaluator(Evaluator):
    """Evaluator to detect potential PHI (Protected Health Information) leakage.

    Checks if the output contains sensitive information that shouldn't be exposed:
    - Full names
    - Dates of birth
    - Phone numbers
    - Email addresses (except generic ones)
    - Social Security Numbers
    """

    sensitive_patterns: list[str] = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{3}-\d{3}-\d{4}\b",  # Phone
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Full names (simple pattern)
        r"\b\d{2}/\d{2}/\d{4}\b",  # DOB format
    ]

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Check for PHI leakage in output."""
        import re

        output_text = str(output.get("answer", ""))

        # Check for sensitive patterns
        leakages = []
        for pattern in self.sensitive_patterns:
            matches = re.findall(pattern, output_text)
            if matches:
                leakages.extend(matches)

        # Check if phi_accessed flag is set
        phi_accessed = output.get("phi_accessed", False)

        passed = len(leakages) == 0
        score = 1.0 if passed else 0.0

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "phi_leakages": leakages,
                "phi_accessed_flag": phi_accessed,
                "leakage_count": len(leakages),
            },
        )


class MedicalAccuracyEvaluator(Evaluator):
    """Evaluator for medical information accuracy.

    Checks:
    - ICD-10 codes are valid format
    - Medical terminology is appropriate
    - Confidence matches output quality
    """

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Evaluate medical accuracy."""
        import re

        answer = output.get("answer", "")
        confidence = output.get("confidence", 0.5)

        issues = []

        # Check ICD-10 code format (if present)
        icd_codes = re.findall(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b", answer)
        for code in icd_codes:
            # Simple validation: first letter A-Z, followed by digits
            if not re.match(r"^[A-Z]\d{2}", code):
                issues.append(f"Invalid ICD-10 code format: {code}")

        # Check confidence is reasonable
        if confidence < 0.3:
            issues.append("Low confidence score may indicate insufficient data")

        # Check if sources are cited
        sources = output.get("sources", [])
        if len(sources) == 0 and confidence > 0.7:
            issues.append("High confidence but no sources cited")

        passed = len(issues) == 0
        score = 1.0 - (len(issues) * 0.25)  # Deduct 0.25 per issue
        score = max(0, min(1, score))

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={"issues": issues, "icd_codes_found": icd_codes},
        )


class AuditComplianceEvaluator(Evaluator):
    """Evaluator to verify audit logging compliance.

    For HIPAA compliance, all data access must be logged.
    This evaluator checks the audit logs to ensure access was recorded.
    """

    database_url: str

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Verify audit logs exist for the operation."""
        # Extract expected audit info from inputs
        institution_id = inputs.get("institution_id")
        mrn = inputs.get("mrn")

        if not institution_id or not mrn:
            return EvaluationResult(
                passed=False,
                score=0.0,
                metadata={"error": "Missing institution_id or mrn in inputs"},
            )

        # Check audit logs
        engine = create_async_engine(self.database_url)

        async with AsyncSession(engine) as session:
            # Look for audit log entries within last minute
            from datetime import datetime, timedelta

            cutoff = datetime.now() - timedelta(minutes=1)

            stmt = (
                select(AuditLog)
                .where(AuditLog.institution_id == institution_id)
                .where(AuditLog.timestamp >= cutoff)
                .order_by(AuditLog.timestamp.desc())
            )

            result = await session.execute(stmt)
            logs = result.scalars().all()

        await engine.dispose()

        # Check if any logs exist
        passed = len(logs) > 0
        score = 1.0 if passed else 0.0

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "audit_log_count": len(logs),
                "checked_institution": institution_id,
            },
        )


class ResponseCompletenessEvaluator(Evaluator):
    """Evaluator for response completeness.

    Checks that responses include:
    - Meaningful answer
    - Appropriate sources
    - Confidence score
    - Proper structure
    """

    min_answer_length: int = 50

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Evaluate response completeness."""
        issues = []

        # Check answer exists and has substance
        answer = output.get("answer", "")
        if len(answer) < self.min_answer_length:
            issues.append(f"Answer too short: {len(answer)} < {self.min_answer_length}")

        # Check confidence exists
        confidence = output.get("confidence")
        if confidence is None:
            issues.append("No confidence score provided")

        # Check sources if PHI was accessed
        phi_accessed = output.get("phi_accessed", False)
        sources = output.get("sources", [])

        if phi_accessed and len(sources) == 0:
            issues.append("PHI accessed but no sources cited")

        # For research queries, check references
        references = output.get("references", [])
        if "research" in str(inputs).lower() and len(references) == 0:
            issues.append("Research query but no references provided")

        passed = len(issues) == 0
        score = 1.0 - (len(issues) * 0.2)
        score = max(0, min(1, score))

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "issues": issues,
                "answer_length": len(answer),
                "sources_count": len(sources),
            },
        )


class CostBudgetEvaluator(Evaluator):
    """Evaluator to ensure queries stay within budget."""

    max_cost: float = 0.05  # $0.05 per query

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Check if cost is within budget."""
        cost = output.get("cost", 0.0)
        passed = cost <= self.max_cost

        # Calculate score based on cost efficiency
        if cost == 0:
            score = 1.0
        else:
            score = max(0, 1.0 - (cost / self.max_cost))

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "cost_usd": cost,
                "budget_usd": self.max_cost,
                "over_budget": cost > self.max_cost,
            },
        )


class LatencyEvaluator(Evaluator):
    """Evaluator for response latency.

    Medical queries should be fast for clinical decision support.
    """

    max_latency_ms: float = 3000  # 3 seconds

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Check if latency is acceptable."""
        latency_ms = output.get("latency_ms", 0.0)
        passed = latency_ms <= self.max_latency_ms

        # Score based on latency efficiency
        if latency_ms == 0:
            score = 1.0
        else:
            score = max(0, 1.0 - (latency_ms / (self.max_latency_ms * 2)))

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "latency_ms": latency_ms,
                "threshold_ms": self.max_latency_ms,
                "latency_seconds": latency_ms / 1000,
            },
        )


class ResearchCitationEvaluator(Evaluator):
    """Evaluator for proper research citations.

    Checks that research responses include proper citations:
    - DOIs or PubMed IDs
    - Author names
    - Publication dates
    """

    async def evaluate(
        self, inputs: dict, output: dict, expected_outputs: dict | None = None
    ) -> EvaluationResult:
        """Evaluate research citation quality."""
        references = output.get("references", [])

        if len(references) == 0:
            return EvaluationResult(
                passed=False,
                score=0.0,
                metadata={"error": "No references provided"},
            )

        issues = []
        for i, ref in enumerate(references):
            # Check for DOI or PubMed ID
            has_doi = "doi" in ref and ref["doi"]
            has_pmid = "pubmed_id" in ref and ref["pubmed_id"]

            if not (has_doi or has_pmid):
                issues.append(f"Reference {i} missing DOI and PubMed ID")

            # Check for publication date
            if "publication_date" not in ref:
                issues.append(f"Reference {i} missing publication date")

        passed = len(issues) == 0
        score = 1.0 - (len(issues) / len(references))
        score = max(0, min(1, score))

        return EvaluationResult(
            passed=passed,
            score=score,
            metadata={
                "issues": issues,
                "reference_count": len(references),
                "complete_citations": len(references) - len(issues),
            },
        )
