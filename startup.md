# Run PerfPilot and test an authorized system

This guide is for an operator who does not write code. Follow the steps in order. PerfPilot runs on your computer through Docker Desktop and sends real traffic to the system you choose. The same steps apply to any **authorized, reachable target**; the example names below are placeholders, not a special setup for one website.

## What you need before starting

- A computer with Docker Desktop installed and running, with the Linux container engine enabled. Docker Compose version 2.24 or newer is required. The first start downloads and builds images and may take several minutes.
- A copy of this PerfPilot folder and permission to edit its `.env` file.
- The system owner's explicit permission for performance testing, the exact hostname allowed, a safe testing window, an approved maximum number of simulated users, and someone who can watch the target's health during the test. Prefer a staging system.
- A target that can be reached from the Docker worker and has a **safe, public, read-only GET path**. See [What this version can test](#what-this-version-can-test) before using a login or API system.

Do not use a test account or password in the PerfPilot form. Do not start a larger run until the owner agrees to the load and the smaller run has finished without harming the service.

## 1. Set up PerfPilot once

1. Open the PerfPilot folder in File Explorer. Make a copy of `.env.example` in the **same folder** and name the copy `.env`. If Windows warns about changing the extension, accept it. Turn on **View → Show → File name extensions** if you need to check that the file is `.env`, not `.env.txt`.
2. Open `.env` in Notepad or another plain-text editor. Find `API_AUTH_SECRET=` and replace `replace-me-with-a-long-random-value` with a long random value from a password manager. Keep this file private; do not commit or share it.
3. Find `ALLOWED_TARGET_HOSTS=`. Replace its value with the approved hostnames, separated by commas. Enter **hostnames only**: for `https://shop.example.org/`, enter `shop.example.org`. Do not include `https://`, a path, or a port. Add every approved hostname you intend to test, and no others. Example: `ALLOWED_TARGET_HOSTS=shop.example.org,api.example.org`.
4. Find `MAX_VIRTUAL_USERS=`. Set it to the largest load the owner has approved for this testing window. For a first smoke test, use `MAX_VIRTUAL_USERS=1`; change it to `10` or `100` only when that level has been approved. PerfPilot rejects an investigation whose planned peak exceeds this ceiling.
5. Leave `MAX_TEST_DURATION_SECONDS=1800` unless the owner has approved a lower limit. The built-in planner **ramps toward each load level over 60 seconds**: a 1-user or 10-user run has one stage; a 100-user run has 10, 50, and 100-user stages. A lower duration ceiling can prevent a run from starting.
6. Leave `AI_PROVIDER_ENABLED=false` for the first run. PerfPilot can measure and produce a report in this deterministic mode. To evaluate live model reasoning later, see [Optional: live AI reasoning](#optional-live-ai-reasoning).
7. Save `.env` and close the editor.

You only need to repeat steps 3–5 when the approved target, maximum load, or time limit changes. **Restart the containers after editing `.env`** using the start command below.

## 2. Start the application

1. Open Docker Desktop and wait until it says the engine is running.
2. Open the PerfPilot folder in File Explorer. Click the address bar, type `powershell`, and press Enter. A PowerShell window opens in the right folder.
3. Copy and run these commands **one line at a time**:

   ```powershell
   cd infrastructure/docker
   docker compose --profile all up -d --build --force-recreate
   docker compose exec api python -m alembic -c apps/api/alembic.ini upgrade head
   docker compose ps
   docker compose port web 3000
   docker compose port api 8000
   ```

4. Wait for `api`, `worker`, `db`, and `redis` to be running or healthy in `docker compose ps`. The `web` service must be running. The migration command must finish without an error. If it fails, stop here and use [Troubleshooting](#troubleshooting).
5. The `docker compose port web 3000` result gives the browser port. For example, `0.0.0.0:3000` means open `http://localhost:3000`. If it prints another port, use that port instead. Similarly, open `http://localhost:<API port>/health`; it should show `{"status":"ok"}`.
6. Keep Docker Desktop and the PowerShell window available while you test. Closing the PowerShell window does not stop the containers.

On later days, use the same commands. The migration is safe to rerun. The `--force-recreate` option makes saved `.env` changes take effect.

## 3. Add the system you are allowed to test

1. Open the PerfPilot browser address from step 2. The dashboard creates a local project automatically.
2. Select **Add an application** or **Add target**.
3. Enter a clear **Application name**, such as `Shop staging`.
4. In **Base URL**, enter the approved origin, such as `https://shop.example.org`. Include `https://` (or `http://` for an approved local service); leave off `/login`, `/api`, query strings, and credentials. You choose the request path separately when starting an investigation.
5. Enter your name, tick the ownership/permission confirmation only when it is true, and select **Add application**.
6. If the target is rejected, check that its hostname exactly matches an entry in `ALLOWED_TARGET_HOSTS`, then restart the containers. If the worker cannot reach it, the system owner may need to allow the Docker host's network access. A site on your own computer is **not** reached by using `localhost` from inside the worker container; on Docker Desktop, the owner may need to expose it through `host.docker.internal` and allow that hostname.

The dashboard stores its target list in this browser's local storage. Keep using the same browser profile. Save each results-page URL separately so you can reopen a report; clearing browser data may remove the visible target list even when the server still has records.

## 4. Run a small test and watch it

1. Select the intended target on the dashboard. Check its name and Base URL before every run.
2. Under **Start an investigation**, choose an **Objective**. Use **Baseline — record current performance** for the first run. The other choices describe the question PerfPilot should investigate; they do not change the target endpoint.
3. In **Request path**, enter a safe page path beginning with `/`. The default `/` may be forbidden even when the site is available. For an authorized public login-page check at EduQuest, enter `/login.php`. Do not enter the full URL, a query string, or credentials. This checks the public page; it does not sign in.
4. Set **Normal concurrent users** and **Peak concurrent users** to `1` for the first run. You may add a plain-language **Peak description**, such as `Quiet staging check`.
5. Select **Start investigation** once. This sends real load. Avoid clicking again because that creates another run.
6. Keep the results page open. The **Timeline** shows planning, execution, analysis, and reporting progress. Wait for **Complete** or **Failed**. Copy the page URL and record the date, target, objective, request path, requested users, and any error shown.
7. Check the target's own monitoring and normal user experience during and after the run. If the target degrades, follow [Emergency stop](#emergency-stop).

The **Peak concurrent users** field is a requested ceiling, not proof that that many complete user sessions ran. The report's **Peak concurrency** describes simulated k6 workers reached. For this browser workflow, each worker repeats one unauthenticated GET to the selected path with a one-second pause.

If the form says **“Requested concurrency exceeds the configured safety ceiling”**, the requested peak is above `MAX_VIRTUAL_USERS` in `.env`. A 100-user built-in plan also needs about 180 seconds, so a `MAX_TEST_DURATION_SECONDS` value below 180 will reject it even after the user limit is raised. Change either ceiling only within the target owner's approved limits, save `.env`, rerun the start command in step 2, and submit a new investigation. A rejected request has no completed test or report to export.

## 5. Increase load only after reviewing the previous run

For each approved load level, first change `MAX_VIRTUAL_USERS` in `.env` if needed, save it, and rerun the start command in step 2 so the worker reads the new ceiling. Then start a **new investigation** on the same target.

| Run | Normal concurrent users | Peak concurrent users | Expected built-in stages |
|---|---:|---:|---|
| Smoke test | 1 | 1 | Ramp toward 1 over about 60 seconds |
| Small load | 10 | 10 | Ramp toward 10 over about 60 seconds |
| Larger load, only with explicit approval | 100 | 100 | Ramp toward 10, then 50, then 100; about 60 seconds per stage |

Wait for each run to finish and for the target to recover before moving to the next row. The **normal** number describes your expected traffic; the planner uses the **peak** number to choose the stages. The actual run can end early if an error-rate threshold trips or another failure occurs. A 100-user request therefore does not guarantee a full 100-user measurement.

For another system, repeat steps 1, 3, 4, and 5 with that system's **own** authorization, hostname, load ceiling, and results record. Do not carry over one system's safe load or performance target to another.

## 6. Read the result

- **Summary** shows throughput (requests per second), p95/p99 latency (slow-end response times), error rate, and peak concurrency. Smaller latency and error rate are generally better, but compare them with the system owner's targets and the same test conditions.
- **Download report CSV** in Summary exports one completed investigation's metrics, findings, hypotheses, and recommendations. It works without a second run. Save the CSV with the results-page URL and target team's monitoring notes.
- **Findings** lists measured observations and any hypotheses. A hypothesis or “likely cause” is an interpretation, not a confirmed diagnosis. Ask the system team to compare it with server, database, and application monitoring before changing the system.
- **Timeline** shows what PerfPilot actually did and whether it completed. If the report is missing or the run failed, record the status; do not present a partial result as a pass.
- **Comparison** may show a linked baseline and follow-up experiment when both exist and are compatible. If it says no baseline or comparison is available, do not infer improvement from two unrelated summaries.
- **Download CSV/JSON** in Comparison is enabled only when that compatible baseline and experiment pair exists. A first completed run can use **Download report CSV** instead.

The browser investigation uses default success limits of **p95 under 500 ms** and **HTTP error rate under 1%**. The form does not let an operator change these yet. Record the system owner's real limits separately; a PerfPilot “pass” against these defaults may not meet that system's requirements. A 1-user run establishes behavior only at that load, not total capacity. Keep the results-page URL, screenshots or exported comparison, the approved load, and the target team's monitoring notes together.

## What this version can test

| System | What the browser workflow measures | Operator action |
|---|---|---|
| Public website with a safe page | Repeated unauthenticated GET requests to the selected path | Follow this guide, with the owner's permission. |
| Website with a public login page | The selected public login page | Select its path, such as `/login.php`, and label the result **login-page traffic only**. It does not test logged-in work. |
| Authenticated site, checkout, search, write API, or multi-step journey | The browser workflow cannot represent the real user actions or sign in | Ask the PerfPilot team to add a reviewed journey and secure credential handling before claiming to test that workflow. Never put passwords in a URL or form field intended for a target name. |
| API with a safe public GET endpoint | Only that selected endpoint | Enter the approved path. A result for `/` says nothing about another API endpoint. |
| Private or local system | Only if the worker container can reach its address | Have the system owner arrange access and verify the correct Docker-visible hostname. |

PerfPilot has agent components for planning, load execution, investigation, and reporting, but this version's generated browser test uses **only the first journey** and one GET endpoint. It does not simulate independent logged-in users, browser rendering, or a whole customer journey. Do not treat “100 virtual users” as 100 authenticated accounts.

## Optional: live AI reasoning

The default `AI_PROVIDER_ENABLED=false` mode uses deterministic specialist behavior. To observe the live planner, investigator, and reporter reasoning, obtain an approved provider key and change `.env` to `AI_PROVIDER_ENABLED=true`, set `AI_PROVIDER` to `gemini` or `deepseek`, and fill the matching `GEMINI_API_KEY` or `DEEPSEEK_API_KEY`. Save the file and rerun the start command in step 2. Keep the key private; provider calls may incur cost.

Run the same small, authorized target and compare the **Findings**, **hypotheses**, **recommendations**, and **Timeline** with the measured metrics. Look for claims that cite actual evidence and for clear uncertainty when server-side telemetry is missing. A fluent explanation alone is not proof of cause. If the Reporting Agent's answer cannot pass validation, PerfPilot may save a deterministic report; do not present that as live-model reasoning. If AI configuration or provider calls fail, record the error and return `AI_PROVIDER_ENABLED=false` for a measurement-only run. See [AI provider setup](docs/phase3/ai-providers.md) for model options and provider details.

## Emergency stop

If the target slows sharply, produces unexpected errors, or its owner asks you to stop, use the PowerShell window still in `infrastructure/docker` and run:

```powershell
docker compose stop worker
```

Tell the target owner immediately and wait for recovery. The current PerfPilot run may stay incomplete or failed after this stop. Do not restart the worker until the owner approves more testing. When approved, run `docker compose --profile all up -d --force-recreate` from the same folder and check `docker compose ps` again. Coordinate with other operators: stopping the worker also affects their queued or running tests.

## Troubleshooting

| What you see | What to do |
|---|---|
| `docker` is not recognized or the engine is unavailable | Open Docker Desktop and wait for the engine. If Docker is not installed, ask the machine administrator to install it. |
| A port is already in use | Close the other local service using that port or ask the PerfPilot maintainer to provide a Compose port override. Do not guess a different browser address. |
| Migration fails or `api`/`worker` is unhealthy | From `infrastructure/docker`, run `docker compose ps` and `docker compose logs --tail=100 api worker db`. Share the error, without secrets, with the PerfPilot maintainer. |
| Dashboard cannot connect | Check the API `/health` page and `docker compose ps`, then refresh the dashboard once. |
| Target is forbidden or not allowed | Check the exact hostname in `.env` and restart the containers. Authorization must also be confirmed in the Add application form. |
| Run stays queued | Check that `worker` and `redis` are running. Do not submit the same test repeatedly. Ask the maintainer to inspect worker logs and the saved results-page URL. |
| Run fails or stops early | Note the Timeline status, target health, requested load, and error. Check worker logs. Lower the approved load or correct the target/network problem before retrying. |
| Report shows 100% errors | Check the saved request path first. A website can return 403 or 404 for `/` while another page works. Ask the owner to verify the exact path and HTTP response from the Docker worker. A successful PerfPilot test run means the load tool finished; it does not mean the target requests succeeded. Do not increase load until the one-user result is understood. |
| Report is missing after Complete | Save the results-page URL and ask the maintainer to inspect the API and worker logs. Treat the report as unavailable. |

The log command above is for collecting an error. Logs can contain target details, so share them only with the authorized PerfPilot team. Never paste `.env`, passwords, or provider keys into a support message.

## Finish and shut down

When all runs are complete, save their URLs and notes, tell the target owner testing has ended, and run this from the same `infrastructure/docker` PowerShell window:

```powershell
docker compose --profile all down
```

This stops PerfPilot while keeping its database volume for later use. Do **not** add `-v`; that would remove stored database data.
