# Engine review and AltF4 reference project

Review date: 10 November 2026. This checks our analysis tool; it does not test the database application's runtime behavior. No AltF4 source, dependencies, tests, build commands, or launchers were executed.

## Bugs reproduced and fixed

1. A dotted filename such as `pkg.child.py` was incorrectly matched to `import pkg.child`. Python package separators refer to directories, not dots embedded in filenames. The resolver now keeps these files in the structure report but does not invent importable module paths for them.
2. The same false connection occurred with dotted directories such as `pkg.child/module.py`. Invalid path components are now excluded from the import index, and intermediate package paths must exist.
3. `from pkg import missing` could be reported as local when pkg was only an implicit namespace directory and missing did not exist. The resolver now leaves that name unresolved. Valid child modules and bare namespace imports still work.

The three initial regression cases failed before the fixes and passed afterward. Nearby cases include a missing namespace child beneath a regular parent package, plus dotted-file and module-shadowing checks. Two hundred seeded eight-node graph comparisons were added as well. The graph comparisons use an independent transitive-closure calculation. Existing checks cover all 64 directed three-node graphs without self edges and a 1,500-node circular group.

## Verified scope

- All 31 unit/command-line tests passed.
- Python's dependency consistency check passed.
- React's production build passed.
- The package registry audit reported zero frontend dependency advisories at review time; this is not a complete security assessment.
- A fresh local backend process returned the expected /health JSON and OpenAPI route, then was stopped.
- The reference was analyzed repeatedly; the complete reports were identical.
- The import fixes did not change AltF4's report.
- A separate AST walk agreed with the file, function, class, and import-statement counts. This independently checks counting, not every resolved edge.

This does not establish correctness for every Python project. Public uploads, external downloads in the application, and their resource limits remain unimplemented. The reference command below is a developer tool for an already-downloaded local copy, not the future GitHub-link API.

## The reference snapshot

Repository: https://github.com/nikhilbajantri/AltF4.git

Pinned commit: `10a0bf44b2490104c61d2696290ea3ed27234dc1`.

The downloaded copy lives in `temp/AltF4`, which is excluded from our Git commits. We do not copy its source into our repository or silently update it. Analyze the repository root because its imports use names such as `src.engine`, `tests.util`, and `torturelib.protocol`. For this project, analyzing only `src` would lose those root-relative package names.

## Measured results

| Metric | Result |
| --- | --- |
| Python files found and analyzed | 53 |
| Named functions, including methods/nested functions | 431 |
| Classes | 56 |
| Import statements | 377 |
| Local file connections | 167 |
| Unresolved imported names | 336 |
| Source parse/read errors | 0 |
| Circular groups in the resolved graph | 0 |

The first measured run took about 1.13 seconds on this machine; later runs can be faster due to caching. This is not a hosting performance guarantee. Changing `src/engine.py` potentially affects 17 direct and 3 indirect dependent files, 20 in total, according to the resolved import map.

Unresolved names include standard-library modules and symbols. This does not mean there are 336 broken imports. Our engine deliberately does not install dependencies or load modules to classify them.

## Repeat the check

From our project root:

```powershell
backend/.venv/Scripts/python.exe scripts/check_altf4.py
```

From a terminal already in backend:

```powershell
.venv/Scripts/python.exe ../scripts/check_altf4.py
```

The script writes `output/reference/AltF4-analysis.txt`, the full JSON report, and a comparison summary. It compares the revision, metrics, and full report fingerprint with `tests/reference/altf4.json`. A mismatch exits with code 1 so we notice changes. The baseline is a repeatability check, not independently verified ground truth for all 167 edges.

To inspect another file, use the ordinary engine command from backend:

```powershell
.venv/Scripts/python.exe -m app.analyzer ../temp/AltF4 --format text --impact src/format.py
```

On a fresh machine, create the reference copy once:

```powershell
git clone --no-checkout --depth 1 --no-tags https://github.com/nikhilbajantri/AltF4.git temp/AltF4
git -C temp/AltF4 fetch --depth 1 origin 10a0bf44b2490104c61d2696290ea3ed27234dc1
git -C temp/AltF4 checkout --detach 10a0bf44b2490104c61d2696290ea3ed27234dc1
```

Keep this copy at the recorded revision for repeatable checks. If you deliberately change the snapshot or the report schema, review the differences before updating the baseline. Do not simply replace the expected fingerprint to hide a failure.

## Known limits exposed by this example

The tool reads `.py` files only. AltF4 also has extensionless Python launchers (`kvdb`, `torture`, `prove`), which are not included in the 53-file report. Dynamic imports, runtime path changes, and subprocess-launched modules are not inferred. No circular groups in the resolved graph is not proof of no runtime cycles. Function-call analysis, running the database, and proving its crash-safety guarantees are outside this review.

## Next development gate

Keep the small examples and automated suite as our correctness checks, and use AltF4 as an additional realistic repeatability sample. Then implement shared safe input handling before connecting ZIP uploads and public GitHub URLs to the API.
