# Development plan

## Responsibilities

- Backend: receive requests and coordinate analysis.
- Analyzer (next): parse source with ast without importing or executing it.
- Frontend: display analysis results and support exploration.
- Example: predictable input for checking analyzer results.

## Milestones

1. Extract functions, classes, and imports with file and line locations.
2. Resolve local imports and construct a directed module graph.
3. Calculate reverse dependencies and circular relationships.
4. Accept ZIP files with safe extraction and resource limits.
5. Connect React to the API and add a graph view.
6. Deploy, verify behavior, and document limitations.

## Git workflow

`git status` shows changes. `git add <file>` selects files for the next checkpoint. `git commit -m "Describe the change"` creates that checkpoint locally. `git push` sends commits to GitHub.

Review changes with `git diff` before committing. Do not commit secrets, dependencies, uploaded projects, or local environments.

## Deployment approach

Build the React frontend as static files and run FastAPI as a separate service. Choose hosting after the first complete workflow works. Configure the API URL and allowed frontend origin through environment settings when connecting the two services.
