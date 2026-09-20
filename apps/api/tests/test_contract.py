"""Every endpoint in api-contract.md, checked against its documented shape.

Issue #12's done-when: "every listed endpoint matches its documented
request/response shape in api-contract.md, tested against a stub
Orchestrator". These tests assert the *contract* — status codes, field
names, the error envelope — rather than implementation details, so they
keep holding when the stub is replaced by the real Orchestrator.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.db import models as m
from packages.schemas.python.entities import (
    ExperimentStatus,
    HypothesisStatus,
    InvestigationObjective,
    InvestigationStatus,
    Severity,
    TestPlanStatus,
    TestRunStatus,
)

from .conftest import AUTH, make_uuid

# --------------------------------------------------------------------------
# Auth — "Every endpoint below requires this header unless noted."
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/projects"),
        ("get", f"/api/projects/{make_uuid()}"),
        ("post", f"/api/projects/{make_uuid()}/targets"),
        ("post", "/api/tests/plan"),
        ("post", f"/api/tests/{make_uuid()}/run"),
        ("get", f"/api/test-runs/{make_uuid()}"),
        ("get", f"/api/test-runs/{make_uuid()}/metrics"),
        ("post", "/api/investigations"),
        ("get", f"/api/investigations/{make_uuid()}"),
        ("get", f"/api/investigations/{make_uuid()}/findings"),
        ("post", f"/api/investigations/{make_uuid()}/experiments"),
        ("post", f"/api/investigations/{make_uuid()}/continue"),
        ("get", f"/api/reports/{make_uuid()}"),
    ],
)
def test_every_endpoint_requires_auth(client: TestClient, method: str, path: str) -> None:
    # TestClient.get() takes no `json=`; only the body-carrying verbs get one.
    kwargs = {"json": {}} if method == "post" else {}
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 401, f"{method.upper()} {path} did not require auth"
    assert res.json()["error"]["code"] == "unauthorized"


def test_health_is_unauthenticated(client: TestClient) -> None:
    # Documented as the one exception: compose and Render probe it without
    # a token.
    assert client.get("/health").status_code == 200


def test_wrong_token_is_rejected(client: TestClient) -> None:
    res = client.post("/api/projects", json={"name": "x"}, headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401


# --------------------------------------------------------------------------
# Error envelope — { "error": { "code", "message", "detail" } }
# --------------------------------------------------------------------------


def test_error_envelope_shape(client: TestClient) -> None:
    body = client.get(f"/api/projects/{make_uuid()}", headers=AUTH).json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail"}
    assert isinstance(body["error"]["detail"], dict)


def test_validation_failure_uses_the_envelope(client: TestClient) -> None:
    # A Pydantic failure would otherwise return FastAPI's bare list, which
    # is the one response shape a client couldn't parse.
    res = client.post("/api/projects", json={}, headers=AUTH)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_unknown_path_uses_the_envelope(client: TestClient) -> None:
    res = client.get("/api/nope", headers=AUTH)
    assert res.status_code == 404
    assert "error" in res.json()


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------


def test_create_project(client: TestClient) -> None:
    res = client.post("/api/projects", json={"name": "PerfPilot demo"}, headers=AUTH)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "PerfPilot demo"
    assert {"id", "name", "description", "created_at", "updated_at"} <= set(body)


def test_create_project_requires_name(client: TestClient) -> None:
    assert client.post("/api/projects", json={"description": "x"}, headers=AUTH).status_code == 422


def test_get_project_summary(client: TestClient, project: dict, target: dict) -> None:
    body = client.get(f"/api/projects/{project['id']}", headers=AUTH).json()
    # "fetch a project and its summary (target count, latest investigation
    # status)" — both fields the contract names.
    assert body["target_count"] == 1
    assert body["latest_investigation_status"] is None


def test_get_missing_project_404(client: TestClient) -> None:
    assert client.get(f"/api/projects/{make_uuid()}", headers=AUTH).status_code == 404


# --------------------------------------------------------------------------
# Targets — the two independent authorization gates
# --------------------------------------------------------------------------


def test_create_target(client: TestClient, target: dict) -> None:
    assert target["authorization_confirmed"] is True
    assert target["authorization_confirmed_by"] == "kamogelo"
    # Recorded server-side, never taken from the request.
    assert target["authorization_confirmed_at"] is not None


def test_unconfirmed_target_is_422(client: TestClient, project: dict) -> None:
    res = client.post(
        f"/api/projects/{project['id']}/targets",
        json={
            "base_url": "https://demo.perfpilot.local",
            "name": "demo",
            "authorization_confirmed": False,
        },
        headers=AUTH,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "authorization_not_confirmed"


def test_target_off_allow_list_is_403(client: TestClient, project: dict) -> None:
    res = client.post(
        f"/api/projects/{project['id']}/targets",
        json={
            "base_url": "https://www.example.com",
            "name": "not ours",
            "authorization_confirmed": True,
        },
        headers=AUTH,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "target_not_allowed"


def test_confirmation_is_checked_before_the_allow_list(client: TestClient, project: dict) -> None:
    """A request failing both gates reports the one the caller controls.

    Otherwise an unconfirmed request for an arbitrary host learns which
    hosts the operator has allow-listed, which is information it shouldn't
    get for free.
    """
    res = client.post(
        f"/api/projects/{project['id']}/targets",
        json={
            "base_url": "https://www.example.com",
            "name": "neither",
            "authorization_confirmed": False,
        },
        headers=AUTH,
    )
    assert res.status_code == 422


def test_allow_list_matches_host_not_url(client: TestClient, project: dict) -> None:
    # localhost is allow-listed; the port must not affect the decision.
    res = client.post(
        f"/api/projects/{project['id']}/targets",
        json={
            "base_url": "http://localhost:8080/api",
            "name": "local",
            "authorization_confirmed": True,
        },
        headers=AUTH,
    )
    assert res.status_code == 201


# --------------------------------------------------------------------------
# Test plans and runs
# --------------------------------------------------------------------------


def test_create_test_plan(client: TestClient, test_plan: dict) -> None:
    assert test_plan["status"] == "proposed"  # persisted as proposed
    assert test_plan["target_concurrency"] == 1000  # echoed from peak traffic
    assert test_plan["user_journeys"] == ["browse", "checkout"]
    assert test_plan["thresholds"]["p95_ms"] == 2000.0
    assert test_plan["ramp_strategy"]["type"] == "step"
    assert [stage["target_vus"] for stage in test_plan["stages"]] == [
        10,
        50,
        100,
        250,
        500,
        750,
        1000,
    ]


def test_create_plan_for_missing_target_404(client: TestClient, project: dict) -> None:
    res = client.post(
        "/api/tests/plan",
        json={
            "project_id": project["id"],
            "target_id": make_uuid(),
            "objective": "determine_capacity",
            "user_journeys": ["browse"],
            "expected_traffic": {"normal_concurrent_users": 10, "peak_concurrent_users": 50},
            "p95_ms": 500.0,
            "max_error_rate": 0.01,
        },
        headers=AUTH,
    )
    assert res.status_code == 404


def test_run_test_plan_returns_202_queued(
    client: TestClient, test_plan: dict, target: dict
) -> None:
    res = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == TestRunStatus.QUEUED.value
    assert body["test_run_id"]


def test_second_run_while_queued_is_409(client: TestClient, test_plan: dict, target: dict) -> None:
    client.post(f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH)
    res = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "run_in_progress"


def test_over_ceiling_plan_is_429(
    client: TestClient, db_session, test_plan: dict, target: dict
) -> None:
    """The safety ceiling bounds load regardless of what the plan asks for."""
    plan = db_session.get(m.TestPlan, test_plan["id"])
    plan.target_concurrency = 999_999
    db_session.commit()

    res = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "vus_over_limit"
    assert res.json()["error"]["detail"]["max_virtual_users"] == 5000


def test_run_against_revoked_target_is_403(
    client: TestClient, db_session, test_plan: dict, target: dict
) -> None:
    """Authorization is re-checked at run time, not trusted from creation."""
    row = db_session.get(m.Target, target["id"])
    row.authorization_confirmed = False
    db_session.commit()

    res = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    )
    assert res.status_code == 403


def test_get_test_run_progress_shape(client: TestClient, test_plan: dict, target: dict) -> None:
    run_id = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    ).json()["test_run_id"]

    body = client.get(f"/api/test-runs/{run_id}", headers=AUTH).json()
    assert body["status"] == "queued"
    assert body["progress"] == {"current_vus": 0, "target_vus": 1000}


def test_get_metrics_empty_then_populated(
    client: TestClient, db_session, test_plan: dict, target: dict
) -> None:
    run_id = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    ).json()["test_run_id"]

    assert client.get(f"/api/test-runs/{run_id}/metrics", headers=AUTH).json() == {"metrics": []}

    db_session.add(
        m.Metric(
            test_run_id=run_id,
            endpoint=None,
            p50_ms=120.0,
            p90_ms=400.0,
            p95_ms=2800.0,
            p99_ms=5000.0,
            throughput_rps=310.5,
            error_rate=0.02,
            concurrency=750,
            http_status_distribution={"200": 14500, "500": 300},
            recorded_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    metrics = client.get(f"/api/test-runs/{run_id}/metrics", headers=AUTH).json()["metrics"]
    assert len(metrics) == 1
    assert metrics[0]["p95_ms"] == 2800.0
    assert metrics[0]["http_status_distribution"] == {"200": 14500, "500": 300}


def test_metrics_for_missing_run_404(client: TestClient) -> None:
    assert client.get(f"/api/test-runs/{make_uuid()}/metrics", headers=AUTH).status_code == 404


# --------------------------------------------------------------------------
# Investigations
# --------------------------------------------------------------------------


def test_create_investigation(client: TestClient, db_session, target: dict) -> None:
    res = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 200, "peak_concurrent_users": 1000},
        },
        headers=AUTH,
    )
    assert res.status_code == 201
    body = res.json()
    # Creation owns the initial PLAN -> queued RUN transition, so the
    # investigation is running as soon as its first run is linked.
    assert body["status"] == InvestigationStatus.RUNNING.value
    assert body["objective"] == InvestigationObjective.DETERMINE_CAPACITY.value
    assert body["experiments_run"] == 0
    assert body["current_test_run_id"] is not None
    run = db_session.get(m.TestRun, body["current_test_run_id"])
    assert run is not None
    assert str(run.target_id) == target["id"]
    plan = db_session.get(m.TestPlan, run.test_plan_id)
    assert plan is not None
    assert plan.status is TestPlanStatus.APPROVED


def test_investigation_for_unauthorized_target_is_403(
    client: TestClient, db_session, target: dict
) -> None:
    row = db_session.get(m.Target, target["id"])
    row.authorization_confirmed = False
    db_session.commit()
    res = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "baseline",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    )
    assert res.status_code == 403


def test_get_investigation_returns_investigation_state(client: TestClient, target: dict) -> None:
    """GET must mirror the Orchestrator's InvestigationState, per data-flow.md."""
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 200, "peak_concurrent_users": 1000},
        },
        headers=AUTH,
    ).json()

    body = client.get(f"/api/investigations/{inv['id']}", headers=AUTH).json()
    assert set(body) >= {
        "investigation_id",
        "target_id",
        "status",
        "baseline_test_run_id",
        "current_test_run_id",
        "findings",
        "hypotheses",
        "experiments",
        "decisions",
    }
    assert body["investigation_id"] == inv["id"]
    assert body["findings"] == []


def _seed_finding(db_session, investigation_id: str, severity: Severity) -> m.Finding:
    finding = m.Finding(
        investigation_id=investigation_id,
        severity=severity,
        summary=f"{severity.value} finding",
        observations=[{"id": "obs_1", "statement": "p95 rose", "metric_ref": "met_1"}],
    )
    db_session.add(finding)
    db_session.commit()
    return finding


def test_findings_are_ranked_by_severity(client: TestClient, db_session, target: dict) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()

    # Inserted worst-last, so an unordered query would return them wrong.
    for sev in (Severity.LOW, Severity.CRITICAL, Severity.MEDIUM):
        _seed_finding(db_session, inv["id"], sev)

    findings = client.get(f"/api/investigations/{inv['id']}/findings", headers=AUTH).json()[
        "findings"
    ]
    assert [f["severity"] for f in findings] == ["CRITICAL", "MEDIUM", "LOW"]


def test_experiment_without_recommendation_is_409(
    client: TestClient, db_session, target: dict
) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    finding = _seed_finding(db_session, inv["id"], Severity.HIGH)
    hypothesis = m.Hypothesis(
        finding_id=finding.id,
        statement="pool contention",
        confidence=0.6,
        status=HypothesisStatus.PROPOSED,
        evidence=[],
        recommended_experiment=None,
    )
    db_session.add(hypothesis)
    db_session.commit()

    res = client.post(
        f"/api/investigations/{inv['id']}/experiments",
        json={"hypothesis_id": str(hypothesis.id)},
        headers=AUTH,
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "no_recommended_experiment"


def test_approve_experiment_queues_a_run(
    client: TestClient, db_session, target: dict, test_plan: dict
) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    finding = _seed_finding(db_session, inv["id"], Severity.HIGH)
    hypothesis = m.Hypothesis(
        finding_id=finding.id,
        statement="pool contention",
        confidence=0.6,
        status=HypothesisStatus.TESTING,
        evidence=[],
        recommended_experiment={"variable_to_isolate": "db_pool_size"},
    )
    db_session.add(hypothesis)
    db_session.commit()

    res = client.post(
        f"/api/investigations/{inv['id']}/experiments",
        json={"hypothesis_id": str(hypothesis.id)},
        headers=AUTH,
    )
    assert res.status_code == 202
    assert res.json()["test_run_id"]

    # The budget counter must move, or MAX_EXPERIMENTS_PER_INVESTIGATION
    # never bites and the loop can generate load indefinitely.
    db_session.expire_all()
    assert db_session.get(m.Investigation, inv["id"]).experiments_run == 1


def test_investigation_state_exposes_budget_and_ordered_event_history(
    client: TestClient, target: dict
) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()

    state = client.get(f"/api/investigations/{inv['id']}", headers=AUTH).json()

    assert state["experiment_budget"] == {
        "max_experiments": 3,
        "consumed": 0,
        "remaining": 3,
        "exhausted": False,
    }
    assert [event["sequence"] for event in state["events"]] == sorted(
        event["sequence"] for event in state["events"]
    )
    assert [event["type"] for event in state["events"][:2]] == [
        "investigation_created",
        "test_run_queued",
    ]


def test_approve_experiment_is_idempotent(client: TestClient, db_session, target: dict) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    finding = _seed_finding(db_session, inv["id"], Severity.HIGH)
    hypothesis = m.Hypothesis(
        finding_id=finding.id,
        statement="pool contention",
        confidence=0.6,
        status=HypothesisStatus.TESTING,
        evidence=[],
        recommended_experiment={"variable_to_isolate": "db_pool_size", "change": "32"},
    )
    db_session.add(hypothesis)
    db_session.commit()

    headers = {**AUTH, "Idempotency-Key": "approve-pool-1"}
    first = client.post(
        f"/api/investigations/{inv['id']}/experiments",
        json={"hypothesis_id": str(hypothesis.id)},
        headers=headers,
    )
    second = client.post(
        f"/api/investigations/{inv['id']}/experiments",
        json={"hypothesis_id": str(hypothesis.id)},
        headers=headers,
    )

    assert first.status_code == second.status_code == 202
    assert first.json()["test_run_id"] == second.json()["test_run_id"]
    assert db_session.query(m.Experiment).filter_by(hypothesis_id=hypothesis.id).count() == 1
    assert db_session.query(m.Experiment).filter_by(hypothesis_id=hypothesis.id).one().status in {
        ExperimentStatus.QUEUED,
        ExperimentStatus.RUNNING,
        ExperimentStatus.SUCCEEDED,
    }


def test_experiment_budget_exhaustion_is_explicit_409(
    client: TestClient, db_session, target: dict
) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    investigation = db_session.get(m.Investigation, inv["id"])
    investigation.max_experiments = 0
    finding = _seed_finding(db_session, inv["id"], Severity.HIGH)
    hypothesis = m.Hypothesis(
        finding_id=finding.id,
        statement="pool contention",
        confidence=0.6,
        status=HypothesisStatus.TESTING,
        evidence=[],
        recommended_experiment={"variable_to_isolate": "db_pool_size"},
    )
    db_session.add(hypothesis)
    db_session.commit()

    response = client.post(
        f"/api/investigations/{inv['id']}/experiments",
        json={"hypothesis_id": str(hypothesis.id)},
        headers=AUTH,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "experiment_budget_exhausted"


def test_continue_returns_an_orchestrator_decision(
    client: TestClient, target: dict, test_plan: dict
) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    run_id = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    ).json()["test_run_id"]

    res = client.post(
        f"/api/investigations/{inv['id']}/continue", json={"test_run_id": run_id}, headers=AUTH
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"next_action", "updated_state"}
    assert body["next_action"] == "invoke_investigator"
    assert body["updated_state"]["current_test_run_id"] == run_id


def test_continue_with_unknown_run_404(client: TestClient, target: dict) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "baseline",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    res = client.post(
        f"/api/investigations/{inv['id']}/continue",
        json={"test_run_id": make_uuid()},
        headers=AUTH,
    )
    assert res.status_code == 404


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def test_report_404_before_reporting(client: TestClient, target: dict) -> None:
    """ "404 if the investigation hasn't reached reporting/complete yet — the
    API does not auto-generate a partial report on this endpoint."
    """
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    assert client.get(f"/api/reports/{inv['id']}", headers=AUTH).status_code == 404


def test_get_report(client: TestClient, db_session, target: dict) -> None:
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
        },
        headers=AUTH,
    ).json()
    db_session.add(
        m.Report(
            investigation_id=inv["id"],
            executive_summary="Capacity is roughly 700 concurrent users.",
            capacity={"max_vus": 700},
            key_metrics={"p95_ms": 2800},
            bottleneck_analysis=[{"component": "database connection pool"}],
            regression={"delta_pct": 0.0},
        )
    )
    db_session.commit()

    body = client.get(f"/api/reports/{inv['id']}", headers=AUTH).json()
    assert body["executive_summary"].startswith("Capacity")
    assert body["capacity"] == {"max_vus": 700}
    assert body["bottleneck_analysis"] == [{"component": "database connection pool"}]
