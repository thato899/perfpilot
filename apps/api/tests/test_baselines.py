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
from apps.api.scenario_identity import fingerprint
from packages.metrics.metrics import ComparisonStatus
from packages.schemas.python.entities import TestRunStatus

from .conftest import AUTH, m

TARGET_A = uuid.uuid4()
TARGET_B = uuid.uuid4()


def scenario(**overrides) -> dict:
    """A plausible canonical scenario document, overridable one field at a time."""
    base = {
        "test_type": "load",
        "target_concurrency": 100,
        "ramp_strategy": {"kind": "linear", "ramp_up_s": 60},
        "user_journeys": ["browse", "checkout"],
        "duration": {"total_s": 300},
        "stages": [
            {"duration_s": 60, "target": 50},
            {"duration_s": 240, "target": 100},
        ],
    }
    base.update(overrides)
    return base


def facts(**overrides) -> RunFacts:
    """RunFacts whose scenario agrees with its type and concurrency by default.

    Keeping them consistent matters: a helper that left the scenario document
    saying `load` while the fact said `stress` would make every ordering
    assertion below pass for the wrong reason.
    """
    document = overrides.pop("scenario", None)
    base = {
        "test_run_id": uuid.uuid4(),
        "target_id": TARGET_A,
        "status": TestRunStatus.SUCCEEDED,
        "test_type": "load",
        "target_concurrency": 100,
    }
    base.update(overrides)
    if document is None:
        document = scenario(
            test_type=base["test_type"],
            target_concurrency=base["target_concurrency"],
        )
    base["scenario"] = document
    base["scenario_fingerprint"] = overrides.get("scenario_fingerprint", fingerprint(document))
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

    @pytest.mark.parametrize(
        "field, value",
        [
            ("user_journeys", ["browse"]),
            ("user_journeys", ["checkout", "browse"]),
            ("stages", [{"duration_s": 300, "target": 100}]),
            ("duration", {"total_s": 2400}),
            ("ramp_strategy", {"kind": "step", "step_s": 30}),
        ],
    )
    def test_a_different_scenario_is_refused(self, field, value):
        # The gap this closes: all three of target, test type and concurrency
        # can agree while the two plans still describe substantially different
        # tests. A five-minute soak of one journey against a forty-minute ramp
        # through three produces a difference that is a change of experiment,
        # not a change in performance.
        failure = check_pair(facts(), facts(scenario=scenario(**{field: value})))
        assert failure.reason is IncompatibleReason.SCENARIO_MISMATCH
        assert failure.detail["differing_fields"] == [field]
        assert failure.detail["baseline_scenario_fingerprint"].startswith("v1:")

    def test_reordered_journeys_are_a_different_scenario(self):
        # Order is treated as significant everywhere, including here where an
        # argument could be made that it is incidental. A spurious refusal
        # names the field and is fixed by re-selecting; a spurious match
        # silently compares two different experiments. Only one self-corrects.
        failure = check_pair(
            facts(scenario=scenario(user_journeys=["browse", "checkout"])),
            facts(scenario=scenario(user_journeys=["checkout", "browse"])),
        )
        assert failure.reason is IncompatibleReason.SCENARIO_MISMATCH

    def test_every_differing_field_is_named(self):
        failure = check_pair(
            facts(),
            facts(scenario=scenario(duration={"total_s": 60}, user_journeys=["browse"])),
        )
        assert failure.detail["differing_fields"] == ["duration", "user_journeys"]

    def test_concurrency_is_reported_before_the_wider_scenario(self):
        # Both differ. "You changed the load" is the more useful sentence than
        # "something in the scenario changed", so the specific check runs first
        # even though concurrency is inside the fingerprint too.
        failure = check_pair(
            facts(target_concurrency=200),
            facts(target_concurrency=1000, scenario=scenario(user_journeys=["browse"])),
        )
        assert failure.reason is IncompatibleReason.CONCURRENCY_MISMATCH

    def test_an_unrecognised_identity_version_is_not_read_as_a_change(self):
        # A fingerprint computed under a rule this build does not know cannot
        # honestly be reported as "the scenario changed" — we have no way to
        # tell. Say what is actually true instead.
        stale = facts()
        stale = RunFacts(
            test_run_id=stale.test_run_id,
            target_id=stale.target_id,
            status=stale.status,
            test_type=stale.test_type,
            target_concurrency=stale.target_concurrency,
            scenario_fingerprint="v0:" + "0" * 64,
            scenario=stale.scenario,
        )
        failure = check_pair(stale, facts())
        assert failure.reason is IncompatibleReason.SCENARIO_IDENTITY_UNSUPPORTED
        assert failure.detail == {
            "baseline_scenario_identity_version": "v0",
            "supported_scenario_identity_version": "v1",
        }

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
                    scenario_fingerprint=fingerprint(scenario()),
                    scenario=scenario(),
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
                scenario_fingerprint=fingerprint(scenario()),
                scenario=scenario(),
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

    def test_a_reused_key_conflicts_even_when_its_run_is_already_a_baseline(
        self, client, db_session, test_plan, target
    ):
        # The ordering bug this pins: the (target, run) lookup used to return
        # 200 before the key was ever examined, so a caller retrying with a key
        # that meant a different run got a success and walked away believing
        # their key now referred to this one.
        first_run = _succeeded_run(client, db_session, test_plan, target)
        second_run = _succeeded_run(client, db_session, test_plan, target)
        key = "retry-1"
        for run_id, label, body_key in (
            (first_run, "v1", key),
            (second_run, "v2", None),
        ):
            payload = {"test_run_id": run_id, "label": label, "selected_by": "k"}
            if body_key is not None:
                payload["idempotency_key"] = body_key
            assert (
                client.post(
                    f"/api/targets/{target['id']}/baselines", json=payload, headers=AUTH
                ).status_code
                == 201
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
        assert res.json()["error"]["detail"]["existing_test_run_id"] == first_run

    def test_the_same_key_for_the_same_run_is_a_replay_not_a_conflict(
        self, client, db_session, test_plan, target
    ):
        run_id = _succeeded_run(client, db_session, test_plan, target)
        payload = {
            "test_run_id": run_id,
            "label": "v1",
            "selected_by": "k",
            "idempotency_key": "retry-1",
        }
        first = client.post(f"/api/targets/{target['id']}/baselines", json=payload, headers=AUTH)
        second = client.post(f"/api/targets/{target['id']}/baselines", json=payload, headers=AUTH)
        assert (first.status_code, second.status_code) == (201, 200)
        assert first.json()["id"] == second.json()["id"]

    def test_a_key_collision_that_loses_the_race_is_a_conflict_not_a_500(
        self, client, db_session, test_plan, target
    ):
        # The sequential path cannot reach the IntegrityError branch, so the
        # loser of the race is simulated by claiming the key underneath the
        # request — after its pre-check has passed. Before this, that branch
        # only looked for a (target, run) winner, found none, and re-raised
        # into a 500: the one outcome an idempotency key exists to prevent.
        first_run = _succeeded_run(client, db_session, test_plan, target)
        second_run = _succeeded_run(client, db_session, test_plan, target)
        key = "raced"

        import apps.api.routers.baselines as router_module

        real = router_module._by_key
        calls: list[int] = []

        def claim_the_key_after_the_precheck(db, target_id, idempotency_key):
            calls.append(1)
            if len(calls) == 1:
                # Pre-check: the key is still free, as it was for the winner.
                db_session.add(
                    m.Baseline(
                        target_id=uuid.UUID(target["id"]),
                        test_run_id=uuid.UUID(first_run),
                        label="winner",
                        selected_by="k",
                        test_type="load",
                        target_concurrency=1000,
                        scenario_fingerprint=fingerprint(scenario()),
                        scenario=scenario(),
                        idempotency_key=key,
                    )
                )
                db_session.commit()
                return None
            return real(db, target_id, idempotency_key)

        router_module._by_key = claim_the_key_after_the_precheck
        try:
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
        finally:
            router_module._by_key = real

        assert res.status_code == 409
        assert res.json()["error"]["code"] == "idempotency_key_reused"
        # Two calls means the pre-check passed and the IntegrityError branch
        # resolved it — not that the pre-check caught it and the branch was
        # never reached.
        assert len(calls) == 2

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

    def _replanned_run(self, db_session, test_plan: dict, target: dict, **changes) -> str:
        """A run under a *different* plan with the same type and concurrency.

        Cloned from the fixture's plan so only the fields under test differ —
        a hand-built plan would differ in ways that make the assertion pass for
        the wrong reason.
        """
        original = db_session.get(m.TestPlan, uuid.UUID(test_plan["id"]))
        clone = m.TestPlan(
            project_id=original.project_id,
            target_id=original.target_id,
            test_type=original.test_type,
            rationale=original.rationale,
            target_concurrency=original.target_concurrency,
            ramp_strategy=changes.get("ramp_strategy", original.ramp_strategy),
            user_journeys=changes.get("user_journeys", original.user_journeys),
            thresholds=original.thresholds,
            duration=changes.get("duration", original.duration),
            stages=changes.get("stages", original.stages),
            success_criteria=original.success_criteria,
            status=original.status,
        )
        db_session.add(clone)
        db_session.commit()
        db_session.refresh(clone)
        run = m.TestRun(
            test_plan_id=clone.id,
            target_id=uuid.UUID(target["id"]),
            status=TestRunStatus.SUCCEEDED,
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        return str(run.id)

    def test_a_different_scenario_sharing_an_endpoint_is_refused(
        self, client, db_session, test_plan, target
    ):
        # Same target, same test type, same concurrency, one shared endpoint —
        # everything the old rule checked. The plans still describe different
        # tests, and before the scenario identity this returned a comparison
        # whose deltas were a change of experiment dressed as a regression.
        baseline_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, baseline_run, ("/checkout",), p95=100.0)
        baseline = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": baseline_run, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()

        current_run = self._replanned_run(
            db_session,
            test_plan,
            target,
            user_journeys=["browse"],
            duration={"total_s": 2400},
        )
        _add_metrics(db_session, current_run, ("/checkout",), p95=180.0)

        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 409
        error = res.json()["error"]
        assert error["code"] == "scenario_mismatch"
        assert error["detail"]["differing_fields"] == ["duration", "user_journeys"]

    def test_the_same_scenario_under_a_different_plan_row_still_compares(
        self, client, db_session, test_plan, target
    ):
        # The other half of the rule: re-planning the identical scenario must
        # not disqualify a historical baseline, or every plan edit would strand
        # every baseline taken before it.
        baseline_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, baseline_run, (None,), p95=100.0)
        baseline = client.post(
            f"/api/targets/{target['id']}/baselines",
            json={"test_run_id": baseline_run, "label": "v1", "selected_by": "k"},
            headers=AUTH,
        ).json()

        current_run = self._replanned_run(db_session, test_plan, target)
        _add_metrics(db_session, current_run, (None,), p95=120.0)

        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 200, res.text
        assert res.json()["baseline"]["scenario_fingerprint"].startswith("v1:")

    def test_a_baseline_on_a_revoked_target_is_403_not_a_409(
        self, client, db_session, project, test_plan, target
    ):
        # Authorizing only the current run's target meant a caller could name a
        # baseline belonging to a target whose authorization had been revoked
        # and receive a 409 whose detail carried that target's id. The record
        # has to be authorized before it is read, not after.
        other = client.post(
            f"/api/projects/{project['id']}/targets",
            json={
                "base_url": "https://demo.perfpilot.local",
                "name": "second environment",
                "authorization_confirmed": True,
                "authorization_confirmed_by": "kamogelo",
            },
            headers=AUTH,
        ).json()
        other_plan = m.TestPlan(
            project_id=uuid.UUID(project["id"]),
            target_id=uuid.UUID(other["id"]),
            test_type="load",
            rationale="second environment",
            target_concurrency=1000,
            ramp_strategy={"kind": "linear"},
            user_journeys=["browse"],
            thresholds={},
            duration={"total_s": 300},
            stages=[],
            success_criteria=[],
            status="approved",
        )
        db_session.add(other_plan)
        db_session.commit()
        db_session.refresh(other_plan)
        other_run = m.TestRun(
            test_plan_id=other_plan.id,
            target_id=uuid.UUID(other["id"]),
            status=TestRunStatus.SUCCEEDED,
        )
        db_session.add(other_run)
        db_session.commit()
        db_session.refresh(other_run)
        foreign_baseline = client.post(
            f"/api/targets/{other['id']}/baselines",
            json={"test_run_id": str(other_run.id), "label": "elsewhere", "selected_by": "k"},
            headers=AUTH,
        ).json()

        revoked = db_session.get(m.Target, uuid.UUID(other["id"]))
        revoked.authorization_confirmed = False
        db_session.commit()

        current_run = _succeeded_run(client, db_session, test_plan, target)
        _add_metrics(db_session, current_run, (None,))
        res = client.get(
            f"/api/test-runs/{current_run}/comparison",
            params={"baseline_id": foreign_baseline["id"]},
            headers=AUTH,
        )
        assert res.status_code == 403, res.text
        assert other["id"] not in res.text

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
