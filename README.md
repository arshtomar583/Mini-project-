# Explain This Codebase

Under development. A tool for exploring Python project structure, import dependencies, and potential change impact through static analysis.

## Current status

Initial project structure with a FastAPI health endpoint and a React welcome screen. Uploads, AST analysis, graphs, and AI explanations are not implemented yet.

## Structure

```text
backend/             Python API and future analyzer
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

## Next step

Build a small analyzer that reads the example project with Python's `ast` module and reports files, functions, classes, and imports with source locations.
