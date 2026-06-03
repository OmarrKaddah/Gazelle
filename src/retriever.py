import numpy as np
from neo4j import GraphDatabase
from embedding import embedQuery, embedTexts
from ontology import RELATIONSHIP_DESCRIPTIONS
from config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    RRF_K, OVERFETCH, PATH_DEPTH, SEED_K, PATH_LIMIT,
    REL_TYPE_TOP, REL_TYPE_FLOOR, ENTITY_WEIGHT,
)


# Pre-compute relation-type embeddings once per process. RELATIONSHIP_DESCRIPTIONS
# is a small constant dict, so this is cheap and keeps query-time work minimal.
_relTypes = list(RELATIONSHIP_DESCRIPTIONS.keys())
_relTypeEmbs = dict(zip(_relTypes, embedTexts([RELATIONSHIP_DESCRIPTIONS[t] for t in _relTypes])))


def cosineSim(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(a @ b / (na * nb))


def vectorQuery(tx, queryEmbedding, k):
    print(f"[DEBUG] vectorQuery: k={k}, kPool={k * OVERFETCH}")
    res = tx.run(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $kPool, $emb) YIELD node, score
        WITH node, score ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        emb=queryEmbedding,
        kPool=k * OVERFETCH,
        k=k,
    )
    rows = [dict(r) for r in res]
    print(f"[DEBUG] vectorQuery: returned {len(rows)} rows")
    for r in rows:
        print(f"  chunkId={r['chunkId']} score={r['score']:.4f} doc={r['docName']}")
    return rows


def fulltextQuery(tx, query, k):
    print(f"[DEBUG] fulltextQuery: query={query!r}, k={k}")
    res = tx.run(
        """
        CALL db.index.fulltext.queryNodes('chunk_text', $searchText) YIELD node, score
        WITH node, score ORDER BY score DESC LIMIT $k
        RETURN node.chunkId AS chunkId, node.text AS text, node.sectionPath AS sectionPath,
               node.pages AS pages, node.docName AS docName, score
        """,
        searchText=query,
        k=k,
    )
    rows = [dict(r) for r in res]
    print(f"[DEBUG] fulltextQuery: returned {len(rows)} rows")
    for r in rows:
        print(f"  chunkId={r['chunkId']} score={r['score']:.4f} doc={r['docName']}")
    return rows


def rrfFuse(rankedLists, topK):
    print(f"[DEBUG] rrfFuse: {len(rankedLists)} lists, sizes={[len(l) for l in rankedLists]}, topK={topK}")
    scores = {}
    items = {}
    for rankedList in rankedLists:
        for rank, item in enumerate(rankedList):
            cid = item['chunkId']
            scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
            items[cid] = item
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:topK]
    print(f"[DEBUG] rrfFuse: {len(scores)} unique chunks -> top {len(ranked)}")
    return [{**items[cid], 'score': s, 'source': 'hybrid'} for cid, s in ranked]


def selectRelevantRelTypes(queryEmb):
    sims = {t: cosineSim(queryEmb, e) for t, e in _relTypeEmbs.items()}
    ranked = sorted(sims.items(), key=lambda x: -x[1])
    print(f"[DEBUG] selectRelevantRelTypes: all sims={[(t, f'{s:.4f}') for t, s in ranked]}")
    selected = [t for t, s in ranked if s >= REL_TYPE_FLOOR][:REL_TYPE_TOP]
    result = selected if selected else [ranked[0][0]]
    print(f"[DEBUG] selectRelevantRelTypes: selected={result}")
    return result


def seedEntities(tx, queryEmb, k):
    print(f"[DEBUG] seedEntities: k={k}, kPool={k * OVERFETCH}")
    res = tx.run(
        """
        CALL db.index.vector.queryNodes('entity_embedding', $kPool, $emb) YIELD node, score
        RETURN node.canonicalId AS id, node.canonicalName AS name, score
        ORDER BY score DESC
        LIMIT $k
        """,
        emb=queryEmb,
        kPool=k * OVERFETCH,
        k=k,
    )
    rows = [dict(r) for r in res]
    print(f"[DEBUG] seedEntities: returned {len(rows)} seeds")
    for r in rows:
        print(f"  id={r['id']} name={r['name']} score={r['score']:.4f}")
    return rows


def extractPaths(tx, seedIds, relTypes, depth, limit):
    print(f"[DEBUG] extractPaths: {len(seedIds)} seeds, relTypes={relTypes}, depth={depth}, limit={limit}")
    res = tx.run(
        f"""
        MATCH (seed:Entity) WHERE seed.canonicalId IN $seedIds
        MATCH path = (seed)-[*1..{depth}]-(target:Entity)
        WHERE ALL(r IN relationships(path) WHERE type(r) IN $relTypes)
        WITH path, nodes(path) AS ns, relationships(path) AS rs
        RETURN [n IN ns | n.canonicalId] AS entityIds,
               [n IN ns | n.canonicalName] AS entityNames,
               [r IN rs | type(r)] AS pathRelTypes,
               [r IN rs | r.chunkIds] AS chunkIdsLists
        LIMIT $limit
        """,
        seedIds=seedIds,
        relTypes=relTypes,
        limit=limit,
    )
    rows = [dict(r) for r in res]
    print(f"[DEBUG] extractPaths: returned {len(rows)} paths")
    return rows


def fetchEntityEmbeddings(tx, entityIds):
    print(f"[DEBUG] fetchEntityEmbeddings: fetching {len(entityIds)} entity embeddings")
    res = tx.run(
        """
        MATCH (e:Entity) WHERE e.canonicalId IN $ids
        RETURN e.canonicalId AS id, e.embedding AS emb
        """,
        ids=list(entityIds),
    )
    result = {r['id']: r['emb'] for r in res if r['emb']}
    print(f"[DEBUG] fetchEntityEmbeddings: got embeddings for {len(result)}/{len(entityIds)} entities")
    return result


def fetchChunks(tx, chunkIds):
    print(f"[DEBUG] fetchChunks: fetching {len(chunkIds)} chunks")
    res = tx.run(
        """
        MATCH (c:Chunk) WHERE c.chunkId IN $ids
        RETURN c.chunkId AS chunkId, c.text AS text, c.sectionPath AS sectionPath,
               c.pages AS pages, c.docName AS docName
        """,
        ids=list(chunkIds),
    )
    result = {r['chunkId']: dict(r) for r in res}
    print(f"[DEBUG] fetchChunks: returned {len(result)}/{len(chunkIds)} chunks")
    return result


def scorePath(path, queryEmb, embMap):
    entityEmbs = [embMap[eid] for eid in path['entityIds'] if eid in embMap]
    if not entityEmbs:
        return 0.0
    entityScore = float(np.mean([cosineSim(queryEmb, e) for e in entityEmbs]))
    relScores = [cosineSim(queryEmb, _relTypeEmbs[t]) for t in path['pathRelTypes'] if t in _relTypeEmbs]
    relScore = float(np.mean(relScores)) if relScores else 0.0
    return ENTITY_WEIGHT * entityScore + (1 - ENTITY_WEIGHT) * relScore


def collectPathChunkIds(path):
    chunkIds = set()
    for cids in path['chunkIdsLists']:
        if cids:
            chunkIds.update(cids)
    return chunkIds


def vectorSearch(query, k):
    print(f"[DEBUG] vectorSearch: query={query!r}, k={k}")
    emb = embedQuery(query)
    print(f"[DEBUG] vectorSearch: embedding computed, dim={len(emb)}")
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            results = session.execute_read(vectorQuery, emb, k)
    print(f"[retriever] vectorSearch returned {len(results)} chunks", flush=True)
    for r in results:
        r['source'] = 'vector'
    print(f"[DEBUG] vectorSearch: final results={len(results)}")
    return results


def hybridSearch(query, k):
    print(f"[DEBUG] hybridSearch: query={query!r}, k={k}")
    emb = embedQuery(query)
    print(f"[DEBUG] hybridSearch: embedding computed, dim={len(emb)}")
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            v = session.execute_read(vectorQuery, emb, k * 2)
            f = session.execute_read(fulltextQuery, query, k * 2)
    print(f"[DEBUG] hybridSearch: vector={len(v)}, fulltext={len(f)}")
    return rrfFuse([v, f], topK=k)


def graphSearch(query, k):
    print(f"[DEBUG] graphSearch: query={query!r}, k={k}")
    queryEmb = embedQuery(query)
    print(f"[DEBUG] graphSearch: embedding computed, dim={len(queryEmb)}")
    relTypes = selectRelevantRelTypes(queryEmb)

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            seeds = session.execute_read(seedEntities, queryEmb, SEED_K)
            if not seeds:
                print("[DEBUG] graphSearch: no seed entities found, returning []")
                return []
            seedIds = [s['id'] for s in seeds]
            paths = session.execute_read(extractPaths, seedIds, relTypes, PATH_DEPTH, PATH_LIMIT)
            if not paths:
                print("[DEBUG] graphSearch: no paths found, returning []")
                return []

            entityIds = set()
            for p in paths:
                entityIds.update(p['entityIds'])
            print(f"[DEBUG] graphSearch: {len(entityIds)} unique entities across all paths")
            embMap = session.execute_read(fetchEntityEmbeddings, entityIds)

            chunkIdsAll = set()
            for p in paths:
                p['score'] = scorePath(p, queryEmb, embMap)
                p['_chunkIds'] = collectPathChunkIds(p)
                chunkIdsAll.update(p['_chunkIds'])
            print(f"[DEBUG] graphSearch: {len(chunkIdsAll)} unique chunkIds from paths")

            if not chunkIdsAll:
                print("[DEBUG] graphSearch: no chunk IDs from paths, returning []")
                return []
            chunkMap = session.execute_read(fetchChunks, chunkIdsAll)

    chunkScores = {}
    chunkPaths = {}
    for p in paths:
        for cid in p['_chunkIds']:
            if cid not in chunkMap:
                continue
            if p['score'] > chunkScores.get(cid, 0):
                chunkScores[cid] = p['score']
            chunkPaths.setdefault(cid, []).append({
                'entities': p['entityNames'],
                'relations': p['pathRelTypes'],
                'score': p['score'],
            })

    ranked = sorted(chunkScores.items(), key=lambda x: -x[1])[:k]
    print(f"[DEBUG] graphSearch: {len(chunkScores)} scored chunks -> top {len(ranked)}")
    out = []
    for cid, score in ranked:
        chunk = chunkMap[cid]
        chunk['score'] = score
        chunk['source'] = 'graph'
        chunk['paths'] = sorted(chunkPaths[cid], key=lambda p: -p['score'])[:3]
        out.append(chunk)
        print(f"  chunkId={cid} score={score:.4f} doc={chunk['docName']}")
    return out


def retrieve(query, mode='vector', k=5, clearance='public'):
    print(f"[DEBUG] retrieve: query={query!r}, mode={mode}, k={k}, clearance={clearance}")
    if mode == 'vector':
        return vectorSearch(query, k)
    if mode == 'hybrid':
        return hybridSearch(query, k)
    if mode == 'graph':
        return graphSearch(query, k)
    print(f"[DEBUG] retrieve: unknown mode {mode!r}, returning []")
    return []
