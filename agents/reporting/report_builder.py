"""Deterministic Report synthesis for the Reporting Agent.

Turns a `ReportRequest` (the full `InvestigationState` plus the
`capacity_estimate`/`regression_comparison`/`key_metrics` numbers
`packages/metrics` already computed) into a valid `ReportOutput`, per
docs/agents/reporting-agent.md.

This is the fixture-first slice of the contract (see issue #15 /
docs/development/next-steps.md): "produce a valid Report from fixture
InvestigationState, then wire to a real one." Prose generation (the
executive summary, each recommendation's phrasing) uses plain deterministic
templates here, not an LLM call — `packages/ai` (issue #1) doesn't exist
yet. The template functions are isolated on purpose so the *structural*
logic (grounding every claim in the input, passing numbers through
unaltered, ranking findings) doesn't have to change once that swap happens.

# BLOCKED-ON: #1 (packages/ai) — replace `_executive_summary` and
# `_recommendation_statement` with AIService-generated prose once
# packages/ai exists. See docs/development/coding-standards.md §5.
"""

from __future__ import annotations

from packages.schemas.python.agent_io import (
    BottleneckAnalysisEntry,
    FindingSummary,
    RecommendationOutput,
    ReportOutput,
    ReportRequest,
)
from packages.schemas.python.entities import (
    Evidence,
    Finding,
    Hypothesis,
    HypothesisStatus,
    Severity,
)

# CRITICAL -> INFO, per reporting-agent.md's "ranked CRITICAL -> INFO" responsibility.
_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
]


def build_report(request: ReportRequest) -> ReportOutput:
    """Build a valid `ReportOutput` from a `ReportRequest`.

    Raises `ValueError` if `investigation_state` is malformed (a hypothesis
    referencing a `finding_id` that isn't in `investigation_state.findings`)
    or if the assembled report fails `validate_report`'s guardrail checks —
    this should never happen given well-formed input, but failing loudly
    beats silently guessing, per the "structured contracts, not invented
    shapes" rule in CONTRIBUTING.md.
    """
    state = request.investigation_state
    findings_by_id: dict[str, Finding] = {str(f.id): f for f in state.findings}

    for hypothesis in state.hypotheses:
        if str(hypothesis.finding_id) not in findings_by_id:
            raise ValueError(
                f"hypothesis {hypothesis.id} references finding_id="
                f"{hypothesis.finding_id}, which is not in investigation_state.findings"
            )

    ranked_findings = sorted(state.findings, key=lambda f: _SEVERITY_ORDER.index(f.severity))

    report = ReportOutput(
        executive_summary=_executive_summary(request, ranked_findings),
        capacity=request.capacity_estimate,
        key_metrics=request.key_metrics,
        findings=[
            FindingSummary(id=str(f.id), severity=f.severity, summary=f.summary)
            for f in ranked_findings
        ],
        bottleneck_analysis=[
            _bottleneck_entry(h, findings_by_id[str(h.finding_id)]) for h in state.hypotheses
        ],
        recommendations=[
            RecommendationOutput(
                finding_id=str(h.finding_id),
                statement=_recommendation_statement(h),
                priority=findings_by_id[str(h.finding_id)].severity,
            )
            for h in state.hypotheses
            if h.status == HypothesisStatus.SUPPORTED
        ],
        regression=request.regression_comparison,
    )

    violations = validate_report(report, request)
    if violations:
        raise ValueError("build_report produced an invalid Report:\n" + "\n".join(violations))

    return report


def _bottleneck_entry(hypothesis: Hypothesis, finding: Finding) -> BottleneckAnalysisEntry:
    return BottleneckAnalysisEntry(
        observation=finding.summary,
        likely_cause=hypothesis.statement,
        evidence=[_render_evidence(e) for e in hypothesis.evidence],
        confidence=hypothesis.confidence,
    )


def _render_evidence(evidence: Evidence) -> str:
    # Keeps source_ref traceable in the rendered text even though
    # BottleneckAnalysisEntry.evidence is list[str], not list[Evidence].
    return f"{evidence.statement} (source: {evidence.source_ref})"


def _recommendation_statement(hypothesis: Hypothesis) -> str:
    # BLOCKED-ON: #1 — templated placeholder; real AIService phrasing later.
    # Deliberately one recommendation per supported hypothesis, not an
    # elaborated multi-step list — inventing extra sub-recommendations not
    # traceable to a specific hypothesis would violate the "grounded in
    # evidence" rule in reporting-agent.md's Responsibilities.
    statement = hypothesis.statement.strip().rstrip(".")
    return f"Investigate {statement[0].lower()}{statement[1:]}."


def _executive_summary(request: ReportRequest, ranked_findings: list[Finding]) -> str:
    # BLOCKED-ON: #1 — templated placeholder; real AIService prose later.
    capacity = request.capacity_estimate
    if not ranked_findings:
        # Failure states table: a fully healthy run is valid output, not an error.
        return (
            "The application handled the tested load cleanly, with no findings raised. "
            f"Estimated sustainable capacity: ~{capacity.sustainable_concurrency} concurrent "
            f"users (recommended operating level: {capacity.recommended_operating_concurrency})."
        )
    top = ranked_findings[0]
    return (
        "The application remained healthy up to approximately "
        f"{capacity.recommended_operating_concurrency} concurrent users. "
        f"Most significant finding ({top.severity.value}): {top.summary}"
    )


def validate_report(report: ReportOutput, request: ReportRequest) -> list[str]:
    """Mechanically check the guardrails in docs/agents/reporting-agent.md's
    Failure states table. Returns a list of violation messages — empty means
    valid. `build_report` calls this on its own output before returning
    (defense in depth, matching the "enforced, not just prompted" guardrail
    style used elsewhere — see performance-investigator.md).

    Known limitation: the confidence-preserved check below assumes
    `report.bottleneck_analysis` was built in the same order as
    `request.investigation_state.hypotheses` (true for anything built by
    `build_report` in this module) — `BottleneckAnalysisEntry` has no
    hypothesis-linking id in the schema to check this more robustly.
    Flagged here rather than silently relied on; a future schema addition
    (e.g. a `hypothesis_id` field) would let this be order-independent.
    """
    violations: list[str] = []

    if report.capacity != request.capacity_estimate:
        violations.append("capacity was altered from the input capacity_estimate")
    if report.regression != request.regression_comparison:
        violations.append("regression was altered from the input regression_comparison")
    if report.key_metrics != request.key_metrics:
        violations.append("key_metrics was altered from the input key_metrics")

    finding_ids = {str(f.id) for f in request.investigation_state.findings}
    for fs in report.findings:
        if fs.id not in finding_ids:
            violations.append(f"output finding id={fs.id} is not in investigation_state.findings")

    for rec in report.recommendations:
        matching_hypotheses = [
            h for h in request.investigation_state.hypotheses if str(h.finding_id) == rec.finding_id
        ]
        if not matching_hypotheses:
            violations.append(
                f"recommendation references finding_id={rec.finding_id} with no matching "
                "hypothesis in investigation_state.hypotheses"
            )

    if len(report.bottleneck_analysis) == len(request.investigation_state.hypotheses):
        for bottleneck, hypothesis in zip(
            report.bottleneck_analysis, request.investigation_state.hypotheses, strict=True
        ):
            if bottleneck.confidence != hypothesis.confidence:
                violations.append(
                    f"bottleneck_analysis confidence ({bottleneck.confidence}) does not match "
                    f"source hypothesis {hypothesis.id}'s confidence ({hypothesis.confidence})"
                )
    else:
        violations.append(
            "bottleneck_analysis length does not match investigation_state.hypotheses length"
        )

    return violations
