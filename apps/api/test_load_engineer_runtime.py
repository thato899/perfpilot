import json
import uuid

from apps.api import load_engineer, tasks
from apps.api.config import Settings
from packages.metrics.metrics import compare_metrics
from packages.schemas.python.agent_io import (
    InvestigationAnalysisRequest,
    LoadExecutionRequest,
    RampStrategy,
    TargetRef,
    TestPlanOutput,
    TestRunMetricsRef,
    TestStagePlan,
)
from packages.schemas.python.entities import TestType


def test_real_adapter_generates_parses_and_returns_metrics(tmp_path, monkeypatch):
    run_id = uuid.uuid4()
    plan = TestPlanOutput(
        test_type=TestType.CAPACITY,
        rationale="test",
        target_concurrency=2,
        ramp_strategy=RampStrategy(type="step", step_size=1, step_duration_s=1),
        user_journeys=["/health"],
        thresholds={"p95_ms": 500, "max_error_rate": 0.01},
        duration={"total_s": 2},
        stages=[
            TestStagePlan(target_vus=1, duration_s=1),
            TestStagePlan(target_vus=2, duration_s=1),
        ],
        success_criteria=["healthy"],
    )
    request = LoadExecutionRequest(
        test_plan=plan,
        target=TargetRef(base_url="http://localhost:8000"),
        test_run_id=run_id,
    )

    class FakeModule:
        SafetyLimits = load_engineer._load_engineer_module().SafetyLimits

        @staticmethod
        def prepare_load(plan, limits):
            return type("Prepared", (), {"test_plan": plan, "clamped": None})()

        @staticmethod
        def generate_k6_script(plan, target):
            return "export default function () {}"

        @staticmethod
        def run_k6(script_path, output_path, target, **kwargs):
            output_path.write_text(
                json.dumps(
                    {
                        "duration_seconds": 1,
                        "http_status_distribution": {"200": 2},
                        "metrics": {
                            "http_reqs": {"values": {"count": 2, "rate": 2}},
                            "http_req_duration": {
                                "values": {"med": 10, "p(90)": 20, "p(95)": 30, "p(99)": 40}
                            },
                            "http_req_failed": {"values": {"rate": 0}},
                        },
                    }
                ),
                encoding="utf-8",
            )

    monkeypatch.setattr(load_engineer, "_load_engineer_module", lambda: FakeModule)
    result = load_engineer.K6LoadEngineer(
        Settings(
            api_auth_secret="secret",
            allowed_target_hosts=frozenset({"localhost"}),
            k6_results_dir=str(tmp_path),
        )
    ).execute(request)
    assert result.status.value == "succeeded"
    assert result.metrics[0].p95_ms == 30
    assert result.metrics[0].concurrency == 2

    investigator = tasks._load_investigator_module()
    analysis_request = InvestigationAnalysisRequest(
        test_run=TestRunMetricsRef(id=run_id, metrics=result.metrics),
        baseline_test_run=TestRunMetricsRef(id=run_id, metrics=result.metrics),
        comparison=compare_metrics(result.metrics[0], result.metrics[0]).model_dump(mode="json"),
        thresholds=plan.thresholds,
    )
    analysis = investigator.PerformanceInvestigator().analyze(analysis_request)
    assert analysis.finding.severity.value == "INFO"
    assert analysis.hypotheses == []
