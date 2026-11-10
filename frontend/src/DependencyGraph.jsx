import React, { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { buildGraphView } from './graph-model.js';

const styles = [
  { selector: 'node', style: {
    'shape': 'round-rectangle', 'width': 168, 'height': 54,
    'background-color': '#223650', 'border-width': 1.5, 'border-color': '#6682a4',
    'label': 'data(label)', 'color': '#edf4ff', 'font-family': 'monospace', 'font-size': 12,
    'text-valign': 'center', 'text-halign': 'center', 'text-wrap': 'wrap',
    'text-max-width': 152, 'text-overflow-wrap': 'anywhere',
  } },
  { selector: 'edge', style: {
    'width': 1.5, 'line-color': '#667e9d', 'target-arrow-color': '#667e9d',
    'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'arrow-scale': 1.1,
    'opacity': 0.65,
  } },
  { selector: 'node.outgoing', style: { 'background-color': '#214d75', 'border-color': '#83bfff' } },
  { selector: 'node.incoming', style: { 'background-color': '#654720', 'border-color': '#efc074' } },
  { selector: 'node.both, node.indirect', style: { 'background-color': '#4d386e', 'border-color': '#c2a3f2' } },
  { selector: 'edge.connected', style: { 'width': 2.5, 'opacity': 1, 'line-color': '#b4c9df', 'target-arrow-color': '#b4c9df' } },
  { selector: 'node.circular', style: { 'border-color': '#ff9da9', 'border-width': 3, 'border-style': 'dashed' } },
  { selector: 'edge.circular', style: { 'line-color': '#ff9da9', 'target-arrow-color': '#ff9da9', 'line-style': 'dashed', 'opacity': 1 } },
  { selector: 'node.focused', style: { 'background-color': '#83ddc7', 'color': '#102d2b', 'border-width': 4, 'border-color': '#d0fff3', 'font-weight': 'bold' } },
];

function arrange(cy, layout) {
  if (!cy.nodes().length) return;
  cy.layout(layout === 'network' ? {
    name: 'cose', animate: false, randomize: true, padding: 40,
    boundingBox: { x1: 0, y1: 0, w: cy.width(), h: cy.height() },
    nodeDimensionsIncludeLabels: true, componentSpacing: 100,
    nodeRepulsion: () => 18000, idealEdgeLength: () => 140, numIter: 500,
  } : {
    name: 'breadthfirst', directed: true, circle: false, grid: false,
    spacingFactor: 1.1, padding: 40, nodeDimensionsIncludeLabels: true, animate: false,
  }).run();
  // A single file should remain a normal-sized box, rather than fill the map.
  if (cy.zoom() > 1.2) { cy.zoom(1.2); cy.center(); }
}

export default function DependencyGraph({ report, selected, onSelect }) {
  const [mode, setMode] = useState(report.graph.nodes.length > 25 ? 'neighbors' : 'all');
  const [layout, setLayout] = useState('network');
  const [hovered, setHovered] = useState('');
  const container = useRef(null);
  const instance = useRef(null);
  const selectRef = useRef(onSelect);
  const rendered = useRef({ signature: '', layout: '' });
  const view = useMemo(() => buildGraphView(report, selected, mode), [report, selected, mode]);
  useEffect(() => { selectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    const cy = cytoscape({
      container: container.current, elements: [], style: styles,
      minZoom: 0.04, maxZoom: 3, boxSelectionEnabled: false,
      autounselectify: true, layout: { name: 'preset' },
    });
    instance.current = cy;
    cy.on('tap', 'node', event => selectRef.current(event.target.data('path')));
    cy.on('mouseover', 'node', event => setHovered(event.target.data('path')));
    cy.on('mouseout', 'node', () => setHovered(''));
    const observer = new ResizeObserver(() => cy.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      cy.destroy();
      instance.current = null;
      rendered.current = { signature: '', layout: '' };
    };
  }, []);

  useEffect(() => {
    const cy = instance.current;
    const signature = JSON.stringify(view.elements.map(element => element.data.id));
    const changed = signature !== rendered.current.signature;
    cy.batch(() => {
      if (changed) { cy.elements().remove(); cy.add(view.elements); }
      else view.elements.forEach(element => cy.getElementById(element.data.id).classes(element.classes));
    });
    if (changed || layout !== rendered.current.layout) {
      arrange(cy, layout);
      setHovered('');
    }
    rendered.current = { signature, layout };
  }, [view, layout]);

  function fit() {
    const cy = instance.current;
    if (!cy?.nodes().length) return;
    cy.fit(undefined, 40);
    if (cy.zoom() > 1.2) { cy.zoom(1.2); cy.center(); }
  }

  function zoom(factor) {
    const cy = instance.current;
    cy.zoom({ level: Math.min(cy.maxZoom(), Math.max(cy.minZoom(), cy.zoom() * factor)),
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }

  return <section className="graph-panel" aria-labelledby="graph-title">
    <div className="section-heading"><div><p className="eyebrow">VISUAL MAP</p><h3 id="graph-title">Follow the file connections</h3></div>
      <a className="small" href="#file-details">Read selected file details ↓</a></div>
    <p id="graph-help" className="small muted"><strong>A → B means A imports B.</strong> Drag a box to move it; drag the background to pan. Scroll or use the buttons to zoom. Select any box to explore that file.</p>
    <div className="graph-toolbar">
      <label>Map view<select value={mode} onChange={event => setMode(event.target.value)}>
        <option value="all">Whole project</option><option value="neighbors">Selected file + connections</option>
        <option value="impact">Potential change impact</option><option value="cycles">Circular groups</option>
      </select></label>
      <label className="graph-file-choice">Selected file<select value={selected} onChange={event => onSelect(event.target.value)}>
        {report.graph.nodes.map(node => <option key={node.id} value={node.id}>{node.id}</option>)}
      </select></label>
      <label>Layout<select value={layout} onChange={event => setLayout(event.target.value)}>
        <option value="network">Spread out</option><option value="layers">Layers</option>
      </select></label>
    </div>
    <div className="graph-caption" role="status">
      Showing {view.nodeCount} of {report.graph.nodes.length} files · {view.edgeCount} of {report.graph.edges.length} connections
      {mode === 'neighbors' && <span> · Only the selected file, its imports, and its importers.</span>}
      {mode === 'impact' && <span> · Selected file and its direct/indirect dependents. Arrows still point from importer to imported file.</span>}
      {mode === 'cycles' && <span> · Only connections inside circular groups.</span>}
    </div>
    <div className="graph-stage">
      <div ref={container} className="graph-canvas" role="img" aria-label={`Dependency map showing ${view.nodeCount} Python files and ${view.edgeCount} import connections. Use the selected file control or file list to explore without a mouse.`} aria-describedby="graph-help" />
      {!view.nodeCount && <p className="graph-empty">{mode === 'cycles' ? 'No circular groups found in this project.' : 'No analyzed files to show.'}</p>}
      <div className="graph-navigation" aria-label="Map controls">
        <button type="button" className="secondary" aria-label="Zoom in" onClick={() => zoom(1.3)} disabled={!view.nodeCount}>+</button>
        <button type="button" className="secondary" aria-label="Zoom out" onClick={() => zoom(1 / 1.3)} disabled={!view.nodeCount}>−</button>
        <button type="button" className="secondary" onClick={fit} disabled={!view.nodeCount}>Fit map</button>
        <button type="button" className="secondary" onClick={() => arrange(instance.current, layout)} disabled={!view.nodeCount}>Rearrange</button>
      </div>
    </div>
    <div className="graph-legend" aria-label="Map legend">
      <span><i className="swatch focused" />Selected file</span>
      {mode !== 'impact' && <span><i className="swatch outgoing" />Imported by selected file</span>}
      <span><i className="swatch incoming" />Imports selected file</span>
      <span><i className="swatch indirect" />{mode === 'impact' ? 'Indirect dependent' : 'Imports in both directions'}</span>
      <span><i className="swatch circular" />Circular group (dashed)</span>
    </div>
    <p className="graph-selection small">{hovered ? `Pointing at: ${hovered}` : `Selected: ${selected || 'none'}`}
      {!view.includesSelected && selected && ' · This file is outside the current map view.'}</p>
    {mode === 'impact' && <p className="small muted">These files may need attention after a change; this does not mean they will break.</p>}
    <p className="small muted">This map shows resolved local imports, including isolated files in the whole-project view. It does not show function calls or execution order.</p>
  </section>;
}
