# Step 2: turning imports into file dependencies

## Try it

In a terminal already in backend, run the same command as before:

```powershell
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project
```

The original file details are still there. The report now also includes:

```json
"dependencies": {
  "edges": [
    {"source": "auth.py", "target": "database.py"},
    {"source": "main.py", "target": "auth.py"}
  ]
}
```

This excerpt omits the import-resolution details printed alongside edges. The summary includes `local_dependencies: 2` and `unresolved_imports: 0` for our demo. The schema version is now 2 because we extended the report format.

## What an edge means

`source -> target` means the source has a possible import dependency on the target. It does not mean a function was called or that either file executed. Repeated imports between the same pair produce one edge. Self references are retained in resolution details but omitted from the graph of different files.

## How it works

1. The analyzer extracts imports as before.
2. The separate resolver in `backend/app/dependencies.py` creates a lookup table: `database` maps to `database.py`, and `models.user` maps to `models/user.py`.
3. It matches each import against that table. `from database import find_user` creates a dependency on `database.py`; it does not verify the existence or identity of `find_user` yet.
4. It records the match, including the source line, enclosing scope, alias, and target paths.
5. It collects unique source-target pairs. This list is the input for our next graph algorithms.

Keeping this step separate makes parsing and matching easier to understand, test, and change independently.

## Packages and relative imports

`pkg/__init__.py` represents the package `pkg`. Importing `pkg.service` can involve both `pkg/__init__.py` and `pkg/service.py`, so both are recorded when present. A directory without an initializer can act as a namespace package; importing only that directory may have no file target.

`from .database import query` is resolved relative to the importing file's package. Each extra dot moves one package level upwards. A relative import beyond that package is marked invalid rather than guessed.

## Important boundaries

- Select the folder that acts as the Python import root. For a `src` layout, analyze `project/src`. For imports beginning with `mypackage`, analyze the folder containing `mypackage`, rather than `mypackage` itself. We do not inspect packaging configuration yet.
- Resolution uses successfully parsed local files only. Targets with syntax or read errors can remain unresolved; those errors appear separately.
- `unresolved` means no usable local match. It could be a standard-library import, third-party library, missing file, or unsupported layout.
- `ambiguous` means multiple local files represent the same module name. We conservatively avoid choosing one.
- `local` means the module or namespace was matched. It does not prove that every imported attribute exists.
- For `from pkg import child`, a child module and package initializer may both be potential dependencies. Re-exported attributes can change runtime behavior; we do not resolve them yet.
- Dynamic imports, runtime path changes, import hooks, and installed package metadata are not analyzed. Imports inside conditional blocks or functions are still potential dependencies.
- These are static file relationships, not function calls or guaranteed runtime order. The resolver uses only in-memory analysis results and never imports the analyzed source.

## Verify it

From backend:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The suite covers aliases, repeated imports, namespace packages, package initializers, relative imports, ambiguous names, unavailable targets, and the original structure extraction.

## Next milestone

Use the edges to answer which files directly or indirectly depend on a selected file, and detect circular dependency groups. Then expose analysis through a controlled API workflow and build the visual graph.
