import _bootstrap  # noqa: F401  (puts src/ and graphTraversal/ on sys.path)
import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBED_DIM

# Portable Neo4j graph dump: every node + relationship streamed to one JSONL file,
# using the Python driver only (no neo4j-admin, no APOC, version-independent).
# Restore with runners/restoreGraph.py. Each line is one record:
#   {"_t": "meta",  "embedDim": ..., "nodes": N, "rels": M}      (first line)
#   {"_t": "node",  "id": <elementId>, "labels": [...], "props": {...}}
#   {"_t": "rel",   "s": <elementId>, "t": <elementId>, "type": "...", "props": {...}}
# elementId is a transient key used only to re-wire relationships on restore.

BATCH = 5000


def driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def streamNodes(session, out):
    n = 0
    res = session.run('MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props')
    for r in res:
        out.write(json.dumps({'_t': 'node', 'id': r['id'], 'labels': r['labels'], 'props': dict(r['props'])}) + '\n')
        n += 1
    return n


def streamRels(session, out):
    m = 0
    res = session.run('MATCH (a)-[r]->(b) RETURN elementId(a) AS s, elementId(b) AS t, type(r) AS type, properties(r) AS props')
    for r in res:
        out.write(json.dumps({'_t': 'rel', 's': r['s'], 't': r['t'], 'type': r['type'], 'props': dict(r['props'])}) + '\n')
        m += 1
    return m


def dump(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.part')
    with driver() as d, d.session() as s, tmp.open('w', encoding='utf-8') as out:
        out.write(json.dumps({'_t': 'meta', 'embedDim': EMBED_DIM, 'placeholder': True}) + '\n')
        nodes = streamNodes(s, out)
        rels = streamRels(s, out)
    # rewrite the meta line now that counts are known
    body = tmp.read_text(encoding='utf-8').split('\n', 1)[1]
    path.write_text(json.dumps({'_t': 'meta', 'embedDim': EMBED_DIM, 'nodes': nodes, 'rels': rels}) + '\n' + body, encoding='utf-8')
    tmp.unlink()
    size = path.stat().st_size / (1024 * 1024)
    print(f'[dump] {nodes} nodes, {rels} rels -> {path}  ({size:.1f} MB)')


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'dumps/graph.jsonl'
    dump(out)
