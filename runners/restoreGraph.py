import _bootstrap  # noqa: F401  (puts src/ and graphTraversal/ on sys.path)
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBED_DIM

# Restore a dump produced by runners/dumpGraph.py into Neo4j: wipe the DB, recreate
# nodes/relationships, strip the transient dump keys, then rebuild the constraints
# and the vector + fulltext indexes the serving path needs. Python driver only.
#
#   python runners/restoreGraph.py dumps/cbe.jsonl
#
# Every node gets a transient :_Dump label + _dumpId so relationships can be re-wired
# by an indexed lookup; both are removed at the end.

BATCH = 1000
NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def safe(token):
    if not NAME.match(token):
        raise ValueError(f'unsafe label/type in dump: {token!r}')
    return token


def readDump(path):
    meta, nodes, rels = None, [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line:
            continue
        rec = json.loads(line)
        if rec['_t'] == 'meta':
            meta = rec
        elif rec['_t'] == 'node':
            nodes.append(rec)
        else:
            rels.append(rec)
    return meta, nodes, rels


def batched(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def wipe(session):
    session.run('MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS')


def loadNodes(session, nodes):
    byLabels = defaultdict(list)
    for n in nodes:
        key = ':'.join(safe(l) for l in n['labels'])
        byLabels[key].append({'id': n['id'], 'props': n['props']})
    session.run('CREATE INDEX dumpLookup IF NOT EXISTS FOR (n:_Dump) ON (n._dumpId)')
    for labels, rows in byLabels.items():
        labelClause = f':{labels}' if labels else ''
        cypher = f'UNWIND $rows AS r CREATE (n{labelClause}:_Dump) SET n = r.props, n._dumpId = r.id'
        for chunk in batched(rows):
            session.execute_write(lambda tx, c=chunk: tx.run(cypher, rows=c))


def loadRels(session, rels):
    byType = defaultdict(list)
    for r in rels:
        byType[safe(r['type'])].append({'s': r['s'], 't': r['t'], 'props': r['props']})
    for relType, rows in byType.items():
        cypher = (f'UNWIND $rows AS r MATCH (a:_Dump {{_dumpId: r.s}}), (b:_Dump {{_dumpId: r.t}}) '
                  f'CREATE (a)-[x:{relType}]->(b) SET x = r.props')
        for chunk in batched(rows):
            session.execute_write(lambda tx, c=chunk: tx.run(cypher, rows=c))


def stripDumpKeys(session):
    session.run('MATCH (n:_Dump) CALL { WITH n REMOVE n:_Dump, n._dumpId } IN TRANSACTIONS OF 1000 ROWS')
    session.run('DROP INDEX dumpLookup IF EXISTS')


def rebuildSchema(session):
    session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.docName IS UNIQUE')
    session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE')
    session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonicalId IS UNIQUE')
    session.run(f"CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBED_DIM}, `vector.similarity_function`: 'cosine'}}}}")
    session.run(f"CREATE VECTOR INDEX entity_embedding IF NOT EXISTS FOR (e:Entity) ON (e.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBED_DIM}, `vector.similarity_function`: 'cosine'}}}}")
    session.run(f"CREATE VECTOR INDEX community_embedding IF NOT EXISTS FOR (c:Community) ON (c.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBED_DIM}, `vector.similarity_function`: 'cosine'}}}}")
    session.run('CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]')


def restore(path):
    meta, nodes, rels = readDump(path)
    print(f'[restore] {path}: {len(nodes)} nodes, {len(rels)} rels (dump embedDim={meta and meta.get("embedDim")})')
    with driver() as d, d.session() as s:
        wipe(s)
        loadNodes(s, nodes)
        loadRels(s, rels)
        stripDumpKeys(s)
        rebuildSchema(s)
    print('[restore] done: graph loaded, constraints + vector/fulltext indexes rebuilt')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: python runners/restoreGraph.py <dump.jsonl>')
    restore(sys.argv[1])
