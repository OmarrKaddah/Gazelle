import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from embedding import embedQuery
from docAccess import allowedDocs


load_dotenv()
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']

RRF_K = 60
OVERFETCH = 4  # vector index is filtered after retrieval; pull more so the budget survives the access filter


def vectorQuery(tx, queryEmbedding, k, allowed):
    res = tx.run(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $kPool, $emb) YIELD node, score
        WITH node, score WHERE node.docName IN $allowed
        WITH node, score ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        emb=queryEmbedding,
        kPool=k * OVERFETCH,
        k=k,
        allowed=allowed,
    )
    rows = [dict(r) for r in res]
    print(f"[retriever] vectorQuery returned {len(rows)} rows", flush=True)
    return rows


def fulltextQuery(tx, query, k, allowed):
    res = tx.run(
        """
        CALL db.index.fulltext.queryNodes('chunk_text', $searchText) YIELD node, score
        WITH node, score WHERE node.docName IN $allowed
        ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        searchText=query,
        k=k,
        allowed=allowed,
    )
    rows = [dict(r) for r in res]
    print(f"[retriever] fulltextQuery returned {len(rows)} rows", flush=True)
    return rows


def graphExpand(tx, seedChunkIds, hops, allowed):
    res = tx.run(
        f"""
        MATCH (seed:Chunk) WHERE seed.chunkId IN $seedIds
        MATCH (seedEnt:Entity)-[:MENTIONED_IN]->(seed)
        MATCH path = (seedEnt)-[*1..{hops}]-(relEnt:Entity)
        WHERE NONE(r IN relationships(path) WHERE type(r) = 'MENTIONED_IN')
        MATCH (relEnt)-[:MENTIONED_IN]->(neighbor:Chunk)
        WHERE NOT neighbor.chunkId IN $seedIds AND neighbor.docName IN $allowed
        WITH neighbor, count(DISTINCT relEnt) AS overlap
        RETURN neighbor.chunkId AS chunkId, neighbor.text AS text,
               neighbor.sectionPath AS sectionPath, neighbor.pages AS pages,
               neighbor.docName AS docName, overlap
        ORDER BY overlap DESC
        LIMIT 20
        """,
        seedIds=seedChunkIds,
        allowed=allowed,
    )
    rows = [dict(r) for r in res]
    print(f"[retriever] graphExpand returned {len(rows)} rows", flush=True)
    return rows


def rrfFuse(rankedLists, topK):
    scores = {}
    items = {}
    for rankedList in rankedLists:
        for rank, item in enumerate(rankedList):
            cid = item['chunkId']
            scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
            items[cid] = item
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:topK]
    return [{**items[cid], 'score': s, 'source': 'hybrid'} for cid, s in ranked]


def vectorSearch(query, k, allowed):
    print(
        f"[retriever] vectorSearch query={query!r} k={k} allowed={allowed}",
        flush=True,
    )
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            results = session.execute_read(vectorQuery, emb, k, allowed)
    print(f"[retriever] vectorSearch returned {len(results)} chunks", flush=True)
    for r in results:
        r['source'] = 'vector'
    return results


def hybridSearch(query, k, allowed):
    print(
        f"[retriever] hybridSearch query={query!r} k={k} allowed={allowed}",
        flush=True,
    )
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            v = session.execute_read(vectorQuery, emb, k * 2, allowed)
            f = session.execute_read(fulltextQuery, query, k * 2, allowed)
    print(
        f"[retriever] hybridSearch vector={len(v)} fulltext={len(f)} fused={k}",
        flush=True,
    )
    return rrfFuse([v, f], topK=k)


def graphSearch(query, k, hops, allowed):
    print(
        f"[retriever] graphSearch query={query!r} k={k} hops={hops} allowed={allowed}",
        flush=True,
    )
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            seeds = session.execute_read(vectorQuery, emb, k, allowed)
            if not seeds:
                print(
                    "[retriever] graphSearch found no vector seeds; falling back to fulltext seeds",
                    flush=True,
                )
                seeds = session.execute_read(fulltextQuery, query, k, allowed)
            seedIds = [s['chunkId'] for s in seeds]
            neighbors = session.execute_read(graphExpand, seedIds, hops, allowed) if seedIds else []
    print(
        f"[retriever] graphSearch seeds={len(seeds)} neighbors={len(neighbors)}",
        flush=True,
    )
    for s in seeds:
        s['source'] = 'seed'
    for n in neighbors:
        n['source'] = 'neighbor'
        n['score'] = float(n.get('overlap', 0))
    return seeds + neighbors


def retrieve(query, mode='vector', k=5, hops=1, clearance='public'):
    allowed = allowedDocs(clearance)
    print(
        f"[retriever] retrieve query={query!r} mode={mode} clearance={clearance} allowedDocs={allowed}",
        flush=True,
    )
    if not allowed:
        print(f"[retriever] no documents allowed for clearance={clearance}", flush=True)
        return []
    if mode == 'vector':
        return vectorSearch(query, k, allowed)
    if mode == 'hybrid':
        return hybridSearch(query, k, allowed)
    if mode == 'graph':
        return graphSearch(query, k, hops, allowed)
    print(f"[retriever] unknown mode={mode!r}", flush=True)
    return []
