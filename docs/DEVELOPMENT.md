# Development plan

## Responsibilities

- Backend: receive requests and coordinate analysis.
- Analyzer: parse source with ast, resolve supported imports, and calculate graph results without importing or executing the analyzed source.
- Frontend: display analysis results and support exploration.
- Example: predictable input for checking analyzer results.

## Milestones

1. Done: extract functions, classes, and imports with file and line locations.
2. Done: resolve supported local imports and construct a directed file graph.
3. Done: calculate potential impact and circular dependency groups.
4. Next: accept ZIP files and public GitHub repository snapshots with shared safe extraction and resource limits.
5. Connect React to the API and add a graph view.
6. Deploy, verify behavior, and document limitations.

## Git workflow

`git status` shows changes. `git add <file>` selects files for the next checkpoint. `git commit -m "Describe the change"` creates that checkpoint locally. `git push` sends commits to GitHub.

Review changes with `git diff` before committing. Do not commit secrets, dependencies, uploaded projects, or local environments.

## Deployment approach

Build the React frontend as static files and run FastAPI as a separate service. Choose hosting after the first complete workflow works. Configure the API URL and allowed frontend origin through environment settings when connecting the two services.
