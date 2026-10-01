# Production AI reasoning (#70, #78, #79, #80)

The Python API and Celery worker use `packages/ai/runtime.py` for live reasoning.
`AI_PROVIDER_ENABLED=false` is the default and keeps local demos and CI deterministic.
Setting it to `true` makes the initial Test Planner call in the API process and
the Investigator and Reporting Agent calls in the worker use the selected
provider. A missing key, unavailable service, timeout, or invalid response
fails the investigation; the runtime never substitutes another provider or a
deterministic answer.

## Configuration

Copy `.env.example` to `.env` and set `AI_PROVIDER_ENABLED=true`,
`AI_PROVIDER=gemini|deepseek|ollama`, and optionally `AI_PROVIDER_MODEL`.
The defaults are `gemini-2.5-pro`, `deepseek-chat`, and `qwen3:8b` respectively.
`AI_MODEL_TEST_PLANNER`, `AI_MODEL_PERFORMANCE_INVESTIGATOR`, and
`AI_MODEL_REPORTING` override the model per specialist. Gemini requires
`GEMINI_API_KEY`; DeepSeek requires `DEEPSEEK_API_KEY`; Ollama requires no cloud
key. Secrets are read from the process environment, never from the database.
`AI_TIMEOUT_SECONDS` defaults to 60 and is limited to 1–180. Each response is
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

Prompts carry `2026-10-01.v1`, one typed request, the output JSON schema, and
the specialist instruction. Typed requests contain target descriptions and
journeys for planning; metric IDs, measured values, comparisons, thresholds,
and prior hypotheses for investigation; and persisted state plus canonical
capacity, regression, and key metrics for reporting. Credential-shaped fields
and URL query strings are removed before transmission. This means a journey
requiring a secret query parameter cannot be generated as an identical plan;
validation fails instead of disclosing the parameter. Target auth headers,
raw credentials, load-engineer execution data, and unrelated investigations
are never part of the request.

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
  AI_TIMEOUT_SECONDS=60 AI_MAX_OUTPUT_TOKENS=2048 \
  python -m packages.ai.smoke
```

Set provider and credentials for DeepSeek or Gemini. The command prints only
the validated result status and provider/model. It performs no load test.
For a Docker Desktop connectivity check, execute the same command in the
worker container with `docker compose exec worker python -m packages.ai.smoke`.
Live calls are excluded from normal CI. The local environment used for the
offline test suite has no Ollama model or cloud credentials, so a live smoke
result requires an operator to run the opt-in command.

Transport conventions follow the official [Gemini generateContent API](https://ai.google.dev/api/generate-content),
[DeepSeek JSON output guide](https://api-docs.deepseek.com/guides/json_mode/),
and [Ollama chat API](https://github.com/ollama/ollama/blob/main/docs/api.md).
