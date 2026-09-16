"""The Celery task — issue #13.

The done-when ("a test run can be triggered via the API and completes
asynchronously via a Celery worker") is proven against a real broker and a
real worker; what's here covers the paths a live run can't easily be pushed
down — a revoked target, a clamped ceiling, a wrapper that raises, and a
duplicate delivery.

The task is called directly rather than through `.delay()`. Eager mode would
run it in-process too, but it also swallows the difference between "the task
works" and "the worker can find it" — which is exactly the bug that only
showed up against a real worker (see celery_app.py's `include`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api import tasks
from apps.api.config import get_settings
from apps.api.db import models as m
from apps.api.load_engineer_stub import StubLoadEngineer, TargetNotAllowedError
from packages.schemas.python.entities import InvestigationStatus, TestRunStatus

from .conftest import AUTH


@pytest.fixture
def queued_run(client: TestClient, db_session, test_plan: dict, target: dict) -> m.TestRun:
    """A run in the state the API leaves it: queued, nothing consumed yet."""
    run_id = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    ).json()["test_run_id"]
    db_session.expire_all()
    return db_session.get(m.TestRun, run_id)


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_task_runs_queued_to_succeeded(db_session, queued_run: m.TestRun) -> None:
    assert queued_run.status is TestRunStatus.QUEUED

    tasks.execute_test_run(str(queued_run.id))

    db_session.expire_all()
    run = db_session.get(m.TestRun, queued_run.id)
    assert run.status is TestRunStatus.SUCCEEDED
    assert run.started_at is not None and run.completed_at is not None
    # Refs are stored for audit — load-engineer.md keeps the script and the
    # raw summary retrievable after the fact.
    assert run.k6_script_ref and run.raw_output_ref
    assert run.clamped is None


def test_task_writes_metrics_and_stages(db_session, queued_run: m.TestRun) -> None:
    tasks.execute_test_run(str(queued_run.id))
    db_session.expire_all()

    metrics = db_session.query(m.Metric).filter_by(test_run_id=queued_run.id).all()
    assert len(metrics) == 1
    assert metrics[0].p95_ms == 2800.0
    assert metrics[0].http_status_distribution == {"200": 14500, "500": 300}

    stages = (
        db_session.query(m.TestStage)
        .filter_by(test_run_id=queued_run.id)
        .order_by(m.TestStage.sequence_index)
        .all()
    )
    assert [s.sequence_index for s in stages] == [0, 1]
    assert [s.target_vus for s in stages] == [500, 1000]


def test_progress_endpoint_reflects_completion(client: TestClient, queued_run: m.TestRun) -> None:
    """What the dashboard polls actually changes once the worker is done."""
    before = client.get(f"/api/test-runs/{queued_run.id}", headers=AUTH).json()
    assert before["status"] == "queued"
    assert before["progress"]["current_vus"] == 0

    tasks.execute_test_run(str(queued_run.id))

    after = client.get(f"/api/test-runs/{queued_run.id}", headers=AUTH).json()
    assert after["status"] == "succeeded"
    assert after["progress"] == {"current_vus": 1000, "target_vus": 1000}


# --------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------


def test_duplicate_delivery_does_not_re_run(db_session, queued_run: m.TestRun) -> None:
    """Celery is at-least-once. A second delivery must not fire a second load test."""
    tasks.execute_test_run(str(queued_run.id))
    db_session.expire_all()
    first_completed = db_session.get(m.TestRun, queued_run.id).completed_at

    result = tasks.execute_test_run(str(queued_run.id))
    assert result["skipped"] is True

    db_session.expire_all()
    run = db_session.get(m.TestRun, queued_run.id)
    assert run.completed_at == first_completed
    assert db_session.query(m.Metric).filter_by(test_run_id=run.id).count() == 1


def test_unknown_run_is_not_an_error(db_session) -> None:
    """A task for a deleted run should report, not crash the worker."""
    from uuid import uuid4

    assert tasks.execute_test_run(str(uuid4()))["status"] == "not_found"


def test_target_revoked_before_execution_aborts(
    db_session, queued_run: m.TestRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Allow-listed at queue time, removed before the worker got to it.

    load-engineer.md requires this second check precisely because the gap
    between approval and execution is where a target can be revoked.
    """
    monkeypatch.setenv("ALLOWED_TARGET_HOSTS", "somewhere-else.invalid")
    get_settings.cache_clear()
    try:
        tasks.execute_test_run(str(queued_run.id))
    finally:
        get_settings.cache_clear()

    db_session.expire_all()
    run = db_session.get(m.TestRun, queued_run.id)
    assert run.status is TestRunStatus.ABORTED_OVER_LIMIT
    assert db_session.query(m.Metric).filter_by(test_run_id=run.id).count() == 0


def test_wrapper_failure_marks_the_run_failed(
    db_session, queued_run: m.TestRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self, request):  # noqa: ANN001, ANN202, ARG001
        raise RuntimeError("k6 exited 1")

    monkeypatch.setattr(StubLoadEngineer, "execute", boom)
    tasks.execute_test_run(str(queued_run.id))

    db_session.expire_all()
    run = db_session.get(m.TestRun, queued_run.id)
    assert run.status is TestRunStatus.FAILED
    assert run.completed_at is not None


# --------------------------------------------------------------------------
# The safety ceiling, enforced at execution time
# --------------------------------------------------------------------------


def test_over_ceiling_run_is_clamped_not_rejected(
    db_session, queued_run: m.TestRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    """security-model.md: "clamped, not silently honored and not silently rejected".

    The API's 429 catches a plan that's over the ceiling at approval time.
    This is the other half: a ceiling lowered *after* approval still binds,
    and the run proceeds at the cap with the reduction recorded.
    """
    monkeypatch.setenv("MAX_VIRTUAL_USERS", "600")
    get_settings.cache_clear()
    try:
        tasks.execute_test_run(str(queued_run.id))
    finally:
        get_settings.cache_clear()

    db_session.expire_all()
    run = db_session.get(m.TestRun, queued_run.id)

    assert run.status is TestRunStatus.SUCCEEDED, "a clamped run still runs"
    assert run.clamped == {
        "requested_vus": 1000,
        "executed_vus": 600,
        "reason": "MAX_VIRTUAL_USERS=600",
    }

    # The recorded stages are what actually ran, not what was planned —
    # the 1000-VU stage executed at 600.
    stages = (
        db_session.query(m.TestStage)
        .filter_by(test_run_id=run.id)
        .order_by(m.TestStage.sequence_index)
        .all()
    )
    assert [s.target_vus for s in stages] == [500, 600]

    metric = db_session.query(m.Metric).filter_by(test_run_id=run.id).one()
    assert metric.concurrency == 600


def test_clamp_uses_the_ceiling_not_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper is the enforcement point, independent of any caller."""
    monkeypatch.setenv("MAX_VIRTUAL_USERS", "100")
    get_settings.cache_clear()
    try:
        engine = StubLoadEngineer(get_settings())
        with pytest.raises(TargetNotAllowedError):
            engine.execute(_request(base_url="https://not-allowed.invalid"))
    finally:
        get_settings.cache_clear()


def _request(base_url: str):  # noqa: ANN202
    import uuid

    from packages.schemas.python.agent_io import (
        LoadExecutionRequest,
        RampStrategy,
        TargetRef,
        TestPlanOutput,
        TestStagePlan,
    )
    from packages.schemas.python.entities import TestType

    return LoadExecutionRequest(
        test_plan=TestPlanOutput(
            test_type=TestType.CAPACITY,
            rationale="x",
            target_concurrency=1000,
            ramp_strategy=RampStrategy(type="step", step_size=250, step_duration_s=60),
            user_journeys=["browse"],
            thresholds={"p95_ms": 2000.0},
            duration={"total_s": 600},
            stages=[TestStagePlan(target_vus=1000, duration_s=300)],
            success_criteria=["p95 < 2s"],
        ),
        target=TargetRef(base_url=base_url, auth=None),
        test_run_id=uuid.uuid4(),
    )


# --------------------------------------------------------------------------
# Dispatch and the completion callback
# --------------------------------------------------------------------------


def test_run_endpoint_dispatches_the_task(
    client: TestClient, test_plan: dict, target: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 202 has to actually enqueue something, not just write a row."""
    sent: list[str] = []
    monkeypatch.setattr(
        tasks.execute_test_run, "delay", lambda run_id: sent.append(run_id), raising=False
    )

    res = client.post(
        f"/api/tests/{test_plan['id']}/run", json={"target_id": target["id"]}, headers=AUTH
    )
    assert res.status_code == 202
    assert sent == [res.json()["test_run_id"]]


def test_completion_advances_a_linked_investigation(
    client: TestClient, db_session, queued_run: m.TestRun, target: dict
) -> None:
    """data-flow.md's completion callback: OBSERVE -> the Orchestrator decides."""
    inv = client.post(
        "/api/investigations",
        json={
            "target_id": target["id"],
            "objective": "determine_capacity",
            "expected_traffic": {"normal_concurrent_users": 500, "peak_concurrent_users": 1000},
        },
        headers=AUTH,
    ).json()

    investigation = db_session.get(m.Investigation, inv["id"])
    investigation.current_test_run_id = queued_run.id
    db_session.commit()

    tasks.execute_test_run(str(queued_run.id))

    db_session.expire_all()
    # The stub Orchestrator always answers COMPLETE with status `reporting`.
    assert db_session.get(m.Investigation, inv["id"]).status is InvestigationStatus.REPORTING


def test_completion_without_an_investigation_is_fine(db_session, queued_run: m.TestRun) -> None:
    """A standalone run has no investigation state machine to move."""
    tasks.execute_test_run(str(queued_run.id))
    db_session.expire_all()
    assert db_session.get(m.TestRun, queued_run.id).status is TestRunStatus.SUCCEEDED
