# P2-UI-1: Investigation timeline and run-state visualization

Issue #37 renders the ordered event history that issue #35 persists. It adds
no state machine, no client-side progression and no second source of truth:
every row on screen corresponds to one `investigation_event` the server wrote.

The contract it consumes is [p2-api-2-investigation-state.md](p2-api-2-investigation-state.md),
whose consumer note for this ticket is the whole design brief — *"consume
`experiment_budget`, typed statuses, stable entity IDs, and ordered `events`;
do not infer timeline order from array position."*

## Where the pieces live

| File | Responsibility |
|---|---|
| `apps/web/src/lib/investigation-events.ts` | Pure mapping: server event → renderable entry, ordering, gap detection |
| `apps/web/src/components/dashboard/investigation-timeline.tsx` | Presentation, including every loading/empty/stale/error/terminal state |
| `apps/web/src/lib/polling.ts` | Poll interval, error budget, staleness window |
| `apps/web/src/app/investigations/[id]/page.tsx` | Owns the poll loop and passes state down |

## Event mapping

Each of the fourteen types in `InvestigationEventType` has a label and a coarse
phase used for grouping:

| Phase | Event types |
|---|---|
| planning | `investigation_created` |
| execution | `test_run_queued`, `test_run_started`, `test_run_completed`, `experiment_started`, `experiment_completed` |
| analysis | `finding_recorded`, `hypothesis_recorded`, `experiment_proposed` |
| approval | `experiment_approved` |
| reporting | `recommendation_recorded`, `report_persisted` |
| control | `budget_exhausted`, `continue_requested` |

Three rules govern the mapping, and all three exist to stop the UI asserting
more than the server said:

1. **A detail line is only rendered when the payload carries the field it
   describes.** `test_run_queued` says "Queued as the baseline run" only when
   `payload.kind` is present. There is no default sentence, because a default
   sentence is a fabricated one.
2. **An unrecognised event type is rendered, not dropped.** It gets its
   sequence, its timestamp and a humanised label, plus a visible
   "unrecognised event type" marker. Dropping it would leave a hole in the
   history with nothing to indicate anything was missing — the worst of the
   available options.
3. **Related IDs are read from an explicit field list**, not by pattern-matching
   `*_id`. A field renamed on the server shows up as a missing ID rather than
   as a silently reinterpreted one.

### Ordering

`toTimeline()` sorts on `sequence`, deduplicates by event ID, and falls back to
the event ID when two events share a sequence.

Ordering by `sequence` rather than array position is not defensive
over-engineering; the recorded order genuinely is not the order the lifecycle
prose implies. In a real captured run, `finding_recorded` (#4) precedes
`test_run_completed` (#5). A UI that reasoned about what "should" come next
would present that run incorrectly.

Deduplication matters because Celery is at-least-once and a reconnect can
overlap an in-flight poll; the same event arriving twice must not read as two
transitions.

### Gaps

`hasSequenceGap()` is true when the sequences are not `1..n` contiguous. The
timeline then says the history is incomplete rather than presenting a partial
history as the whole story. A short history is not a gap — a run that failed at
`test_run_started` is still `1,2,3`, and flagging that would cry wolf on every
failed investigation.

### What is deliberately *not* derived from events

The "Now:" line comes from `investigation.status`, not from the last event.
The status column is what the Orchestrator owns and writes; the last event is
merely the most recent thing recorded. Mid-run those can disagree, and the
status is the one the backend treats as authoritative.

With one exception, which is worth spelling out because the status name is
misleading. `experimenting` does **not** mean an approved experiment is
running. `Orchestrator.continue_investigation` sets it together with
`INVOKE_TEST_PLANNER`, so it means "an experiment is being worked out"; human
approval is a separate boundary (`POST /api/investigations/{id}/experiments`)
that security-model.md requires before any additional load is generated. At
that point the experiment may only be *proposed*, with no follow-up TestRun
and no budget consumed.

So the wording for that stage is read from the persisted `experiments[]` rows,
which carry the real lifecycle, taking the most advanced one:

| Experiment rows | Wording |
|---|---|
| any `running` | Running an approved experiment |
| any `queued` | Approved experiment queued |
| any `approved` | Experiment approved, waiting to start |
| any `proposed` | Experiment proposed, waiting for approval |
| none, or all terminal | Working out the next experiment |

An earlier revision labelled the bare status "Running an approved experiment",
which asserted both an approval and load generation that may not have
happened — the exact invented progression this ticket forbids.

Likewise, **a failed run produces no `test_run_completed` event** —
`apps/api/tasks.py` appends that only on the success path. The timeline shows
the history ending where it really ended and reports the failure from the
status. It does not synthesise the missing event. This is pinned by a contract
test.

## Polling, refresh and reconnect

Polling lives in the page, not the component, and is unchanged from Phase 1
apart from the additions below: `POLL_INTERVAL_MS` 1500ms, stopping at a
terminal investigation status or a terminal run status, and giving up after
`MAX_CONSECUTIVE_POLL_ERRORS` (3) consecutive failures.

- **Refresh** re-fetches and re-sorts from scratch. Because ordering is derived
  from `sequence` and React keys are the server's event UUIDs, the rendered
  order is identical across reloads.
- **Reconnect** shows an explicit "Reconnecting…" notice while retries remain,
  separate from the error text. The user is told we are still trying, not just
  that something broke.
- **Stale** appears once `STALE_AFTER_MS` (four poll intervals) has elapsed
  since the last successful poll **while updates are still expected**. The last
  known history stays on screen — it is real data, just not current, and that
  is a different claim from either hiding it or implying it is live.

  Staleness is suppressed entirely once the investigation reaches `complete` or
  `failed`. Polling stops at a terminal status by design, so a clock that kept
  running would eventually put "It may be out of date" on a final result that
  is never going to change, directly contradicting the terminal notice beside
  it. A terminal result is finished, not stale. The clock itself also stops, so
  a completed page is not left ticking.

Staleness is derived during render from two pieces of state (`lastUpdatedAt`
and a `now` clock ticked by an interval) rather than by calling `Date.now()`
in the render body. Beyond the purity lint, the reason is behavioural: a value
computed during render is only recomputed when React re-renders, which happens
when a poll *succeeds*. The screen would never be marked stale at the one
moment it matters — when polling has given up entirely and nothing is
re-rendering at all.

Read retries are bounded and idempotent; the timeline issues no mutations, so
there is nothing for a reconnect to duplicate.

## Accessibility states

These are implemented by the timeline card and rendered by the page in every
case, including before the first response arrives. The page deliberately has
**no early return** while `investigation` is null: an earlier revision returned
a bare paragraph in that case, so the loading, first-failure and reconnecting
states existed only in the component's own tests and never reached a browser.
The cards that genuinely require a loaded investigation stay conditional; the
timeline does not.


- The event list is an `<ol>` labelled by the card heading, so it is reachable
  as *"Investigation timeline, list"*.
- Each row's ordinal carries `aria-label="Sequence N"`, so a screen reader
  announces "Sequence 4" rather than "hash four".
- Timestamps are `<time dateTime="…">` with an ISO attribute and a UTC-rendered
  label. UTC rather than `toLocaleString` so the rendering does not depend on
  the viewer's machine — and so component tests do not depend on the runner's
  timezone.
- The current-action line is `aria-live="polite"`. It updates on every poll;
  `assertive` would interrupt a screen-reader user mid-sentence.
- Failures use `role="alert"`; stale, reconnecting, gap and loading notices use
  `role="status"`. The polling error is rendered **once**, by this card — an
  earlier revision also rendered it on the page, which produced two identical
  alerts and announced the same failure twice.

## Fixtures and the test boundary

Tests are in three layers, and only the first uses invented data:

| Layer | File | Data |
|---|---|---|
| Unit | `lib/__tests__/investigation-events.test.ts` | Hand-written events, for mapping and ordering edge cases |
| Component / a11y | `components/dashboard/__tests__/investigation-timeline.test.tsx` | Hand-written state, one case per required UI state |
| **Page** | `app/investigations/[id]/page.states.test.tsx` | Mocked API, driving the real page through each state |
| Contract | `lib/__tests__/investigation-events.contract.test.ts` | **Real captured server responses** |

The page layer is not redundant with the component layer, and the reason is
the bug that produced it: the component's loading, first-failure and
reconnecting states were fully tested in isolation while the page returned
early and rendered none of them. A component test cannot catch a caller that
never renders the component. These cover initial loading, a first request that
fails and retries, recovery, an exhausted retry budget, staleness during a
genuine non-terminal outage, and the absence of staleness on both terminal
statuses.

The two files in `lib/__tests__/fixtures/` are the verbatim body of
`GET /api/investigations/{id}`, captured from a running `apps/api` against real
Postgres, real Redis and a real Celery worker. They are not edited by hand;
regenerating them means running that flow again. A hand-written fixture only
proves the mapper agrees with my reading of the contract doc — these prove it
agrees with what the server actually sends.

Fixtures are test-only. Nothing under `src/lib/fixtures.ts` or
`src/lib/mock-api.ts` feeds the timeline; the component renders server state or
an explicit empty state.

## Verification performed

Beyond the suite, this slice was checked against a real stack — apps/api on
real Postgres with a real Celery worker, and `next dev` driving a real browser:

- A completed investigation renders all six of its real events in recorded
  order, with the terminal notice and the real experiment budget.
- A failed investigation renders its three real events and reports the failure,
  without inventing a completion.
- Reloading the page produces an identical order.
- Killing the API under a polling page produces, in order: the reconnecting
  notice, the error text, then the stale notice naming the last good poll —
  with the history retained throughout. No console errors.

That browser pass predates review feedback and did not cover three cases it
should have: the experimenting wording, terminal staleness, and the page's own
first-load and reconnect states. Those are now covered by the page-level suite
listed above. No fresh browser run is claimed for them.
