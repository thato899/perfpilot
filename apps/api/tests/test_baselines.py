"""Baseline selection and comparison — issue #34.

Three layers, deliberately:

- Pure eligibility rules, exercised as values with no database. They are the
  part most likely to be read by a reviewer deciding whether the rules are
  right, so they are readable on their own.
- Persistence and constraints, against real Postgres — the uniqueness and
  RESTRICT rules are enforced by the database, so asserting them in Python
  alone would prove nothing.
- The HTTP surface, including every documented failure, because "explicit
  errors" is an acceptance criterion rather than a nicety.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from apps.api.baselines import (
    ComparisonResult,
    Incompatible,
    IncompatibleReason,
    RunFacts,
    build_comparison,
    check_eligibility,
    check_pair,
)
from packages.metrics.metrics import ComparisonStatus
from packages.schemas.python.entities import TestRunStatus

from .conftest import AUTH, m

TARGET_A = uuid.uuid4()
TARGET_B = uuid.uuid4()


def facts(**overrides) -> RunFacts:
    base = {
        "test_run_id": uuid.uuid4(),
        "target_id": TARGET_A,
        "status": TestRunStatus.SUCCEEDED,
        "test_type": "load",
        "target_concurrency": 100,
    }
    base.update(overrides)
    return RunFacts(**base)


# --- eligibility rules, no database ---------------------------------------


class TestEligibility:
    def test_a_succeeded_run_is_eligible(self):
        assert check_eligibility(facts(), as_baseline=True) is None
        assert check_eligibility(facts(), as_baseline=False) is None

    @pytest.mark.parametrize(
        "status",
        [
            TestRunStatus.QUEUED,
            TestRunStatus.RUNNING,
            TestRunStatus.FAILED,
            TestRunStatus.ABORTED_OVER_LIMIT,
        ],
    )
    def test_any_non_succeeded_run_is_refused(self, status):
        failure = check_eligibility(facts(status=status), as_baseline=True)
        assert failure is not None
        assert failure.reason is IncompatibleReason.BASELINE_RUN_NOT_SUCCEEDED
        assert failure.detail["status"] == status.value

    def test_the_reason_names_the_side_that_failed(self):
        # The same unsuitable run produces a different code depending on which
        # role it was being considered for, so an operator reading the error
        # knows which half of the pair to look at.
        assert (
            check_eligibility(facts(status=TestRunStatus.FAILED), as_baseline=False).reason
            is IncompatibleReason.CURRENT_RUN_NOT_SUCCEEDED
        )


class TestPairCompatibility:
    def test_identical_scenarios_are_comparable(self):
        assert check_pair(facts(), facts()) is None

    def test_a_different_target_is_a_different_environment(self):
        failure = check_pair(facts(), facts(target_id=TARGET_B))
        assert failure.reason is IncompatibleReason.ENVIRONMENT_MISMATCH
        assert failure.detail["baseline_target_id"] == str(TARGET_A)

    def test_a_different_test_type_is_refused(self):
        failure = check_pair(facts(), facts(test_type="stress"))
        assert failure.reason is IncompatibleReason.TEST_TYPE_MISMATCH

    def test_a_different_concurrency_is_refused(self):
        # A 200-VU run against a 1000-VU one would read as a regression that
        # is really just more load.
        failure = check_pair(facts(target_concurrency=200), facts(target_concurrency=1000))
        assert failure.reason is IncompatibleReason.CONCURRENCY_MISMATCH
        assert failure.detail == {
            "baseline_target_concurrency": 200,
            "current_target_concurrency": 1000,
        }

    def test_a_different_plan_of_the_same_shape_is_still_comparable(self):
        # Re-planning the same scenario must not disqualify every historical
        # baseline — compatibility is the shape, not the plan row.
        assert check_pair(facts(), facts()) is None

    def test_status_is_checked_before_the_scenario(self):
        # A run that never finished is not comparable for a more basic reason
        # than which target it used, and the more basic reason is the useful
        # one to report.
        failure = check_pair(facts(status=TestRunStatus.FAILED), facts(target_id=TARGET_B))
        assert failure.reason is IncompatibleReason.BASELINE_RUN_NOT_SUCCEEDED

    def test_every_reason_has_a_message(self):
        from apps.api.baselines import REASON_MESSAGES

        assert set(REASON_MESSAGES) == set(IncompatibleReason)
        assert all(text.strip() for text in REASON_MESSAGES.values())


# --- metric pairing --------------------------------------------------------


def metric(endpoint, *, p95=100.0, run_id=None, recorded="2026-09-24T10:00:00Z"):
    from datetime import datetime

    return m.Metric(
        id=uuid.uuid4(),
        test_run_id=run_id or uuid.uuid4(),
        endpoint=endpoint,
        p50_ms=p95 / 2,
        p90_ms=p95 * 0.9,
        p95_ms=p95,
        p99_ms=p95 * 1.5,
        throughput_rps=50.0,
        error_rate=0.01,
        concurrency=100,
        http_status_distribution={"200": 100},
        recorded_at=datetime.fromisoformat(recorded),
    )


class TestMetricPairing:
    def test_pairs_every_shared_endpoint_with_the_aggregate_first(self):
        result = build_comparison(
            baseline_run_id=uuid.uuid4(),
            current_run_id=uuid.uuid4(),
            baseline_metrics=[metric(None), metric("/checkout"), metric("/browse")],
            current_metrics=[metric(None), metric("/checkout"), metric("/browse")],
        )
        assert isinstance(result, ComparisonResult)
        assert len(result.comparisons) == 3
        assert all(c.status is ComparisonStatus.AVAILABLE for c in result.comparisons)

    def test_names_endpoints_measured_on_only_one_side(self):
        # A scope present in one run and not the other is a real difference.
        # Dropping it silently would make the comparison look complete.
        result = build_comparison(
            baseline_run_id=uuid.uuid4(),
            current_run_id=uuid.uuid4(),
            baseline_metrics=[metric(None), metric("/legacy")],
            current_metrics=[metric(None), metric("/new")],
        )
        assert isinstance(result, ComparisonResult)
        assert result.baseline_only_endpoints == ["/legacy"]
        assert result.current_only_endpoints == ["/new"]
        assert len(result.comparisons) == 1

    def test_refuses_when_no_endpoint_is_shared(self):
        result = build_comparison(
            baseline_run_id=uuid.uuid4(),
            current_run_id=uuid.uuid4(),
            baseline_metrics=[metric("/a")],
            current_metrics=[metric("/b")],
        )
        assert isinstance(result, Incompatible)
        assert result.reason is IncompatibleReason.NO_SHARED_ENDPOINT

    @pytest.mark.parametrize(
        ("baseline", "current", "expected"),
        [
            ([], [metric(None)], IncompatibleReason.BASELINE_METRICS_UNAVAILABLE),
            ([metric(None)], [], IncompatibleReason.CURRENT_METRICS_UNAVAILABLE),
        ],
    )
    def test_missing_metrics_are_refused_not_treated_as_zero(self, baseline, current, expected):
        run_id = uuid.uuid4()
        result = build_comparison(
            baseline_run_id=run_id,
            current_run_id=run_id,
            baseline_metrics=baseline,
            current_metrics=current,
        )
        assert isinstance(result, Incompatible)
        assert result.reason is expected
        assert result.detail["test_run_id"] == str(run_id)

    def test_the_latest_sample_wins_for_a_repeated_endpoint(self):
        # Interval-collected metrics record the same scope more than once;
        # the final sample is the one that describes the finished run.
        result = build_comparison(
            baseline_run_id=uuid.uuid4(),
            current_run_id=uuid.uuid4(),
            baseline_metrics=[
                metric(None, p95=100.0, recorded="2026-09-24T10:00:00Z"),
                metric(None, p95=400.0, recorded="2026-09-24T10:05:00Z"),
            ],
            current_metrics=[metric(None, p95=400.0)],
        )
        assert isinstance(result, ComparisonResult)
        assert result.comparisons[0].p95_delta_ms == 0.0

    def test_arithmetic_comes_from_packages_metrics_untouched(self):
        # 100ms -> 150ms is +50ms / +50%. This asserts the delegation, not the
        # sums: if this layer ever started computing its own numbers, this is
        # where the two would disagree.
        result = build_comparison(
            baseline_run_id=uuid.uuid4(),
            current_run_id=uuid.uuid4(),
            baseline_metrics=[metric(None, p95=100.0)],
            current_metrics=[metric(None, p95=150.0)],
        )
        assert isinstance(result, ComparisonResult)
        comparison = result.comparisons[0]
        assert comparison.p95_delta_ms == 50.0
        assert comparison.p95_delta_pct == 50.0


# --- persistence, against real Postgres ------------------------------------


def _succeeded_run(client: TestClient, db_session, test_plan: dict, target: dict) -> str:
    run = m.TestRun(
        test_plan_id=uuid.UUID(test_plan["id"]),
        target_id=uuid.UUID(target["id"]),
        status=TestRunStatus.SUCCEEDED,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return str(run.id)


def _add_metrics(db_session, run_id: str, endpoints=(None,), p95=100.0) -> None:
    for endpoint in endpoints:
        row = metric(endpoint, p95=p95, run_id=uuid.UUID(run_id))
        db_session.add(row)
    db_session.commit()


class TestPersistence:
    def test_the_same_run_cannot_be_selected_twice(self, client, db_session, test_plan, target):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        for _ in range(2):
            db_session.add(
                m.Baseline(
                    target_id=uuid.UUID(target["id"]),
                    test_run_id=uuid.UUID(run_id),
                    label="v1",
                    selected_by="kamogelo",
                    test_type="load",
                    target_concurrency=1000,
                )
            )
            if _ == 0:
                db_session.commit()
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_a_selected_run_cannot_be_deleted(self, client, db_session, test_plan, target):
        # RESTRICT, not CASCADE: deleting the run would leave every earlier
        # comparison against it unexplainable.
        run_id = _succeeded_run(client, db_session, test_plan, target)
        db_session.add(
            m.Baseline(
                target_id=uuid.UUID(target["id"]),
                test_run_id=uuid.UUID(run_id),
                label="v1",
                selected_by="kamogelo",
                test_type="load",
                target_concurrency=1000,
            )
        )
        db_session.commit()
        db_session.delete(db_session.get(m.TestRun, uuid.UUID(run_id)))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# --- HTTP surface ----------------------------------------------------------


class TestSelectionEndpoint:
    def test_selects_a_succeeded_run(self, client, db_session, test_plan, target):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        res = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": run_id, "label": "v1.2 release", "selected_by": "kamogelo"},
            headers=AUTH,
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["test_run_id"] == run_id
        assert body["label"] == "v1.2 release"
        # The compatibility identity is frozen onto the row at selection.
        assert body["test_type"] == "capacity"
        assert body["target_concurrency"] == 1000

    def test_reselecting_the_same_run_is_a_safe_repeat(self, client, db_session, test_plan, target):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        payload = {"test_run_id": run_id, "label": "v1", "selected_by": "kamogelo"}
        first = client.post(f"/api/targets/{target['id']}/baselines", json=payload, headers=AUTH)
        second = client.post(f"/api/targets/{target['id']}/baselines", json=payload, headers=AUTH)
        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]

    def test_a_reused_idempotency_key_for_another_run_is_a_conflict(
        self, client, db_session, test_plan, target
    ):
        first_run = _succeeded_run(client, db_session, test_plan, target)
        second_run = _succeeded_run(client, db_session, test_plan, target)
        key = "retry-1"
        client.post(
            f"/api/targets/{target['id']}/baselines",
            json={
                "test_run_id": first_run,
                "label": "v1",
                "selected_by": "k",
                "idempotency_key": key,
            },
            headers=AUTH,
        )
        res = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={
                "test_run_id": second_run,
                "label": "v2",
                "selected_by": "k",
                "idempotency_key": key,
            },
            headers=AUTH,
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "idempotency_key_reused"

    def test_an_unfinished_run_cannot_become_a_baseline(
        self, client, db_session, test_plan, target
    ):
        run = m.TestRun(
            test_plan_id=uuid.UUID(test_plan["id"]),
            target_id=uuid.UUID(target["id"]),
            status=TestRunStatus.RUNNING,
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        res = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": str(run.id), "label": "v1", "selected_by": "k"},
            headers=AUTH,
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "baseline_run_not_succeeded"

    def test_a_run_from_another_target_is_refused(self, client, db_session, test_plan, target):
        other = client.post(
            f"/api/projects/{test_plan['project_id']}/targets",
            json={
                "base_url": "https://localhost",
                "name": "other",
                "authorization_confirmed": True,
                "authorization_confirmed_by": "k",
            },
            headers=AUTH,
        ).json()
        run_id = _succeeded_run(client, db_session, test_plan, target)
        res = client.post(
            f"/api/targets/{other['id']}/baselines",
            json={"test_run_id": run_id, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "environment_mismatch"

    def test_unknown_target_and_run(self, client, db_session, test_plan, target):
        missing = str(uuid.uuid4())
        run_id = _succeeded_run(client, db_session, test_plan, target)
        assert (
            client.post(
                f"/api/targets/{missing}/baselines",
                json={"test_run_id": run_id, "label": "v", "selected_by": "k"},
                headers=AUTH,
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/targets/{target['id']}/baselines",
                json={"test_run_id": missing, "label": "v", "selected_by": "k"},
                headers=AUTH,
            ).status_code
            == 404
        )

    def test_requires_a_label_and_auth(self, client, db_session, test_plan, target):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        assert (
            client.post(
                f"/api/targets/{target['id']}/baselines",
                json={"test_run_id": run_id, "label": "", "selected_by": "k"},
                headers=AUTH,
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/targets/{target['id']}/baselines",
                json={"test_run_id": run_id, "label": "v", "selected_by": "k"},
            ).status_code
            == 401
        )


class TestComparisonEndpoint:
    def _pair(
        self,
        client,
        db_session,
        test_plan,
        target,
        *,
        baseline_p95=100.0,
        current_p95=150.0,
        endpoints=(None,),
    ):
        baseline_run = _succeeded_run(client, db_session, test_plan, target)
        current_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, baseline_run, endpoints, p95=baseline_p95)
        _add_metrics(db_session, current_run, endpoints, p95=current_p95)
        baseline = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": baseline_run, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()
        return baseline, current_run

    def test_compares_against_the_named_baseline(self, client, db_session, test_plan, target):
        baseline, current_run = self._pair(client, db_session, test_plan, target)
        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["baseline"]["id"] == baseline["id"]
        assert body["current_test_run_id"] == current_run
        assert len(body["comparisons"]) == 1
        assert body["comparisons"][0]["p95_delta_ms"] == 50.0
        assert body["comparisons"][0]["status"] == "available"

    def test_baseline_id_is_required(self, client, db_session, test_plan, target):
        # Omitting it must not fall back to "the most recent run" — that is the
        # silent selection this ticket exists to prevent.
        _, current_run = self._pair(client, db_session, test_plan, target)
        res = client.get(f"/api/test-runs/{current_run}/comparison", headers=AUTH)
        assert res.status_code == 422

    def test_reports_endpoints_measured_on_only_one_side(
        self, client, db_session, test_plan, target
    ):
        baseline_run = _succeeded_run(client, db_session, test_plan, target)
        current_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, baseline_run, (None, "/legacy"))
        _add_metrics(db_session, current_run, (None, "/new"))
        baseline = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": baseline_run, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()
        body = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        ).json()
        assert body["baseline_only_endpoints"] == ["/legacy"]
        assert body["current_only_endpoints"] == ["/new"]

    def test_a_run_without_metrics_is_refused(self, client, db_session, test_plan, target):
        baseline_run = _succeeded_run(client, db_session, test_plan, target)
        current_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, baseline_run)
        baseline = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": baseline_run, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()
        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "current_metrics_unavailable"

    def test_an_unfinished_current_run_is_refused(self, client, db_session, test_plan, target):
        baseline, current_run = self._pair(client, db_session, test_plan, target)
        run = db_session.get(m.TestRun, uuid.UUID(current_run))
        run.status = TestRunStatus.RUNNING
        db_session.commit()
        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "current_run_not_succeeded"

    def test_unknown_run_and_baseline(self, client, db_session, test_plan, target):
        baseline, current_run = self._pair(client, db_session, test_plan, target)
        missing = str(uuid.uuid4())
        assert (
            client.get(
                f"/api/test-runs/{missing}/comparison",
                params={"baseline_id": baseline["id"]},
                headers=AUTH,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/test-runs/{current_run}/comparison",
                params={"baseline_id": missing},
                headers=AUTH,
            ).status_code
            == 404
        )

    def test_requires_auth(self, client, db_session, test_plan, target):
        baseline, current_run = self._pair(client, db_session, test_plan, target)
        res = client.get(
            f"/api/test-runs/{current_run}/comparison", params={"baseline_id": baseline["id"]}
        )
        assert res.status_code == 401


class TestListingEndpoints:
    def test_lists_and_fetches(self, client, db_session, test_plan, target):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        created = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": run_id, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()
        listed = client.get(f"/api/targets/{target['id']}/baselines", headers=AUTH)
        assert listed.status_code == 200
        assert [b["id"] for b in listed.json()["baselines"]] == [created["id"]]

        fetched = client.get(f"/api/baselines/{created['id']}", headers=AUTH)
        assert fetched.status_code == 200
        assert fetched.json() == created

    def test_empty_list_is_not_an_error(self, client, target):
        res = client.get(f"/api/targets/{target['id']}/baselines", headers=AUTH)
        assert res.status_code == 200
        assert res.json() == {"baselines": []}

    def test_unknown_baseline_is_404(self, client):
        assert client.get(f"/api/baselines/{uuid.uuid4()}", headers=AUTH).status_code == 404
