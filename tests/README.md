# tests

Cross-cutting test suites that don't belong to one package alone — primarily the end-to-end demo-scenario run described in [docs/testing/testing-strategy.md](../docs/testing/testing-strategy.md#end-to-end).

For an operator-run performance test against an authorized system, follow [startup.md](../startup.md); this directory covers tests of PerfPilot itself.

Package-local unit/integration tests live alongside their code (`apps/api/tests`, `agents/*/tests`, `packages/*/tests`) once implementation starts, per the same testing strategy doc. Not implemented yet.
