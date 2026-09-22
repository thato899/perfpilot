"""Phase 2 state/budget contract regressions."""

from uuid import uuid4

from packages.schemas.python.agent_io import (
    ExperimentBudget,
    ExperimentState,
    InvestigationState,
    OrchestratorEvent,
    OrchestratorEventType,
)
from packages.schemas.python.entities import ExperimentStatus


def test_legacy_experiment_fixture_remains_valid() -> None:
    state = InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="investigating",
        experiments=[ExperimentState(id=uuid4())],
    )

    assert state.experiments[0].status is ExperimentStatus.PROPOSED
    assert state.experiments[0].hypothesis_id is None


def test_budget_and_event_contract_are_typed_and_orderable() -> None:
    event = OrchestratorEvent(
        sequence=2,
        type=OrchestratorEventType.EXPERIMENT_APPROVED,
        payload={"experiment_id": str(uuid4())},
    )
    state = InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="experimenting",
        experiment_budget=ExperimentBudget(
            max_experiments=2, consumed=1, remaining=1, exhausted=False
        ),
        experiments=[
            ExperimentState(
                id=uuid4(),
                hypothesis_id=uuid4(),
                variable_changed="db_pool_size",
                status=ExperimentStatus.QUEUED,
                sequence_index=0,
            )
        ],
        events=[event],
    )

    assert state.experiment_budget is not None
    assert state.experiment_budget.remaining == 1
    assert state.events[0].sequence == 2
    assert state.experiments[0].status is ExperimentStatus.QUEUED
