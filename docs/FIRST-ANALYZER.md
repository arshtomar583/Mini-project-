# Understanding the first analyzer

## What we built

`backend/app/analyzer.py` reads a local Python project and prints a JSON report. It uses only Python's standard library. It does not execute or import the project's source files.

## Run it yourself

Open the terminal in the project folder in VS Code:

```powershell
cd backend
.venv/Scripts/python.exe -m app.analyzer ../examples/demo_project
```

Expected totals: 3 files, 3 functions, 0 classes, 2 import statements, 0 errors.

The report includes each file's functions, classes, and import statements, plus definition line ranges and docstrings. Nested definitions have qualified names: `User.save` identifies a function inside the `User` class. Counts include methods and nested functions; lambdas are not counted as named functions. Import counts are statements, not resolved dependencies.

## Why these steps exist

1. `os.walk` discovers source files, skipping environments and dependency folders. Symlinks are skipped to avoid following links outside the input folder.
2. `tokenize.open` reads source using its declared Python encoding.
3. `ast.parse` turns source text into a syntax tree. A `def` becomes a FunctionDef node; a `class` becomes a ClassDef node.
4. `StructureVisitor` visits these nodes and collects facts. Its scope list remembers which function or class contains a definition or import.
5. `analyze_project` combines the files into one report and calculates totals.
6. `json.dumps` displays the report in a format a future API and frontend can consume.

A syntax or encoding error is recorded for that file while other files continue. A report with errors produces exit code 1, so automated checks can notice partial failures. An invalid folder produces a command-line error.

## Verify it

From backend:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Checks cover our demo, nested definitions, async functions, import aliases, relative imports, invalid source, source encodings, ignored folders, and code containing a statement that would fail if executed.

## What comes next

The first milestone extracted imports without matching them. That matching step is now implemented: see [step 2](IMPORT-RESOLUTION.md). The analyzer does not establish execution order, detect unused imports, or answer natural-language questions.

This command is for trusted local development inputs. Before using it with public uploads, add extraction safety checks, file and byte limits, analysis time limits, and cleanup. There is deliberately no API accepting arbitrary local folder paths.
