'''
k-hop baseline retriever adapted to walk the MuSiQue KG.

We don't call src/retriever.py's graphSearch directly because:
  1. It filters paths by RELATIONSHIP_DESCRIPTIONS (CBE Arabic relation ontology —
     ISSUED_BY, AMENDS, etc.). Our MuSiQue edges (COOCCURS_WITH, SYNONYM, TRIPLE)
     aren't in that table, so the path filter would reject every edge.
  2. It projects chunks via r.chunkIds (a property stored on typed CBE edges).
     Our schemaless edges don't carry that; we use MENTIONED_IN instead.
  3. Its module-level code pre-embeds CBE relation descriptions at import time
     via Ollama — wasted work for a MuSiQue eval.

The k-hop *algorithm* is identical: cosine-seed entities, enumerate paths
up to a fixed depth, score by entity cosine, aggregate to chunks. Only the
schema-specific glue differs (Cypher queries, edge types, projection path).
cosineSim is kept as a local 8-line copy rather than imported to avoid
triggering retriever.py's module-level Ollama embed call at import time.
'''

import _bootstrap  # noqa: F401
import numpy as np
from neo4j import GraphDatabase
from embedding import embedQuery
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


SEED_K = 8
PATH_DEPTH = 3
PATH_LIMIT = 300


def cosineSim(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(a @ b / (na * nb))


def seedEntities(tx, queryEmb, docName, k):
    res = tx.run(
        '''
        CALL db.index.vector.queryNodes('entity_embedding', $kPool, $emb) YIELD node, score
        WHERE node.docName = $docName
        RETURN node.canonicalId AS id, node.canonicalName AS name, score
        ORDER BY score DESC LIMIT $k
        ''',
        emb=queryEmb,
        kPool=k * 4,
        docName=docName,
        k=k,
    )
    return [dict(r) for r in res]


def extractPaths(tx, seedIds, docName, depth, limit):
    cypher = (
        'MATCH (seed:Entity {docName: $docName}) WHERE seed.canonicalId IN $seedIds '
        f'MATCH path = (seed)-[:COOCCURS_WITH|SYNONYM|TRIPLE *1..{depth}]-(target:Entity {{docName: $docName}}) '
        'RETURN [n IN nodes(path) | n.canonicalId] AS entityIds, '
        '       [n IN nodes(path) | n.canonicalName] AS entityNames, '
        '       length(path) AS hops '
        'LIMIT $limit'
    )
    res = tx.run(cypher, seedIds=seedIds, docName=docName, limit=limit)
    return [dict(r) for r in res]


def fetchEntityEmbeddings(tx, entityIds, docName):
    res = tx.run(
        '''
        MATCH (e:Entity {docName: $docName}) WHERE e.canonicalId IN $ids
        RETURN e.canonicalId AS id, e.embedding AS emb
        ''',
        ids=list(entityIds),
        docName=docName,
    )
    return {r['id']: r['emb'] for r in res if r['emb']}


def fetchEntityToChunks(tx, entityIds, docName):
    res = tx.run(
        '''
        UNWIND $ids AS eid
        MATCH (e:Entity {canonicalId: eid})-[:MENTIONED_IN]->(c:Chunk {docName: $docName})
        RETURN eid AS entityId, collect(c.chunkId) AS chunkIds
        ''',
        ids=list(entityIds),
        docName=docName,
    )
    return {r['entityId']: r['chunkIds'] for r in res}


def fetchChunkText(tx, chunkIds, docName):
    res = tx.run(
        '''
        MATCH (c:Chunk {docName: $docName}) WHERE c.chunkId IN $ids
        RETURN c.chunkId AS chunkId, c.text AS text
        ''',
        ids=list(chunkIds),
        docName=docName,
    )
    return {r['chunkId']: r['text'] for r in res}


def scorePath(path, queryEmb, embMap):
    embs = [embMap[eid] for eid in path['entityIds'] if eid in embMap]
    if not embs:
        return 0.0
    return float(np.mean([cosineSim(queryEmb, e) for e in embs]))


def khopSearch(query, docName, topK=10, depth=PATH_DEPTH):
    queryEmb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            seeds = session.execute_read(seedEntities, queryEmb, docName, SEED_K)
            if not seeds:
                return []
            seedIds = [s['id'] for s in seeds]
            paths = session.execute_read(extractPaths, seedIds, docName, depth, PATH_LIMIT)
            if not paths:
                return []

            entityIds = set()
            for p in paths:
                entityIds.update(p['entityIds'])
            embMap = session.execute_read(fetchEntityEmbeddings, entityIds, docName)
            entityToChunks = session.execute_read(fetchEntityToChunks, entityIds, docName)

    chunkScore = {}
    for p in paths:
        score = scorePath(p, queryEmb, embMap)
        for eid in p['entityIds']:
            for chunkId in entityToChunks.get(eid, ()):
                if score > chunkScore.get(chunkId, 0):
                    chunkScore[chunkId] = score

    ranked = sorted(chunkScore.items(), key=lambda x: -x[1])[:topK]
    return [{'chunkId': cid, 'score': s, 'text': '', 'contributors': []} for cid, s in ranked]


class KhopIndex:
    def __init__(self, docName, depth=PATH_DEPTH):
        self.docName = docName
        self.depth = depth
        print(f'[index] {docName} [khop depth={depth}]')

    def retrieve(self, query, topK=10, **_ignored):
        chunks = khopSearch(query, self.docName, topK=topK, depth=self.depth)
        return [], chunks
