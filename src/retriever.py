import re

from neo4j import GraphDatabase
from embedding import embedQuery
from docAccess import allowedDocs
from localRetrieve import getLocalIndex
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DB, RRF_K, OVERFETCH

_LUCENE_SPECIAL = re.compile(r'[+\-&|!(){}\[\]^"~*?:\\/]')


def sanitizeFulltext(query):
    return _LUCENE_SPECIAL.sub(' ', query).strip() or '*'


def vectorQuery(tx, queryEmbedding, k, allowed):
    res = tx.run(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $kPool, $emb) YIELD node, score
        WITH node, score WHERE node.docName IN $allowed
        WITH node, score ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        emb=queryEmbedding, kPool=k * OVERFETCH, k=k, allowed=allowed,
    )
    return [dict(r) for r in res]


def fulltextQuery(tx, query, k, allowed):
    res = tx.run(
        """
        CALL db.index.fulltext.queryNodes('chunk_text', $searchText) YIELD node, score
        WITH node, score WHERE node.docName IN $allowed
        ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        searchText=sanitizeFulltext(query), k=k, allowed=allowed,
    )
    return [dict(r) for r in res]


def rrfFuse(rankedLists, topK):
    scores = {}
    items = {}
    for rankedList in rankedLists:
        for rank, item in enumerate(rankedList):
            cid = item['chunkId']
            scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
            items[cid] = item
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:topK]
    return [{**items[cid], 'score': s, 'source': 'fusion'} for cid, s in ranked]


def vectorSearch(query, k, allowed):
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session(database=NEO4J_DB) as session:
            results = session.execute_read(vectorQuery, emb, k, allowed)
    print(f"[retriever] vectorSearch returned {len(results)} chunks", flush=True)
    for r in results:
        r['source'] = 'vector'
    return results


def fusionSearch(query, k, allowed):
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session(database=NEO4J_DB) as session:
            v = session.execute_read(vectorQuery, emb, k * 2, allowed)
            f = session.execute_read(fulltextQuery, query, k * 2, allowed)
    return rrfFuse([v, f], topK=k)


def hybridRetrieve(query, k, clearance):
    allowed = allowedDocs(clearance)
    if not allowed:
        return {'seeds': [], 'chunks': [], 'pathEdges': []}
    fusionChunks = fusionSearch(query, k, allowed)
    graphResult = getLocalIndex().retrieve(query, k=k, allowedDocs=allowed)
    for c in graphResult['chunks']:
        c['source'] = 'graph'
    scores = {}
    items = {}
    for rank, c in enumerate(fusionChunks):
        cid = c['chunkId']
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        items[cid] = c
    for rank, c in enumerate(graphResult['chunks']):
        cid = c['chunkId']
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        if cid not in items:
            items[cid] = c
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    chunks = [{**items[cid], 'score': s, 'source': 'hybrid'} for cid, s in ranked]
    return {'chunks': chunks, 'seeds': graphResult['seeds'], 'pathEdges': graphResult['pathEdges']}


def graphRetrieve(query, k, clearance):
    # Local arm: PPR over the RELATED + SYNONYM entity graph (warm LocalIndex singleton).
    # Returns chunks (clearance-filtered) plus provenance (seeds + path edges) for the UI.
    allowed = allowedDocs(clearance)
    if not allowed:
        return {'seeds': [], 'chunks': [], 'pathEdges': []}
    result = getLocalIndex().retrieve(query, k=k, allowedDocs=allowed)
    for c in result['chunks']:
        c['source'] = 'graph'
    return result


def retrieve(query, mode='vector', k=5, clearance='public'):
    allowed = allowedDocs(clearance)
    if not allowed:
        return {'chunks': [], 'seeds': [], 'pathEdges': []}
    if mode == 'vector':
        chunks = vectorSearch(query, k, allowed)
        return {'chunks': chunks, 'seeds': [], 'pathEdges': []}
    if mode == 'fusion':
        chunks = fusionSearch(query, k, allowed)
        return {'chunks': chunks, 'seeds': [], 'pathEdges': []}
    if mode == 'graph':
        return graphRetrieve(query, k, clearance)
    if mode == 'hybrid':
        return hybridRetrieve(query, k, clearance)
    return {'chunks': [], 'seeds': [], 'pathEdges': []}
