// Keep the backend's arrow direction: source imports target, in every view.
export const fileId = path => `file:${path}`;

export function buildGraphView(report, selected, mode) {
  const nodes = report.graph.nodes;
  const current = nodes.find(node => node.id === selected);
  const outgoing = new Set(current?.dependencies || []);
  const incoming = new Set(current?.imported_by || []);
  const indirect = new Set(report.impact[selected]?.indirect_dependents || []);
  const cycleOf = new Map();
  report.circular_dependency_groups.forEach((group, index) => {
    group.forEach(path => cycleOf.set(path, index));
  });
  let visible;
  if (mode === 'neighbors') visible = new Set([selected, ...outgoing, ...incoming]);
  else if (mode === 'impact') visible = new Set([selected, ...incoming, ...indirect]);
  else if (mode === 'cycles') visible = new Set(cycleOf.keys());
  else visible = new Set(nodes.map(node => node.id));

  const shownNodes = nodes.filter(node => visible.has(node.id));
  const shownEdges = report.graph.edges.filter(edge => visible.has(edge.source) && visible.has(edge.target)
    // Connections between different circular groups are not themselves circular.
    && (mode !== 'cycles' || cycleOf.get(edge.source) === cycleOf.get(edge.target)));
  const elements = shownNodes.map(node => {
    const classes = [];
    if (mode === 'impact') {
      if (incoming.has(node.id)) classes.push('incoming');
      else if (indirect.has(node.id)) classes.push('indirect');
    } else {
      if (outgoing.has(node.id) && incoming.has(node.id)) classes.push('both');
      else if (outgoing.has(node.id)) classes.push('outgoing');
      else if (incoming.has(node.id)) classes.push('incoming');
    }
    if (cycleOf.has(node.id)) classes.push('circular');
    if (node.id === selected) classes.push('focused');
    // Keep long paths inside a box; selection and hover still expose the full path.
    const label = node.id.length > 60 ? `${node.id.slice(0, 24)}…${node.id.slice(-32)}` : node.id;
    return { data: { id: fileId(node.id), path: node.id, label }, classes: classes.join(' ') };
  });
  shownEdges.forEach(edge => {
    const isCircular = cycleOf.has(edge.source) && cycleOf.get(edge.source) === cycleOf.get(edge.target);
    const classes = [];
    if (edge.source === selected || edge.target === selected) classes.push('connected');
    if (isCircular) classes.push('circular');
    elements.push({
      data: { id: `edge:${JSON.stringify([edge.source, edge.target])}`, source: fileId(edge.source), target: fileId(edge.target) },
      classes: classes.join(' '),
    });
  });
  return { elements, nodeCount: shownNodes.length, edgeCount: shownEdges.length, includesSelected: shownNodes.some(node => node.id === selected) };
}
