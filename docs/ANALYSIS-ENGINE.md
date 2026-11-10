# Analysis engine v1

The first local engine milestone is complete. It reads Python source, extracts definitions, matches supported local imports, builds a file map, calculates potential impact, and finds circular groups. It does not run the analyzed source.

## Try the readable output first

From the project folder, open a terminal and enter:

```powershell
cd backend
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project --format text --impact database.py
```

You should see:

```text
Potential impact of changing database.py:
  Direct dependents: auth.py
  Indirect dependents: main.py
  Other files potentially affected: 2

Circular dependency groups: 0
```

This means `auth.py` imports from `database.py`. `main.py` imports from `auth.py`, so it can be affected indirectly. These files deserve attention after a change; neither is guaranteed to break.

## How impact works

1. Remember that `main.py -> auth.py` means main imports auth.
2. For a change to database, follow incoming arrows: who imports database?
3. Continue through the importers of those files.
4. Keep a visited set: a list of files already checked. This prevents loops and duplicate results.
5. Separate files one incoming step away (direct) from the other reachable files (indirect).

If a file is reachable both directly and indirectly, it appears only in the direct list. The selected file never appears as its own dependent.

## Try a circular example

From backend:

```powershell
.venv/Scripts/python.exe -m app.analyzer ../examples/circular_project --format text --impact alpha.py
```

The tool finds one circular group: `alpha.py` and `beta.py`. `main.py` imports alpha but is not part of that group because neither alpha nor beta imports main. `standalone.py` still appears as an isolated graph node in the full JSON report.

A circular group contains files that can reach one another by following import arrows. We report groups, not every possible circular route. A group is a reason to inspect the code, not proof of a runtime error. Package initializer edges can also contribute to these potential groups.

## Where the code lives

- `app/analyzer.py`: reads files, extracts syntax, combines the report, and handles command-line output.
- `app/dependencies.py`: matches import names to local files.
- `app/graph.py`: builds incoming/outgoing file lists, walks incoming connections for impact, and finds circular groups.

The graph operations use Python's standard library; no new packages were needed. Circular-group detection uses two iterative walks (Kosaraju's algorithm), so a long dependency chain does not require deeply nested Python function calls. You can study that algorithm later; the important idea now is mutual reachability.

## Output contract

The report is schema version 3:

- `analysis_status`: complete if all discovered files/directories were read successfully, partial if there were read/syntax/nesting errors. Complete does not mean all imports were resolved.
- `summary`: counts, local edges, unresolved import names, circular groups, and files in those groups. File counts now count discovered Python files independently of directory errors.
- `files` and `errors`: source structure and per-file/folder failures.
- `dependencies`: import matching details and edges, including source lines and uncertainty.
- `graph.nodes`: each successfully analyzed file, its `dependencies`, and its `imported_by` list. `graph.edges` lists unique directed relationships.
- `impact`: a record for every successful file with `direct_dependents`, `indirect_dependents`, and `affected_count`.
- `circular_dependency_groups`: sorted lists of mutually reachable files. The file resolver omits same-file edges, so its groups contain at least two files.

All lists are sorted where order is not meaningful, making results repeatable. Invalid files remain in `errors` and are excluded from the graph. The existing import-root assumptions and uncertainty described in IMPORT-RESOLUTION.md still apply.

## Useful commands

From backend, the original command still prints full JSON:

```powershell
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project
```

Use `--format text` for a readable summary. Add `--impact database.py` to choose a relative path inside the analyzed project. Without text format, this option returns focused impact JSON. Invalid folders or selections return exit code 2 with a message; partial analysis returns 1; successful analysis returns 0. An empty readable directory is a complete, empty result.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The suite covers graph chains, diamonds, isolated files, duplicates, cycles, overlapping direct/indirect paths, CLI errors and output, partial input, and prior parser/resolver cases. It also checks every directed three-node graph without self edges against an independent reachability calculation, and tests circular detection on a 1,500-file synthetic group. This is test evidence, not a performance promise for arbitrary uploaded projects.

## Completion boundary and next milestone

This is a local engine for the first release's file/import features. It does not yet accept ZIP uploads or GitHub URLs, run behind an analysis API, display an interactive map, resolve function calls, or explain business purpose with AI.

Computing impact for every file needs a traversal per file and can produce quadratic output. Public input limits, worker time/memory limits, and response-size limits must be implemented before exposing it publicly. No public-upload safety claim is made here.

Next: add one controlled project-input workflow, with bounded safe extraction. ZIP uploads and public GitHub default-branch snapshots will feed that same workflow, followed by this engine. Then connect the React website to those results.

The follow-up [review and AltF4 reference check](REVIEW-AND-REFERENCE.md) documents import edge-case fixes, the expanded 31-test suite, a pinned real-project snapshot, and a repeatable check command.
