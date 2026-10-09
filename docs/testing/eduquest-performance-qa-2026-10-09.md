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

After this run, both the QA browser and separate requests from the test machine received connection resets from EduQuest. This may be an outage or a network protection block affecting the test machine. No further external load was sent. Site-wide availability was not established.

## PerfPilot behavior observed

PerfPilot's live 1-user investigation measured `/login.php` with p95 35.14 ms, p99 75.67 ms, throughput 0.98 requests/s, and 0% HTTP errors. Its TestRun succeeded, but the investigation failed in reporting: the live reporting provider twice returned a recommendation without a matching hypothesis. The schema validation correctly rejected the ungrounded recommendation; the system then had no report to show. PerfPilot's current generator performs a GET of one journey path and cannot run this authenticated tutor workflow. The local stack also had a configured ceiling of one virtual user, so it could not run the requested 10- and 100-user investigations without an explicit configuration change.

In a separate, bounded AI evaluation using credential-free dashboard aggregates from the 1- and 100-VU summaries, the Performance Investigator marked the degradation `CRITICAL`, cited the measured p50/p95, throughput, and error rate, and returned no causal hypothesis. This was a sound refusal to invent a server-side cause without infrastructure data. It called the latter result "100-user concurrency" because the metric contract records launched VUs but has no field for successful authenticated sessions; only 30 login checks succeeded in that run. The current reasoning path therefore cannot qualify that distinction on its own. This evaluation did not execute a load test or persist an investigation.

## Changes made during this investigation

- Keep a completed k6 summary when k6 exits 99 for a threshold breach; still reject other process errors and missing summaries.
- Pause one second between generated requests and stop early after persistent HTTP error-threshold failures.
- Record the actual maximum virtual users observed when a run ends early; allow k6's graceful stop time in the process timeout.
- If an AI report fails structured validation after retry, persist the deterministic grounded report and audit the fallback instead of failing the completed investigation.

These changes have focused automated coverage. A separate controlled local end-to-end investigation completed after the worker restart: the one-user k6 run succeeded, planner/investigator/reporting AI executions were audited as validated, and a report was persisted. This verified the worker path without sending more traffic to EduQuest.

A second local k6 smoke deliberately breached a 0.001 ms p95 threshold. k6 exited 99, and the production Load Engineer adapter returned `succeeded` with a parsed p95 of 1.383 ms and observed concurrency 1. This confirms that a completed threshold breach now remains usable evidence.

## Remaining product work

PerfPilot needs first-class authenticated, multi-step, read-only journeys with secret references, explicit pacing and ramp controls, and per-stage metrics. Until then, a login-page GET cannot establish EduQuest's authenticated capacity. Repeat the 100-user test only after EduQuest access is healthy, the QA account/session behavior is understood, and the target's server logs can be observed alongside k6 metrics.
