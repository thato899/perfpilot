# Reference Demo Scenario

This scenario is the reference use case the architecture is designed around. Every agent contract, the data model, and the API were written with this walkthrough in mind — if a design decision seems arbitrary elsewhere in the docs, check whether it's actually shaped by this scenario.

## Setup

An e-commerce application (team-owned, controlled — see [security-model.md#sandboxing](security/security-model.md#sandboxing)) expects a flash sale.

```text
Normal traffic:  100 concurrent users
Peak traffic:    1,000 concurrent users
Objective:       determine sustainable capacity
```

## What PerfPilot does

1. **Target registered** — the demo app's URL, confirmed owned, added to the allow-list (see [security-model.md](security/security-model.md#target-authorization)).
2. **Investigation created** with `objective: determine_capacity` and the expected traffic above.
3. **Test Planner** recommends a **capacity test** (not a flat load test — the objective is "find the ceiling," which is what a capacity test type is for; see [test-planner.md](agents/test-planner.md)), with a step ramp:

   ```text
   10 → 50 → 100 → 250 → 500 → 750 → 1000 (concurrent users)
   ```

4. **Load Engineer** generates and runs the corresponding k6 script, stage by stage.
5. **Performance Investigator** watches each stage's metrics against the previous:
   - 10 → 500 users: healthy, thresholds met.
   - 750 users: **anomaly** — p95 latency rises from 420ms to 2.8 seconds.
6. Investigator forms a hypothesis:

   ```text
   Observed:    p95 latency increased significantly at ~750 concurrent users.
   Hypothesis:  Database connection pool contention.
   Evidence:    DB connection pool utilization reached 98%.
   Confidence:  60% (below the 80% continuation threshold — see orchestrator.md)
   Recommended experiment: repeat the 750-user stage with the DB connection
                            pool size doubled (50 → 100) and compare p95.
   ```

7. **Orchestrator** requests a follow-up plan isolating exactly that variable; **Test Planner** produces it; **Load Engineer** executes it.
8. **`packages/metrics`** deterministically compares the experiment's p95 against the 750-user baseline: **latency improves ~42%**.
9. **Investigator** re-analyzes: hypothesis confidence rises to **87%**, now above threshold — `hypothesis_supported`.
10. **Orchestrator** decides the investigation is sufficient and invokes the **Reporting Agent**.

## Resulting report (illustrative)

```text
Executive summary:
  The application remained healthy up to approximately 500 concurrent users.
  Performance degradation began around 750 concurrent users.

Capacity:
  Estimated sustainable capacity:   ~620 concurrent users
  Recommended operating capacity:   500 concurrent users

Primary bottleneck:
  Database connection contention
  Confidence: 87%

Recommendations:
  1. Investigate database connection pool saturation.
  2. Inspect slow queries.
  3. Review missing indexes.
  4. Move non-critical post-processing to asynchronous workers.
```

## Why this scenario specifically

- It exercises the **entire** lifecycle once, end to end (see [data-flow.md](architecture/data-flow.md)), which is exactly the MVP bar (see [roadmap.md](roadmap.md)) — nothing in the demo requires functionality beyond one full loop with one experiment.
- The bottleneck (DB connection pool contention) is a realistic, well-understood failure mode that's straightforward to actually reproduce in a small demo app — the team doesn't need a genuinely complex production system to make the investigation loop show real signal.
- It gives every agent a concrete moment to shine: Test Planner picking `capacity` over `load`, Load Engineer running a multi-stage ramp, Investigator producing a *falsifiable, testable* hypothesis (not just "latency is bad"), and Reporting Agent turning that into a number a stakeholder can act on ("620 users, 500 recommended").
