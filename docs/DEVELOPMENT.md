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
4. Done: accept ZIP files and public GitHub snapshots with shared checked extraction and worker/input limits.
5. Done: React results explorer and interactive dependency map with shared file selection, zoom/pan, layout controls, focused connections, change impact, and circular-group views.
6. In progress: single-service Docker build, EC2 runtime configuration, optional HTTPS proxy, and CI checks are prepared. AWS account/instance setup and live verification remain.

## Git workflow

`git status` shows changes. `git add <file>` selects files for the next checkpoint. `git commit -m "Describe the change"` creates that checkpoint locally. `git push` sends commits to GitHub.

Review changes with `git diff` before committing. Do not commit secrets, dependencies, uploaded projects, or local environments.

## Deployment approach

Build React as static files, then serve those files and the API from one FastAPI service on AWS EC2. The user plans to start the instance for demonstrations and stop it afterward. Docker Compose provides process/memory/storage bounds and automatic restarts; an optional Caddy proxy adds HTTPS for a configured hostname. See AWS-DEPLOYMENT.md for staged private/public checks and the limits of the free plan. No AWS resources have been created yet.
