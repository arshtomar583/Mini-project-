# Explain This Codebase

Under development. A tool for exploring Python project structure, import dependencies, and potential change impact through static analysis.

## Current status

The first local analysis engine is complete: AST structure, supported local imports, a file graph, potential change impact, and circular dependency groups. A FastAPI health endpoint and React welcome screen also exist. ZIP/GitHub inputs, an analysis API, interactive graph UI, and AI explanations are not implemented yet.

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

Open the local URL printed by Vite. The welcome screen is independent of the API for now.

Use `Ctrl+C` in each terminal to stop its server. Run `npm run build` from `frontend` to check the production build. Commit `package-lock.json` so `npm ci` installs the same dependency versions.

## Scope and limits

The first release will accept Python ZIP uploads, extract definitions and local imports, display a module graph, and show potential impact through reverse dependency traversal. An arrow A -> B means A imports B. Static analysis does not prove execution order or guarantee that a dependent module will break.

Uploaded code must never be executed. Before enabling uploads, implement safe extraction, file and size limits, and temporary-file cleanup.

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

Add safe, bounded project ingestion for ZIP uploads and public GitHub default-branch snapshots, then connect the analysis API and visual interface. Both input methods will share extraction and analysis logic.
