# agents/test-planner

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

Turns target/traffic information into a structured `TestPlan` and recommends the right test type (load/stress/spike/endurance/capacity/baseline/regression) for the stated objective.

Implemented in `test_planner.py`. It validates required traffic and journey
inputs, preserves supplied requirements, emits staged capacity plans, and
isolates an explicitly requested experiment variable.
