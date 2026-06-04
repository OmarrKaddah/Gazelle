import React, { useMemo, useRef, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';

// Animated provenance graph for a graph-mode answer: query seeds -> related entities -> cited chunks.
const STYLESHEET = [
  { selector: 'node', style: {
    'label': 'data(label)', 'font-size': 8, 'color': '#3A3226', 'text-valign': 'center', 'text-halign': 'center',
    'text-max-width': 90, 'text-wrap': 'ellipsis', 'width': 34, 'height': 34, 'border-width': 1.5,
  }},
  { selector: 'node[kind="entity"]', style: { 'background-color': '#E8EEF6', 'border-color': '#0E4282', 'color': '#062F62' }},
  { selector: 'node[kind="seed"]', style: { 'background-color': '#C9A961', 'border-color': '#A88840', 'color': '#3A3226', 'width': 42, 'height': 42, 'font-weight': 'bold' }},
  { selector: 'node[kind="chunk"]', style: { 'shape': 'round-rectangle', 'background-color': '#062F62', 'border-color': '#009CDA', 'color': '#FFFFFF', 'width': 30, 'height': 22, 'font-weight': 'bold' }},
  { selector: 'edge[kind="related"]', style: {
    'label': 'data(label)', 'font-size': 7, 'color': '#7A7263', 'text-rotation': 'autorotate', 'text-background-color': '#FBF7EF',
    'text-background-opacity': 1, 'text-background-padding': 1,
    'width': 1.5, 'line-color': '#B9C4D2', 'target-arrow-color': '#B9C4D2', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
  }},
  { selector: 'edge[kind="mention"]', style: { 'width': 1, 'line-color': '#C9A961', 'line-style': 'dashed', 'curve-style': 'bezier', 'target-arrow-shape': 'none' }},
];

function buildElements(graph, citations) {
  const seedIds = new Set(graph.seeds.map((s) => s.id));
  const nodes = new Map();
  const addEntity = (id, name) => {
    const key = 'e:' + id;
    if (!nodes.has(key)) nodes.set(key, { data: { id: key, label: name || id, kind: seedIds.has(id) ? 'seed' : 'entity' } });
  };
  graph.seeds.forEach((s) => addEntity(s.id, s.name));
  graph.pathEdges.forEach((e) => { addEntity(e.src, e.srcName); addEntity(e.dst, e.dstName); });
  citations.forEach((c) => (c.contributors || []).forEach((ct) => addEntity(ct.id, ct.name)));
  citations.forEach((c, i) => nodes.set('c:' + c.chunkId, { data: { id: 'c:' + c.chunkId, label: `[${i + 1}]`, kind: 'chunk' } }));

  const edges = [];
  graph.pathEdges.forEach((e, i) => edges.push({ data: { id: 'r' + i, source: 'e:' + e.src, target: 'e:' + e.dst, label: e.predicate || '', kind: 'related' } }));
  citations.forEach((c) => (c.contributors || []).forEach((ct) => {
    if (nodes.has('e:' + ct.id)) edges.push({ data: { id: `m:${c.chunkId}:${ct.id}`, source: 'e:' + ct.id, target: 'c:' + c.chunkId, kind: 'mention' } });
  }));
  return [...nodes.values(), ...edges];
}

export default function GraphPath({ graph, citations }) {
  const [open, setOpen] = useState(true);
  const cyRef = useRef(null);
  const elements = useMemo(() => buildElements(graph, citations), [graph, citations]);

  const runLayout = (cy) => {
    cyRef.current = cy;
    cy.layout({ name: 'cose', animate: true, animationDuration: 700, padding: 20, nodeRepulsion: 6000, idealEdgeLength: 70 }).run();
  };

  return (
    <div className="pt-3 mt-3 border-t border-cream-border">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 mb-2 group">
        <span className="text-[10px] uppercase tracking-[0.18em] text-ink-faint font-semibold">Retrieval path</span>
        <span className="text-[10px] text-gold-deep font-medium">{graph.seeds.length} seeds · {graph.pathEdges.length} edges</span>
        <span className="text-ink-faint group-hover:text-ink transition">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="rounded-lg border border-cream-border bg-cream-soft overflow-hidden" style={{ height: 280 }}>
          <CytoscapeComponent
            elements={elements}
            stylesheet={STYLESHEET}
            layout={{ name: 'preset' }}
            cy={runLayout}
            style={{ width: '100%', height: '100%' }}
            minZoom={0.2}
            maxZoom={2.5}
          />
        </div>
      )}
    </div>
  );
}
