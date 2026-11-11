# Explain This Codebase

Under development. A tool for exploring Python project structure, import dependencies, and potential change impact through static analysis.

## Current status

The analysis engine, ZIP upload API, public GitHub snapshot API, and React results explorer work locally and on AWS EC2 over HTTPS. An interactive dependency map connects file selection to definitions, imports, potential impact, and circular groups. Open the [live demo](https://explain-codebase.13-54-188-194.sslip.io/) while the EC2 instance is running.

## Structure

```text
backend/             Python API and local analysis engine
frontend/            React interface
examples/demo_project/ Small Python project for learning and validation
docs/                Design notes and development plan
```

## Requirements

- Python 3.12 or newer
- Node.js 22.12 or newer and npm
- Git

## Run the backend (PowerShell, from the project folder)

```powershell
& 'C:/Users/arsht/AppData/Local/Python/bin/python3.12.exe' -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --reload
```

The first command uses the working Python installation on this computer, avoiding its broken Microsoft Store shortcut. On another computer, replace that executable path with your installed Python. The environment is already installed here: future starts only need the Uvicorn command. No environment activation is required.

`requirements.txt` records direct dependencies; `requirements.lock.txt` records all versions verified for this starter.

Backend: http://127.0.0.1:8000/health

Interactive API documentation: http://127.0.0.1:8000/docs

## Run the frontend (a second terminal)

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite. The frontend proxies analysis requests to the backend on port 8000. Choose a ZIP or click **Use AltF4 example**, then **Analyze project**. See [project input instructions](docs/PROJECT-INPUTS.md) for limits, API details, and configuration.

Use `Ctrl+C` in each terminal to stop its server. Run `npm test` and `npm run build` from `frontend` to check the graph behavior and production build. Commit `package-lock.json` so `npm ci` installs the same dependency versions.

After analysis, explore the **Visual map**. Click a file box to select it, drag to rearrange or pan, and use the zoom/fit controls. Switch between the whole project, immediate connections, potential change impact, and circular groups. Larger projects start with immediate connections to keep the map readable. See [the graph walkthrough](docs/INTERACTIVE-GRAPH.md).

## Scope and limits

ZIP uploads and public GitHub default-branch snapshots feed the same engine. The input limit is 5 MiB compressed, 25 MiB extracted, and 200 Python files; other limits are documented in PROJECT-INPUTS.md. An arrow A -> B means A imports B. Static analysis does not prove execution order or guarantee that a dependent module will break.

Uploaded code is read without execution. The API uses checked extraction, bounded requests, disposable analysis workers, and temporary-file cleanup. It admits one analysis at a time and at most 20 attempts per minute across the service. The EC2 configuration adds container limits and optional HTTPS; public verification remains deployment work.

## Run the first analyzer

From the project folder:

```powershell
cd backend
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project --format text --impact database.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Expected demo totals: 3 files, 3 functions, 0 classes, 2 import statements, 2 local dependency edges, 0 unresolved imports, 0 circular groups, 0 errors. Changing database.py potentially affects auth.py directly and main.py indirectly. See [the engine walkthrough](docs/ANALYSIS-ENGINE.md), [AST walkthrough](docs/FIRST-ANALYZER.md), and [import resolution walkthrough](docs/IMPORT-RESOLUTION.md).

## Next step

Use the [EC2 deployment walkthrough](docs/AWS-DEPLOYMENT.md) for the Amazon Linux setup, live verification, and start/stop routine. The demo hostname contains the current public IP and may change when the instance restarts.

The root `Dockerfile` builds React and serves it through FastAPI on the same URL. `deploy/aws/compose.yaml` supplies runtime limits and restarts. `.github/workflows/checks.yml` runs tests and a Linux container check on pushes; it does not deploy or create cloud resources. Docker is not installed on this workstation, so container verification runs in GitHub Actions.

## Real-project reference check

AltF4 is our pinned public reference project. Run `backend/.venv/Scripts/python.exe scripts/check_altf4.py` from the project root after downloading the reference copy. See [the review and reference instructions](docs/REVIEW-AND-REFERENCE.md) for the snapshot, results, limitations, and setup commands. The reference source stays in ignored `temp/AltF4`; it is not bundled with our application.
