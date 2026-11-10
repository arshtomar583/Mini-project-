# ZIP and public GitHub inputs

## What we built

The engine already reads a folder. These inputs prepare that folder: accept a ZIP, or download a public GitHub snapshot. Both use the same extraction checks, source-folder selection, engine, and cleanup. No project code is executed.

React now offers both input methods, an AltF4 example button, loading/errors, counts, file search, definitions with line numbers, imports/importers, potential impact, circular groups, and JSON report download. These results also feed the [interactive dependency map](INTERACTIVE-GRAPH.md).

## Try it

Start the backend from the project root:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Click **Use AltF4 example**, then **Analyze project**. Leave the source folder blank for AltF4 because imports such as `src.engine` begin at its repository root.

For ZIP input select **Upload ZIP**, choose an archive, and analyze it. Remove virtual environments, installed dependencies, and nested archives first. Syntax errors produce partial-analysis warnings; valid files still contribute results.

A blank source folder uses the project root after single-wrapper removal. User ZIPs containing only an actual package with `__init__.py` retain its name; GitHub's generated outer wrapper is always removed. Choose a relative folder such as `src` if that is the intended import root. Arbitrary server paths are not accepted.

## API contract

- `GET /health`: existing health check.
- `POST /api/analyses/zip`: multipart fields `file` and optional `source_root`.
- `POST /api/analyses/github`: JSON fields `repository_url` and optional `source_root`.

Success returns the existing schema-3 report plus `input` metadata. GitHub metadata contains repository URL, default branch, commit SHA, and source folder. ZIP metadata contains kind and source folder. Temporary paths and uploaded filenames are not included.

Input-handler failures return `{"error":{"code":"...","message":"..."}}`: 413 for size limits, 422 for invalid project content, 404 for unavailable public repositories, 429 for the service-wide request cap, 503 for busy/GitHub-rate-limited service, 504 for download/analysis timeout, and 408 for slow uploads. Gateway-level rejections can use the gateway's own error format. Valid partial results use HTTP 200 with their error list.

## GitHub snapshots

Only `https://github.com/owner/repo` URLs are supported, optionally ending in `.git` or `/`. Private repositories, branch/file URLs, credentials, custom ports, queries, and other hosts are unsupported. No GitHub token is used.

The backend reads public metadata, resolves the default branch to a commit, and downloads that SHA from `codeload.github.com`. It does not clone history or install dependencies. Requests use fixed HTTPS hosts, refuse redirects, and ignore proxy credentials from the environment. A renamed repository may need its current URL. Anonymous rate limits and network failures produce retry messages.

Implementation references: [GitHub references](https://docs.github.com/en/rest/git/refs#get-a-reference), [GitHub archives](https://docs.github.com/en/rest/repos/contents#download-a-repository-archive-zip), [FastAPI uploads](https://fastapi.tiangolo.com/tutorial/request-files/).

## Enforced limits

| Resource | Limit |
| --- | --- |
| Uploaded/downloaded ZIP | 5 MiB |
| Multipart request / GitHub JSON body | 6 MiB / 4 KiB |
| Upload reading / GitHub downloading | 20 seconds / 30 seconds overall |
| Entries / Python files | 2,000 / 200 |
| Extracted bytes / individual Python file | 25 MiB / 1 MiB |
| Path depth | 10 components, including any outer wrapper |
| Extraction + analysis worker | 15 seconds |
| Worker report | 4 MiB |
| Concurrent analyses | One per backend process; excess requests receive 503 |
| Admitted analysis attempts | 20 per rolling minute per process, shared by all visitors; excess receives 429 with Retry-After |

The browser allows 65 seconds for the whole request. GitHub metadata responses are bounded to 64 KiB. Linux workers cap address space at 256 MiB. Windows development uses file/runtime/output bounds. The EC2 Compose configuration additionally caps the app container at 512 MiB.

## Extraction and cleanup

Validate original archive names before writing. Reject traversal/absolute paths, Windows-unsafe names and separators, duplicates/case conflicts, links/special files, encryption, corrupt/unsupported ZIPs, and nested archives. Count actual bytes during extraction; never call `extractall`.

Each request gets a unique temporary workspace. A trusted child process extracts and analyzes it. On timeout/cancellation the parent kills and awaits that worker before removing temporary files. Upload objects are closed. Success, failure, oversized-report, and real-timeout cleanup are tested. Machine/server crashes can bypass normal cleanup; deployment needs a stale-temp policy.

These controls are not a claim that arbitrary hostile workloads are fully sandboxed or that the service supports unlimited traffic. The EC2 configuration supplies container limits, a disposable temporary filesystem, and an optional HTTPS gateway with a body limit. Account/hostname setup and live production verification remain; see AWS-DEPLOYMENT.md. Use one backend worker: concurrency locking and rate limiting are per process.

## Configuration

Locally, Vite proxies `/api` to backend port 8000. The Docker deployment keeps `VITE_API_BASE_URL` blank and serves the built frontend through FastAPI using `FRONTEND_DIST`, so UI and API share an origin. For deliberately separate production hosts, set `VITE_API_BASE_URL` at build time and `FRONTEND_ORIGINS` on the backend to the exact frontend origin. Frontend variables are public; do not put secrets there. Example `.env` files are documentation; the backend does not load them automatically.

## Verification

- 53 tests passed, including the existing engine and new input workflows.
- Coverage includes path validation, Windows ZIP normalization, archive/request limits, corrupt/encrypted entries, source roots, fixed-host URLs, network/rate-limit failures, streamed body limits, busy handling, partial results, no source execution, actual worker termination, oversized reports, and cleanup.
- Live HTTP ZIP analysis returned the expected three-file demo.
- Live GitHub analysis of AltF4 at `10a0bf44b2490104c61d2696290ea3ed27234dc1` returned 53 files, 431 functions, 56 classes, and 167 edges. Excluding input metadata, its report exactly matched the pinned local reference.
- Browser checks covered GitHub analysis, ZIP selection/upload, search/selection, rejected URLs, loading, and responsive layout. A controlled-input warning found when switching input methods was fixed by giving the alternative fields distinct React keys.
- Frontend production build and Python dependency consistency passed.

The live GitHub output is saved locally at `output/reference/AltF4-github-api.json`. AltF4 source and its tests were not executed.

## Next

The interactive graph is implemented using the existing nodes/edges and shared file selection. Public deployment follows integrated testing; call graphs and AI remain later work.
