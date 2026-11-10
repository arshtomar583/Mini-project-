# Setup verification

## Verified

- Python 3.12 environment created at backend/.venv; pip and backend dependencies installed.
- `pip check`: no broken requirements.
- Backend GET /health: HTTP 200 with {"status":"ok"}.
- Backend OpenAPI schema lists /health.
- Frontend page and transformed React module: HTTP 200.
- `npm install`: completed; audit reported zero vulnerabilities at installation time.
- `npm run build`: passed.
- Demo Python project executes successfully.
- Existing GitHub main history fetched and linked to the local main branch.

## Setup notes

The default Microsoft Store Python shortcut is inaccessible in this session. Use backend/.venv/Scripts/python.exe after setup.

Some folder, Git metadata, and local network operations failed under restricted execution in this session. Folder creation succeeded using the installed Python, and Git and local servers worked with additional session access. No Windows security settings or folder permissions were changed. These errors do not establish OneDrive as the cause.

## Current application scope

The frontend is a welcome screen and is not connected to the API yet. The local engine extracts structure, matches supported local imports, builds file graphs, calculates potential impact, and detects circular groups. The demo identifies auth.py as a direct dependent of database.py and main.py as indirect. A separate circular example includes alpha.py and beta.py, plus an isolated file. See ANALYSIS-ENGINE.md for the current commands, test coverage, report format, and limitations. There is no upload support or deployment. Next milestone: bounded safe input handling for ZIPs and public GitHub snapshots.

VS Code initially showed a different clone at D:/Mini project/Mini-project-. It was switched to this chat's working folder at C:/Users/arsht/OneDrive/Documents/ChatGPT/Mini project, and the starter folders were verified in its Explorer. Use this folder for ongoing work to avoid confusing the two copies.

## Follow-up review

31 tests pass after fixing false import matches for dotted path components and missing namespace children. Frontend build, dependency consistency, package-registry audit, and live backend health checks passed at review time. AltF4 at commit 10a0bf44b2490104c61d2696290ea3ed27234dc1 is a pinned local reference: 53 Python files, 431 functions, 56 classes, and 167 local edges, with no parse/read errors. The source remains under ignored temp/AltF4. See REVIEW-AND-REFERENCE.md for scope and limitations.

## Project-input milestone

The earlier welcome-screen/input status is superseded: ZIP and public GitHub endpoints are implemented and connected to React. 53 tests pass; live ZIP/GitHub checks match the sample and AltF4 reference. Frontend build and dependency checks pass. See PROJECT-INPUTS.md for enforced limits, commands, cleanup, configuration, and deployment boundaries.

## Interactive map milestone

The dependency map is now connected to file details, with whole-project, immediate-connection, impact, and circular-group views. Zoom, pan, dragging, layout selection, and keyboard file selection are available. Eight frontend graph tests and the production build pass. See INTERACTIVE-GRAPH.md for the walkthrough. The application is still local, not publicly deployed.

## AWS preparation milestone

The selected host is AWS EC2, started for demonstrations and stopped afterward. A Docker build, bounded Compose service, optional Caddy HTTPS proxy, compiled-frontend serving, service-wide rate cap, deployment smoke checker, and GitHub Actions workflow are prepared. The local backend suite has 59 passing tests and the frontend has eight. Account creation, an instance, hostname setup, and live EC2 verification remain. See AWS-DEPLOYMENT.md; no AWS resources have been created.

## EC2 private deployment, 11 November 2026

The user created an Amazon Linux 2023 t3.micro instance in Sydney. SSH login works after restricting the Windows private-key ACL and verifying the server fingerprint. Docker, Git, and checksum-verified Compose are installed; the built app is healthy on server loopback port 10000. The deployed smoke checker passed ZIP and live AltF4 analysis (53 files, 167 edges). The selected free hostname resolves correctly. Public HTTPS awaits inbound HTTP/HTTPS rules and a valid certificate; the proxy is paused while that is configured. See AWS-DEPLOYMENT.md for the actual OS instructions and stop/start implications.
