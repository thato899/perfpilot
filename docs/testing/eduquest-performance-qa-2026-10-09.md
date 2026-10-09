# EduQuest performance QA — 9 October 2026

## Scope and method

The supplied QA tutor account signed in through `https://eduquesttutors.co.za/login.php` and reached the tutor dashboard. Credentials are not stored in this repository or in the k6 script. Tests were read-only after login: each k6 virtual user fetched the login form, submitted its CSRF token and the supplied QA credentials once, then repeatedly fetched `/tutor/dashboard.php` with a one-second pause. The script retained cookies across iterations. Raw summaries and the temporary script are in the gitignored `infrastructure/docker/k6/results/` directory. k6 was v0.57.0.

The 1 and 10 virtual-user tests used a 10-second constant load. The 100 virtual-user test ramped from 0 to 100 over 30 seconds, then planned a 20-second hold. It stopped early after a threshold breach. The check required HTTP 200 and the expected tutor dashboard content; the HTTP error threshold was 5%.

A preliminary 100-user simultaneous-start run lasted only 10 seconds. It made 119 requests but reached no dashboard checks: login setup consumed the window. k6 exited 0 because a threshold with no matching samples did not fail. That result was discarded as inconclusive. The ramped run below is the measured 100-user attempt.

## Authenticated read-only results

| Virtual users | Total HTTP requests | Dashboard checks | Dashboard checks passing | Dashboard p95 | Dashboard p99 | Dashboard HTTP error rate | k6 exit |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 10 | 100% | 43.23 ms | 49.33 ms | 0% | 0 |
| 10 | 100 | 80 | 100% | 200.04 ms | 201.59 ms | 0% | 0 |
| 100 | 2,596 | 501 | 87.03% | 6,017.73 ms | 11,129.20 ms | 12.97% | 99 |

The 100-user run reached 100 virtual users, but only 30 login checks succeeded and 63 failed during its ramp. Thus this is evidence that the attempted 100-user workload degraded, **not** proof that 100 independently authenticated tutor sessions were sustained. The aggregate k6 summary does not identify the failing HTTP status codes, and no server-side logs or resource measurements were available to establish the cause.

The three measured rows are also available as [CSV](eduquest-performance-results-2026-10-09.csv). These are results from a separate authenticated, read-only k6 script, not from PerfPilot's browser investigation. The 1- and 10-user tests held constant load for 10 seconds; the 100-user attempt ramped and stopped early. Compare the direction of the measurements, but do not treat the three rows as an identical-duration capacity curve.

After this run, both the QA browser and separate requests from the test machine received connection resets from EduQuest. This may be an outage or a network protection block affecting the test machine. No further external load was sent. Site-wide availability was not established.

## Testable hypotheses and evidence needed

The observed finding is **degradation during the attempted 100-user workload**: dashboard p95 rose from 200.04 ms at 10 VUs to 6,017.73 ms in the ramped attempt, while dashboard HTTP errors rose from 0% to 12.97%. This is a measured association across different load profiles. No causal root cause is confirmed.

| Candidate hypothesis | Supporting observation | What would distinguish it | Current confidence |
|---|---|---|---|
| Application or database saturation increases queueing and timeouts as load rises. | Dashboard latency and errors grew during the high-load attempt. | Correlate per-minute request latency and failure status with CPU, memory, worker saturation, DB pool wait time, and slow queries. Repeating a short, approved ramp with these signals should show the bottleneck rising before latency. | Low: no server telemetry was available. |
| Edge protection or rate limiting blocked the test source. | Login checks failed during the ramp, and this test machine later received connection resets. | Inspect edge/WAF/access logs for blocks, challenges, 403/429 responses, and source-IP rules at the same timestamps. Check an independent client only after the owner confirms the site is healthy. | Low: resets could also result from an outage or network fault. |
| Concurrent use of one QA tutor account disrupted login sessions. | Only 30 login checks succeeded and 63 failed during the ramp, despite reaching 100 VUs. | Review authentication logs for session replacement, token/CSRF failures, and login throttling. If approved, repeat with distinct disposable accounts and compare login success separately from dashboard latency. | Low: the aggregate summary lacks failure status codes. |

The next investigation should collect HTTP status distribution, login versus dashboard failures, per-stage metrics, application/database telemetry, and edge logs. It should define a stop condition before load begins. Until those signals are available, the report should present these as competing hypotheses and leave the root cause **undetermined**.

## PerfPilot behavior observed

PerfPilot's live 1-user investigation measured `/login.php` with p95 35.14 ms, p99 75.67 ms, throughput 0.98 requests/s, and 0% HTTP errors. Its TestRun succeeded, but the investigation failed in reporting: the live reporting provider twice returned a recommendation without a matching hypothesis. The schema validation correctly rejected the ungrounded recommendation; the system then had no report to show. A later code change added a deterministic report fallback, verified on a controlled local target. PerfPilot's current generator performs a GET of one journey path and cannot run this authenticated tutor workflow. The local `.env` currently sets `MAX_VIRTUAL_USERS=1` and `MAX_TEST_DURATION_SECONDS=120`; the built-in 100-user plan requests 180 seconds. This explains the safety-limit rejection, and no PerfPilot 10- or 100-user investigation ran against EduQuest.

In a separate, bounded AI evaluation using credential-free dashboard aggregates from the 1- and 100-VU summaries, the Performance Investigator marked the degradation `CRITICAL`, cited the measured p50/p95, throughput, and error rate, and returned no causal hypothesis. This was a sound refusal to invent a server-side cause without infrastructure data. It called the latter result "100-user concurrency" because the metric contract records launched VUs but has no field for successful authenticated sessions; only 30 login checks succeeded in that run. The current reasoning path therefore cannot qualify that distinction on its own. This evaluation did not execute a load test or persist an investigation.

## Changes made during this investigation

- Keep a completed k6 summary when k6 exits 99 for a threshold breach; still reject other process errors and missing summaries.
- Pause one second between generated requests and stop early after persistent HTTP error-threshold failures.
- Record the actual maximum virtual users observed when a run ends early; allow k6's graceful stop time in the process timeout.
- If an AI report fails structured validation after retry, persist the deterministic grounded report and audit the fallback instead of failing the completed investigation.

These changes have focused automated coverage. A separate controlled local end-to-end investigation completed after the worker restart: the one-user k6 run succeeded, planner/investigator/reporting AI executions were audited as validated, and a report was persisted. This verified the worker path without sending more traffic to EduQuest.

A second local k6 smoke deliberately breached a 0.001 ms p95 threshold. k6 exited 99, and the production Load Engineer adapter returned `succeeded` with a parsed p95 of 1.383 ms and observed concurrency 1. This confirms that a completed threshold breach now remains usable evidence.

## Follow-up: 100% error report for investigation `8bf039e9-242e-451d-b07c-1524561a7c77`

The operator's later 1-user PerfPilot investigation saved run `68879c46-614a-439d-93b8-82e6b32a3974`. Its plan contained only `/`, and the generated traffic was an unauthenticated GET to `https://eduquesttutors.co.za/`. The k6 summary records 11 requests, all failed, and p95 346.393 ms. The persisted HTTP status distribution is empty. The run's `succeeded` state means k6 completed and supplied metrics; it does not mean the website responded successfully.

On 2026-10-09, a single read-only request from the same Docker worker network returned **HTTP 403** for `/` and **HTTP 200** for `/login.php`. A matching host-side check returned the same statuses. This identifies the tested root endpoint as currently forbidden from this environment while the public login page is reachable. It does **not** identify why `/` is forbidden, establish site-wide health, or measure an authenticated tutor session. The previous report's 90%-confidence cause (misconfiguration or service unavailability) cited only the aggregate error-rate metric and was not supported by diagnostic evidence.

The browser investigation now accepts an explicit request path and sends it to the planner. Choosing `/login.php` would measure only the public login page. The investigator rejects a causal hypothesis for complete failures when both response status distribution and service telemetry are absent; invalid AI output falls back to a grounded measurement-only analysis. No new external load run was performed while making this correction.

## Remaining product work

PerfPilot needs first-class authenticated, multi-step, read-only journeys with secret references, explicit pacing and ramp controls, and per-stage metrics. Until then, a login-page GET cannot establish EduQuest's authenticated capacity. Repeat the 100-user test only after EduQuest access is healthy, the QA account/session behavior is understood, and the target's server logs can be observed alongside k6 metrics.
