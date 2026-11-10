# Interactive dependency map

## What this step adds

The backend already answers which Python files import other files. React now draws that answer as a map using Cytoscape.js. We do not ask the browser to analyze Python again.

```text
ZIP or GitHub → backend analysis → JSON nodes and edges → clickable map
```

A node is a file box. An edge is an arrow. **A → B means A imports B.** For our demo, `main.py → auth.py → database.py`. This is an import map, not proof that the functions run in that order.

## Try it with AltF4

1. Start the backend and frontend using the README instructions; open http://127.0.0.1:5173/.
2. Click **Use AltF4 example**, then **Analyze project**. Leave the source folder blank.
3. Scroll to **Visual map**. Projects with more than 25 files start with the selected file's immediate connections. Smaller projects start with the whole project.
4. Select **Whole project** to see all 53 files and 167 resolved connections in the reference snapshot.
5. Choose `src/engine.py`, then **Potential change impact**. The map contains the selected file plus 20 possible dependents (21 boxes total).
6. Click a box or change **Selected file**. The file list and details below use the same selection. The dropdown and searchable file list provide a keyboard alternative to the canvas.
7. Try **Spread out** and **Layers**, drag boxes, pan the background, zoom, and use **Fit map**. **Rearrange** resets positions using the chosen layout.

The colors explain each file's relationship to the selected file. Green is selected, blue is a dependency, amber is a direct importer, and purple means both directions (or an indirect dependent in impact view). Dashed borders and arrows mark circular relationships. Full paths appear in the selected-file dropdown, details, and hover text; exceptionally long canvas labels are shortened to fit.

## What each view includes

| View | Included files and connections |
| --- | --- |
| Whole project | Every analyzed file, including isolated files, and every resolved local edge |
| Selected file + connections | Selected file, its direct imports, its direct importers, and edges between those files |
| Potential change impact | Selected file, direct and indirect dependents from the backend report, and edges between those files |
| Circular groups | Files belonging to circular groups, with edges inside each group; bridges between different groups are omitted |

Impact follows incoming connections, but the drawn arrows always retain their original importer-to-imported direction. Affected files are possible review targets, not guaranteed failures. If there are no circular groups, the map says so instead of presenting a blank unexplained canvas. A file selected outside that view stays selected in the details and is identified as outside the map.

## How the code fits together

- `frontend/src/graph-model.js` selects which nodes and edges to display and assigns their visual roles. It does not change the report or recalculate Python analysis.
- `frontend/src/DependencyGraph.jsx` manages the Cytoscape canvas and controls. React owns the selection; a graph click updates it. The graph is destroyed when its component unmounts so old analysis views do not accumulate.
- `frontend/src/main.jsx` loads the graph component when results exist and shares selection with the file explorer. The graph library downloads as a separate bundle, keeping it out of the initial input screen's bundle.
- `frontend/src/styles.css` controls the surrounding layout and mobile presentation.

Changing selection in the whole-project view updates colors without moving boxes or resetting zoom. Changing which files are visible or choosing another layout arranges the visible graph again. Resizing the page resizes the canvas. Large graphs can still be dense; use a focused view and zoom for readable labels.

## Verification

From `frontend`, run `npm test` and `npm run build`. All eight graph tests and the production build passed. The tests cover exact arrow direction, isolated files, direct versus indirect impact, separate circular groups, empty views, unusual paths, label shortening, and a 200-file model. They also load elements into a real headless Cytoscape instance to check node/edge identity. They do not substitute for browser layout and interaction checks.

Browser checks used a live GitHub analysis of AltF4 and a ZIP of `examples/circular_project`. Verified 53/167 whole-project totals, 21 files in the engine impact view, an honest empty circular view, two opposite arrows in the circular sample, isolated-file display, box clicks updating details, dragging, zoom, fitting, layout changes, and file dropdown synchronization. A 390-pixel viewport had no horizontal page overflow. The final browser console had no warnings or errors. The spread-out layout was adjusted to use the available canvas dimensions after visual review found it could become too tall and narrow.

The existing 53 backend tests still pass. Backend code, API schema, and the AltF4 reference baseline are unchanged by this milestone.

## Still outside this milestone

The map does not infer external library connections, runtime execution, function calls, or semantic purpose. Positions and view choices are not saved across page refreshes. Public deployment, call analysis, and optional AI explanations remain separate work.

Library reference: [official Cytoscape.js documentation](https://js.cytoscape.org/).
