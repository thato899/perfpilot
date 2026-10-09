# Production AI reasoning (#70, #78, #79, #80)

For the full operator workflow, start with [startup.md](../../startup.md); this document covers live provider configuration and evaluation.

The Python API and Celery worker use `packages/ai/runtime.py` for live reasoning.
`AI_PROVIDER_ENABLED=false` is the default and keeps local demos and CI deterministic.
Setting it to `true` makes the initial Test Planner call in the API process and
the Investigator and Reporting Agent calls in the worker use the selected
provider. A missing key, unavailable service, or timeout can fail the
investigation. Invalid planner or investigator output can also fail it. If the
Reporting Agent's output still fails structured validation after retry, the
worker persists a grounded deterministic report and records the fallback in
the AI audit. The runtime never silently switches providers.

## Configuration

Copy `.env.example` to `.env` and set `AI_PROVIDER_ENABLED=true`,
`AI_PROVIDER=gemini|deepseek|ollama`, and optionally `AI_PROVIDER_MODEL`.
Local Python configuration reads the repository-root `.env`; explicit process
environment variables take precedence. Docker Compose passes `.env` values into
the API and worker processes. Keep `.env` untracked.
The defaults are `gemini-3.5-flash-lite`, `deepseek-chat`, and `qwen3:8b`
respectively. [Gemini 2.5 Pro access is limited for newer projects](https://ai.google.dev/gemini-api/docs/deprecations/);
select it explicitly with `AI_PROVIDER_MODEL=gemini-2.5-pro` if your key
supports it.
`AI_MODEL_TEST_PLANNER`, `AI_MODEL_PERFORMANCE_INVESTIGATOR`, and
`AI_MODEL_REPORTING` override the model per specialist. Gemini requires
`GEMINI_API_KEY`; DeepSeek accepts `DEEPSEEK_API_KEY` (preferred) and the
existing `DEEPSEEK_API` name; Ollama requires no cloud key. API keys are sent
only in provider authorization headers and are never persisted in the database.
`AI_TIMEOUT_SECONDS` defaults to 60 and is limited to 1–180 for Gemini and
DeepSeek. Ollama uses `OLLAMA_TIMEOUT_SECONDS`, which defaults to 600 seconds
and is limited to 1–900 for slower local inference. Each response is
limited to `AI_MAX_OUTPUT_TOKENS` (default 2048, range 128–8192), a 128 KB
request, and a 256 KB response. Validation retries at most once; provider
transport failures are not retried. At most two model requests are made per
specialist call.

For host-run Python, start Ollama and install the model with
`ollama pull qwen3:8b`, then use `OLLAMA_BASE_URL=http://localhost:11434`.
For Docker Desktop, Compose sets `OLLAMA_BASE_URL` to
`http://host.docker.internal:11434` in both API and worker containers. The
host Ollama service must listen on an interface
reachable from Docker Desktop. If it is unreachable or the model is absent,
the call fails explicitly. `OLLAMA_WORKER_BASE_URL` overrides the Compose
worker address. No model download occurs in CI.

## Data and validation

Prompts carry `2026-10-02.v2`, one typed request, the output JSON schema, and
the specialist instruction. Typed requests contain target descriptions and
journeys for planning; metric IDs, measured values, comparisons, thresholds,
and prior hypotheses for investigation; and persisted state plus canonical
capacity, regression, and key metrics for reporting. Credential-shaped fields,
URL userinfo, and URL query strings are removed before transmission. This
means a journey
requiring a secret query parameter cannot be generated as an identical plan;
validation fails instead of disclosing the parameter. Target auth headers,
raw credentials, load-engineer execution data, and unrelated investigations
are never part of the request. The investigator prompt names the exact metric
and infrastructure IDs allowed in evidence references. The report prompt
spells out the exact canonical fields, finding IDs, and evidence citation
format required by the existing validators.

The existing specialist boundaries parse the response and retry once on schema
or semantic failure. Planner journeys and thresholds must match input.
Investigator observations and hypotheses must cite supplied metric or
infrastructure IDs. Report capacity, regression, and key metrics must match
deterministic values, and findings and evidence references must match the
persisted investigation. The model cannot authorize a target, raise load
ceilings, approve an experiment, recalculate metrics, or change lifecycle
state. Only validated typed output reaches persistence. `AIExecution` records
provider, model, prompt version, specialist, and outcome as references; it
does not store prompts, response bodies, or keys.

Provider transport and quota errors report a sanitized provider/status code.
Invalid structured output reports field locations and error types, without
echoing response bodies. Failed investigations remain marked failed, while a
completed load test retains its measured success status. An initial planner
failure returns a `503 ai_generation_failed` error with the investigation ID;
the worker records the failure outcome in `AIExecution` for later calls.

## Verification

Credential-free checks:

```sh
python -m pytest packages/ai/test_runtime.py packages/validation agents -q
python -m ruff check packages/ai apps/api agents packages/validation
```

Opt-in live smoke (three known fixtures, at most two requests per case):

```sh
AI_LIVE_SMOKE=1 AI_PROVIDER_ENABLED=true AI_PROVIDER=ollama \
  OLLAMA_TIMEOUT_SECONDS=600 AI_MAX_OUTPUT_TOKENS=2048 \
  python -m packages.ai.smoke
```

Use `--agent test_planner`, `--agent performance_investigator`, or
`--agent reporting` to run one fixture independently. The runner reports
elapsed time and a sanitized failure reason for each selected case. The
investigator fixture additionally requires a high-severity threshold-breach
finding, an observation, database-pool evidence, and an experiment whose
expected signal names p95.

For cloud evaluations, configure the relevant API key in the process
environment or in the ignored repository-root `.env`. Do not put a key on the
command line. Each command uses the three checked-in fixtures, a 60-second
timeout and 2048-output-token limit per request, and at most one validation
retry per fixture (six requests maximum):

```sh
AI_LIVE_SMOKE=1 AI_PROVIDER_ENABLED=true AI_PROVIDER=deepseek \
  AI_TIMEOUT_SECONDS=60 AI_MAX_OUTPUT_TOKENS=2048 \
  python -m packages.ai.smoke

AI_LIVE_SMOKE=1 AI_PROVIDER_ENABLED=true AI_PROVIDER=gemini \
  AI_TIMEOUT_SECONDS=60 AI_MAX_OUTPUT_TOKENS=2048 \
  python -m packages.ai.smoke
```

The command prints only validated result status, elapsed time, and
provider/model. It performs no load test. Run the three specialist fixtures
for each provider and record any validation or provider failure without
recording prompts, responses, or keys.
For a Docker Desktop connectivity check, execute the same command in the
worker container with `docker compose exec worker python -m packages.ai.smoke`.
Live calls are excluded from normal CI. On 2026-10-01, the local
`qwen3:8b` service returned valid JSON through `AIService` for a small
adapter request, and the Docker worker reached the host service at
`host.docker.internal:11434`. The full planner fixture timed out on this
CPU-only host with both 60 and 180 second request bounds; no complete
three-specialist local evaluation is claimed. On 2026-10-02, a repeat on the
same CPU host with a 180-second per-request bound and 2048 output-token limit
validated the planner fixture. The investigator then timed out, and an
independent reporting fixture timed out after 182.1 seconds of wall time.
With the Ollama-specific 600-second bound on 2026-10-02, the investigator
finished in 339.0 seconds and reporting finished in 525.3 seconds. Both
responses failed semantic validation on their two allowed attempts, so neither
was accepted. Prompt version `2026-10-02.v2` then added explicit evidence and
pass-through instructions. With the same `qwen3:8b` model, 600-second bound,
and 2048 output-token limit, independently selected planner, investigator,
and reporting fixtures all validated in 185.3, 147.9, and 261.0 seconds,
respectively. A stricter investigator fixture check also passed in 159.1
seconds, confirming threshold interpretation and a grounded, falsifiable
experiment. The cases used known fixtures and made no load-test calls.
On 2026-10-08, after PR #89 merged as `c081fa0`, the DeepSeek smoke passed all
three fixtures using `deepseek-chat`, 60-second requests, and 2048 output
tokens: planner 2.0s, investigator 4.4s, reporting 3.3s. An earlier post-merge
full attempt had planner validate in 2.2s and investigator fail after two
attempts in 9.4s (`InvestigatorValidationError`); reporting was not reached. A
standalone investigator fixture later validated in 4.2s. The final full pass
completed and issue #79 is labeled `status:done` and closed. These results are
sanitized; prompts, responses, and credentials were not recorded.

On 2026-10-08, on `main` at `11239d2`, the Gemini smoke with an explicitly
selected `gemini-3.5-flash-lite`, 60-second requests, and 2048 output tokens
validated planner in 12.2s, investigator in 3.9s, and reporting in 2.8s.
The prior default `gemini-2.5-pro` returned HTTP 404 for planner in 1.4s.
Two bounded `gemini-3.8-flash` runs reached HTTP 503 after one or two fixtures,
and `gemini-3.6-flash` returned HTTP 503 on planner. These outcomes are retained
on [issue #80](https://github.com/thato899/perfpilot/issues/80). No automatic
provider/model fallback or transport retry occurred. #80 is
`status:done` and closed. On the default-model branch, the same bounded smoke
without `AI_PROVIDER_MODEL` validated planner in 1.9s, investigator in 2.7s,
and reporting in 3.4s. PR #91 passed CI, received Kamogelo's affected-owner
approval, and merged as `dc4f42a`. On merged `main`, the bounded three-fixture
smoke validated planner in 2.6s, investigator in 2.3s, and reporting in 4.0s.
Post-merge focused tests (72), Ruff, and Black passed. GitHub CI `py-test`
passed with Postgres. On 2026-10-08, the Docker Linux engine was started and
the local database-backed API suite passed 128 tests on a separate temporary
database after isolating tests from the developer's live-provider `.env`. The
temporary database was removed; [PR #92](https://github.com/thato899/perfpilot/pull/92)
tracks review and merge of the test-isolation change.

## Run and demo with Gemini

1. In the ignored root `.env`, set `GEMINI_API_KEY`, `AI_PROVIDER_ENABLED=true`,
   and `AI_PROVIDER=gemini`. Optionally set `AI_PROVIDER_MODEL` to an available
   model. Keep `AI_TIMEOUT_SECONDS=60` and `AI_MAX_OUTPUT_TOKENS=2048` for the
   documented evaluation. `GEMINI_API` is not a configuration name.
2. From the repository root, run the three fixtures. In PowerShell, use
   `$env:AI_LIVE_SMOKE='1'; python -m packages.ai.smoke`. It prints only
   provider/model, validated status, elapsed time, or a sanitized failure.
3. Start Docker Desktop's Linux engine. From `infrastructure/docker`, run
   `docker compose --profile all up -d --build --force-recreate`, then
   `docker compose exec api python -m alembic -c apps/api/alembic.ini upgrade head`.
   Run `docker compose port api 8000` and `docker compose port web 3000` to
   find the published host ports; local Compose overrides can change them.
   Check `/health` on the API host port and open the web host port in a browser.
4. Register a controlled target you own or are authorized to test. Its host
   must appear in `ALLOWED_TARGET_HOSTS` and be reachable from the worker/k6
   container. Start a small investigation in the dashboard (for example,
   1 normal and 5 peak concurrent users), then show its measured results,
   findings, and report. The [reference DB-pool scenario](../demo-scenario.md)
   is illustrative and has not been reproduced locally.
5. To show provider metadata without exposing prompt or response content, run
   `docker compose exec db psql -U perfpilot -d perfpilot -c "SELECT agent, provider, model, decision FROM ai_execution ORDER BY timestamp DESC LIMIT 3;"`
   from `infrastructure/docker`.

Transport conventions follow the official [Gemini generateContent API](https://ai.google.dev/api/generate-content),
[DeepSeek JSON output guide](https://api-docs.deepseek.com/guides/json_mode/),
and [Ollama chat API](https://github.com/ollama/ollama/blob/main/docs/api.md).
