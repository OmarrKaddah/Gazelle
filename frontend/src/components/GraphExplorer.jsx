import React, { useEffect, useMemo, useRef, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import { SearchIcon, RefreshIcon, XIcon, ChevronDownIcon } from './Icons';
import { authHeaders } from '../hooks/useAuth';

cytoscape.use(fcose);

const ENTITY_COLORS = {
  Person: '#7A6FB5',
  BankingInstitution: '#062F62',  // ADIB navy
  RegulatoryBody: '#009CDA',      // ADIB bright blue
  Law: '#0078A8',                 // ADIB deep blue
  Article: '#5A6776',
  License: '#C9A961',             // gold
  Document: '#A88840',            // deep gold
  FinancialInstrument: '#0E4282', // brand soft
  RegulatoryRequirement: '#A8628F',
  MonetaryAmount: '#7D8B5C',
  Date: '#94A2B0',
};

const ALL_TYPES = Object.keys(ENTITY_COLORS);

const cyStyle = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'font-family': 'Inter, sans-serif',
      'font-size': '10px',
      'font-weight': 500,
      'color': '#0F1B2D',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 6,
      'width': 28,
      'height': 28,
      'border-width': 2,
      'border-color': '#F8FBFE',
      'text-wrap': 'ellipsis',
      'text-max-width': '140px',
      'transition-property': 'background-color, border-color, width, height',
      'transition-duration': '180ms',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#009CDA',
      'width': 38,
      'height': 38,
      'z-index': 100,
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-color': '#009CDA',
      'border-width': 3,
    },
  },
  {
    selector: 'node.faded',
    style: {
      opacity: 0.18,
    },
  },
  {
    selector: 'edge',
    style: {
      'curve-style': 'bezier',
      'width': 1.4,
      'line-color': '#5BB8E8',
      'target-arrow-color': '#5BB8E8',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'label': 'data(label)',
      'font-family': 'Inter, sans-serif',
      'font-size': '8.5px',
      'font-weight': 500,
      'color': '#5A6776',
      'text-rotation': 'autorotate',
      'text-background-color': '#F8FBFE',
      'text-background-opacity': 0.95,
      'text-background-padding': '3px',
      'text-background-shape': 'roundrectangle',
      'opacity': 0.7,
      'transition-property': 'opacity, line-color, target-arrow-color, width',
      'transition-duration': '180ms',
    },
  },
  {
    selector: 'edge:selected, edge.highlighted',
    style: {
      'width': 2.4,
      'opacity': 1,
      'line-color': '#062F62',
      'target-arrow-color': '#062F62',
      'color': '#062F62',
    },
  },
  {
    selector: 'edge.faded',
    style: {
      opacity: 0.06,
    },
  },
];

const layout = {
  name: 'fcose',
  animate: true,
  animationDuration: 600,
  randomize: false,
  quality: 'default',
  nodeRepulsion: 5000,
  idealEdgeLength: 90,
  edgeElasticity: 0.3,
  gravity: 0.2,
  numIter: 2000,
  tile: true,
  fit: true,
  padding: 60,
};

export default function GraphExplorer() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [activeTypes, setActiveTypes] = useState(new Set(ALL_TYPES));
  const [selected, setSelected] = useState(null);
  const cyRef = useRef(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      params.set('limit', '300');
      const response = await fetch(`/api/graph?${params}`, { headers: { ...authHeaders() } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setGraph(data);
    } catch (err) {
      setError(err.message);
      setGraph({ nodes: [], edges: [] });
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const elements = useMemo(() => {
    const nodes = graph.nodes
      .filter((n) => activeTypes.has(n.data.type))
      .map((n) => ({
        data: {
          ...n.data,
          color: ENTITY_COLORS[n.data.type] || '#9C968E',
        },
      }));
    const visibleIds = new Set(nodes.map((n) => n.data.id));
    const edges = graph.edges.filter(
      (e) => visibleIds.has(e.data.source) && visibleIds.has(e.data.target)
    );
    return [...nodes, ...edges];
  }, [graph, activeTypes]);

  const stats = useMemo(() => {
    const byType = {};
    for (const n of graph.nodes) {
      byType[n.data.type] = (byType[n.data.type] || 0) + 1;
    }
    return { total: graph.nodes.length, edges: graph.edges.length, byType };
  }, [graph]);

  const onCyReady = (cy) => {
    cyRef.current = cy;
    cy.on('tap', 'node', (e) => {
      const node = e.target;
      setSelected({
        kind: 'node',
        data: node.data(),
        connected: node.connectedEdges().map((edge) => ({
          predicate: edge.data('label'),
          direction: edge.data('source') === node.id() ? 'out' : 'in',
          other: edge.data('source') === node.id()
            ? cy.getElementById(edge.data('target')).data()
            : cy.getElementById(edge.data('source')).data(),
        })),
      });
      cy.elements().addClass('faded');
      node.removeClass('faded').addClass('highlighted');
      node.neighborhood().removeClass('faded').addClass('highlighted');
    });
    cy.on('tap', (e) => {
      if (e.target === cy) {
        setSelected(null);
        cy.elements().removeClass('faded highlighted');
      }
    });
  };

  const toggleType = (type) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const expandNeighbors = async (nodeId) => {
    try {
      const response = await fetch(
        `/api/graph?seed=${encodeURIComponent(nodeId)}&hops=1&limit=80`,
        { headers: { ...authHeaders() } }
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      // merge into existing graph
      setGraph((prev) => {
        const existingNodes = new Set(prev.nodes.map((n) => n.data.id));
        const existingEdges = new Set(prev.edges.map((e) => e.data.id));
        return {
          nodes: [...prev.nodes, ...data.nodes.filter((n) => !existingNodes.has(n.data.id))],
          edges: [...prev.edges, ...data.edges.filter((e) => !existingEdges.has(e.data.id))],
        };
      });
      if (cyRef.current) {
        cyRef.current.layout(layout).run();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ExplorerHeader
        search={search}
        setSearch={setSearch}
        onSearch={load}
        loading={loading}
        stats={stats}
      />
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 relative cy-canvas">
          {elements.length === 0 && !loading && (
            <EmptyState error={error} onRetry={load} />
          )}
          {elements.length > 0 && (
            <CytoscapeComponent
              elements={elements}
              style={{ width: '100%', height: '100%' }}
              layout={layout}
              stylesheet={cyStyle}
              cy={onCyReady}
              wheelSensitivity={0.25}
              minZoom={0.2}
              maxZoom={3}
            />
          )}
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-cream/40 backdrop-blur-sm pointer-events-none">
              <div className="flex items-center gap-2 px-4 py-2 bg-cream-soft border border-cream-border rounded-full shadow-sm">
                <div className="w-2 h-2 rounded-full bg-gold animate-pulse" />
                <span className="text-[12px] text-ink-muted font-medium">Loading graph…</span>
              </div>
            </div>
          )}
          <Legend stats={stats} active={activeTypes} onToggle={toggleType} />
        </div>
        {selected && (
          <Inspector
            selected={selected}
            onClose={() => {
              setSelected(null);
              if (cyRef.current) cyRef.current.elements().removeClass('faded highlighted');
            }}
            onExpand={expandNeighbors}
          />
        )}
      </div>
    </div>
  );
}

function ExplorerHeader({ search, setSearch, onSearch, loading, stats }) {
  return (
    <header className="border-b border-cream-border px-6 py-3 flex items-center gap-3 bg-cream/80 backdrop-blur-sm">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="font-serif text-[18px] text-brand leading-none">Graph Explorer</span>
        <span className="text-[11px] text-ink-faint font-mono">
          {stats.total} nodes · {stats.edges} edges
        </span>
      </div>
      <div className="flex-1" />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSearch();
        }}
        className="flex items-center gap-2 bg-cream-soft border border-cream-border rounded-full px-3 py-1 focus-within:border-gold transition"
      >
        <SearchIcon className="w-3.5 h-3.5 text-ink-faint" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search entity name…"
          dir="auto"
          className="bg-transparent text-[12px] text-ink placeholder-ink-faint focus:outline-none w-56"
        />
      </form>
      <button
        onClick={onSearch}
        disabled={loading}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-br from-adib to-adib-deep text-white text-[11px] font-medium hover:from-adib-deep hover:to-brand transition disabled:opacity-60 shadow-sm"
      >
        <RefreshIcon className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        <span>Refresh</span>
      </button>
    </header>
  );
}

function EmptyState({ error, onRetry }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="text-center max-w-sm">
        <div className="w-12 h-12 rounded-full bg-cream-deeper border border-cream-border mx-auto mb-4 flex items-center justify-center">
          <SearchIcon className="w-5 h-5 text-ink-faint" />
        </div>
        <div className="font-serif text-[20px] text-brand mb-1">No graph data</div>
        <div className="text-[13px] text-ink-muted mb-4">
          {error
            ? `Could not load graph: ${error}`
            : 'No nodes match your filters. Try clearing the search or enabling more entity types.'}
        </div>
        <button
          onClick={onRetry}
          className="px-3 py-1.5 rounded-full bg-brand text-gold text-[12px] font-medium hover:bg-brand-soft transition"
        >
          Reload
        </button>
      </div>
    </div>
  );
}

function Legend({ stats, active, onToggle }) {
  const [expanded, setExpanded] = useState(true);
  const visibleTypes = ALL_TYPES.filter((t) => stats.byType[t] > 0);
  if (visibleTypes.length === 0) return null;

  return (
    <div className="absolute bottom-4 left-4 bg-cream-soft/95 backdrop-blur border border-cream-border rounded-xl shadow-lg max-w-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left"
      >
        <span className="text-[10px] uppercase tracking-[0.16em] text-ink-faint font-semibold">
          Entity Types
        </span>
        <ChevronDownIcon className={`w-3.5 h-3.5 text-ink-faint transition ${expanded ? '' : 'rotate-180'}`} />
      </button>
      {expanded && (
        <div className="px-2 pb-2 space-y-0.5">
          {visibleTypes.map((type) => (
            <button
              key={type}
              onClick={() => onToggle(type)}
              className={`w-full flex items-center gap-2 px-2 py-1 rounded text-[11.5px] transition ${
                active.has(type) ? 'text-ink' : 'text-ink-faint line-through opacity-60'
              } hover:bg-cream-deeper`}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-1 ring-cream-border"
                style={{ background: ENTITY_COLORS[type] }}
              />
              <span className="flex-1 text-left">{type}</span>
              <span className="text-[10px] text-ink-faint font-mono">{stats.byType[type]}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Inspector({ selected, onClose, onExpand }) {
  const { data, connected } = selected;
  const color = ENTITY_COLORS[data.type] || '#9C968E';

  return (
    <aside className="w-80 border-l border-cream-border bg-cream-soft flex flex-col flex-shrink-0 animate-slideIn">
      <div className="px-5 py-4 border-b border-cream-border">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div
            className="px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold"
            style={{
              background: color,
              color: ['RegulatoryBody', 'License', 'Document', 'Article'].includes(data.type) ? '#062F62' : '#FFFFFF',
            }}
          >
            {data.type}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-cream-deeper text-ink-faint hover:text-ink transition"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="font-serif text-[18px] text-brand leading-tight" dir="auto">
          {data.name || data.label}
        </div>
        <div className="text-[11px] text-ink-faint font-mono mt-1 break-all">{data.id}</div>
        {typeof data.chunkCount === 'number' && (
          <div className="text-[11px] text-ink-muted mt-2">
            Mentioned in <span className="font-medium text-ink">{data.chunkCount}</span> chunk{data.chunkCount === 1 ? '' : 's'}
          </div>
        )}
        <button
          onClick={() => onExpand(data.id)}
          className="mt-3 w-full px-3 py-1.5 rounded-md bg-gradient-to-br from-adib to-adib-deep text-white text-[11px] font-medium hover:from-adib-deep hover:to-brand transition shadow-sm"
        >
          Expand neighbors
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-3">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-2">
          Relationships ({connected.length})
        </div>
        {connected.length === 0 && (
          <div className="text-[12px] text-ink-faint italic">No visible connections.</div>
        )}
        <div className="space-y-1.5">
          {connected.map((c, i) => (
            <RelationRow key={i} relation={c} />
          ))}
        </div>
      </div>
    </aside>
  );
}

function RelationRow({ relation }) {
  const otherColor = ENTITY_COLORS[relation.other.type] || '#9C968E';
  return (
    <div className="bg-cream-frame border border-cream-border rounded-md p-2.5">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[9.5px] uppercase tracking-wider text-ink-faint font-semibold">
          {relation.direction === 'out' ? '→' : '←'} {relation.predicate}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ background: otherColor }}
        />
        <span className="text-[12px] text-ink truncate" dir="auto">
          {relation.other.name || relation.other.label}
        </span>
      </div>
    </div>
  );
}
