import test from 'node:test';
import assert from 'node:assert/strict';
import cytoscape from 'cytoscape';
import { buildGraphView, fileId } from '../src/graph-model.js';

function reportFor(paths, pairs, impact = {}, groups = []) {
  return {
    graph: {
      nodes: paths.map(id => ({ id, dependencies: pairs.filter(([a]) => a === id).map(([, b]) => b),
        imported_by: pairs.filter(([, b]) => b === id).map(([a]) => a) })),
      edges: pairs.map(([source, target]) => ({ source, target })),
    }, impact, circular_dependency_groups: groups,
  };
}
const chain = reportFor(['main.py', 'auth.py', 'database.py', 'isolated.py'],
  [['main.py', 'auth.py'], ['auth.py', 'database.py']],
  { 'database.py': { indirect_dependents: ['main.py'] } });
const pathsOf = view => view.elements.filter(item => item.data.path).map(item => item.data.path);
const classesOf = (view, path) => view.elements.find(item => item.data.id === fileId(path)).classes.split(' ');

test('whole project retains isolated files and exact importer-to-imported arrows', () => {
  const view = buildGraphView(chain, 'auth.py', 'all');
  const cy = cytoscape({ headless: true, elements: view.elements });
  try {
    assert.equal(cy.nodes().length, 4);
    assert.equal(cy.edges().length, 2);
    assert.deepEqual(cy.getElementById(fileId('auth.py')).outgoers('node').map(node => node.data('path')), ['database.py']);
    assert.deepEqual(cy.getElementById(fileId('auth.py')).incomers('node').map(node => node.data('path')), ['main.py']);
    assert.equal(cy.getElementById(fileId('isolated.py')).degree(), 0);
    assert.ok(classesOf(view, 'auth.py').includes('focused'));
    assert.ok(classesOf(view, 'main.py').includes('incoming'));
    assert.ok(classesOf(view, 'database.py').includes('outgoing'));
  } finally { cy.destroy(); }
});

test('connections view includes only direct neighbors and retains isolated selection', () => {
  const view = buildGraphView(chain, 'database.py', 'neighbors');
  assert.deepEqual(pathsOf(view), ['auth.py', 'database.py']);
  assert.equal(view.edgeCount, 1);
  const isolated = buildGraphView(chain, 'isolated.py', 'neighbors');
  assert.deepEqual(pathsOf(isolated), ['isolated.py']);
  assert.equal(isolated.edgeCount, 0);
});

test('impact includes transitive importers, excludes dependencies, and never reverses arrows', () => {
  const view = buildGraphView(chain, 'database.py', 'impact');
  assert.deepEqual(pathsOf(view), ['main.py', 'auth.py', 'database.py']);
  assert.ok(classesOf(view, 'main.py').includes('indirect'));
  assert.ok(classesOf(view, 'auth.py').includes('incoming'));
  assert.deepEqual(view.elements.filter(item => item.data.source).map(item => [item.data.source, item.data.target]),
    [[fileId('main.py'), fileId('auth.py')], [fileId('auth.py'), fileId('database.py')]]);
  assert.deepEqual(pathsOf(buildGraphView(chain, 'main.py', 'impact')), ['main.py']);
});

test('circular view omits bridges between separate groups and never marks them circular', () => {
  const report = reportFor(['a.py', 'b.py', 'c.py', 'd.py', 'outside.py'],
    [['a.py', 'b.py'], ['b.py', 'a.py'], ['b.py', 'c.py'], ['c.py', 'd.py'], ['d.py', 'c.py']],
    {}, [['a.py', 'b.py'], ['c.py', 'd.py']]);
  const view = buildGraphView(report, 'outside.py', 'cycles');
  assert.equal(view.nodeCount, 4);
  assert.equal(view.edgeCount, 4);
  assert.equal(view.includesSelected, false);
  assert.ok(view.elements.every(item => item.classes.split(' ').includes('circular')));
  const all = buildGraphView(report, 'b.py', 'all');
  const bridge = all.elements.find(item => item.data.source === fileId('b.py') && item.data.target === fileId('c.py'));
  assert.ok(!bridge.classes.split(' ').includes('circular'));
  assert.ok(classesOf(all, 'a.py').includes('both'));
});

test('empty and acyclic graphs produce an honest empty circular view', () => {
  const empty = buildGraphView(reportFor([], []), '', 'all');
  assert.equal(empty.nodeCount, 0);
  assert.equal(empty.edgeCount, 0);
  assert.equal(empty.includesSelected, false);
  assert.equal(buildGraphView(chain, 'auth.py', 'cycles').elements.length, 0);
});

test('paths with punctuation, duplicate basenames, and edge-like names remain distinct', () => {
  const paths = ['pkg/a.py', 'other/a.py', 'odd [folder]/é.py', 'file:x.py', 'edge:x.py'];
  const pairs = paths.slice(1).map(path => [paths[0], path]);
  const report = reportFor(paths, pairs);
  const before = JSON.stringify(report);
  const view = buildGraphView(report, paths[2], 'all');
  const cy = cytoscape({ headless: true, elements: view.elements });
  try {
    assert.equal(new Set(view.elements.map(item => item.data.id)).size, 9);
    assert.equal(cy.nodes().length, 5);
    assert.equal(cy.edges().length, 4);
    assert.equal(cy.getElementById(fileId(paths[2])).data('label'), paths[2]);
    assert.equal(JSON.stringify(report), before);
  } finally { cy.destroy(); }
});

test('200-file project keeps each induced view internally consistent', () => {
  const paths = Array.from({ length: 200 }, (_, index) => `pkg/file_${index}.py`);
  const pairs = paths.slice(1).map((path, index) => [path, paths[index]]);
  const report = reportFor(paths, pairs, { [paths[0]]: { indirect_dependents: paths.slice(2) } });
  for (const mode of ['all', 'neighbors', 'impact', 'cycles']) {
    const view = buildGraphView(report, paths[0], mode);
    const ids = new Set(view.elements.filter(item => item.data.path).map(item => item.data.id));
    for (const edge of view.elements.filter(item => item.data.source)) {
      assert.ok(ids.has(edge.data.source) && ids.has(edge.data.target));
    }
    assert.equal(view.nodeCount, { all: 200, neighbors: 2, impact: 200, cycles: 0 }[mode]);
  }
});

test('long labels fit their boxes without changing file identity', () => {
  const path = `folder/${'long_name_'.repeat(15)}.py`;
  const view = buildGraphView(reportFor([path], []), path, 'all');
  assert.ok(view.elements[0].data.label.length <= 60);
  assert.equal(view.elements[0].data.path, path);
  assert.equal(view.elements[0].data.id, fileId(path));
});
