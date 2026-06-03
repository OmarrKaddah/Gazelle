import _bootstrap
import numpy as np
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from loadGraph import loadAdjacency
from ppr import ppr, uniformSeed


HOPS = 3
MIN_SEED_DEGREE = 5
MAX_SEED_DEGREE = 50
TOP_K = 20
ALPHA = 0.15


PICK_SEED_CYPHER = """
MATCH (s:Entity)-[r]-(n:Entity)
WHERE s.docName = 'icij'
WITH s, count(DISTINCT n) AS deg
WHERE deg >= $minDeg AND deg <= $maxDeg
RETURN s.canonicalId AS id, s.canonicalName AS name, deg
ORDER BY rand()
LIMIT 1
"""


def neighborhoodQuery(hops):
    return f"""
    MATCH (seed:Entity {{canonicalId: $seedId}})
    MATCH (seed)-[*1..{hops}]-(n:Entity)
    WITH seed, collect(DISTINCT n) AS ns
    WITH ns + [seed] AS nodes
    UNWIND nodes AS a
    UNWIND nodes AS b
    MATCH (a)-[r]->(b)
    RETURN a.canonicalId AS src, b.canonicalId AS dst
    """


def fetchNames(ids):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            res = session.run(
                """
                MATCH (e:Entity) WHERE e.canonicalId IN $ids
                RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type
                """,
                ids=list(ids),
            )
            return {r['id']: (r['name'], r['type']) for r in res}


def fetchSeedNeighbors(seedId):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            res = session.run(
                """
                MATCH (s:Entity {canonicalId: $id})-[r]-(n:Entity)
                RETURN DISTINCT n.canonicalId AS id
                """,
                id=seedId,
            )
            return {r['id'] for r in res}


def pickSeed():
    #go through every entity count unique neighbors keep only b/w 5-50 pick one at random
    #5-50 3ashan mayrag3sh star nodes nodes connected le kol haga mostly leaves and leaves score the same
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:

        with driver.session() as session:
            row = session.run(
                PICK_SEED_CYPHER,
                minDeg=MIN_SEED_DEGREE,
                maxDeg=MAX_SEED_DEGREE,
            ).single()
            assert row is not None, f'no ICIJ entity with degree in [{MIN_SEED_DEGREE}, {MAX_SEED_DEGREE}]'
            return row['id'], row['name'], row['deg']


def main():
    seedId, seedName, seedDeg = pickSeed()
    print(f'seed: id={seedId} name={seedName!r} full-graph degree={seedDeg}')

    print(f'loading {HOPS}-hop neighborhood around seed')
    adj, idToIdx, idxToId = loadAdjacency(neighborhoodQuery(HOPS), undirected=True, seedId=seedId)
    n = adj.shape[0]
    nnz = adj.nnz
    print(f'loaded subgraph: {n} nodes, {nnz} non-zeros (~{nnz // 2} undirected edges)')

    seedIdx = idToIdx[seedId]

    seed = uniformSeed(n, [seedIdx])
    scores = ppr(adj, seed, alpha=ALPHA)
    print(f'ppr done. sum={scores.sum():.6f} (should be ~1.0)')

    order = np.argsort(-scores)[:TOP_K]
    topIds = [idxToId[i] for i in order]

    names = fetchNames(topIds + [seedId])
    actualNeighbors = fetchSeedNeighbors(seedId)
    print(f'seed has {len(actualNeighbors)} direct neighbors in full graph')

    print(f'\ntop {TOP_K} by PPR score (α={ALPHA}, seed={seedId}):')
    print(f'  {"rank":>4} {"score":>10} {"hop":>4} {"type":<18} {"name"}')
    for rank, i in enumerate(order, start=1):
        cid = idxToId[i]
        name, etype = names.get(cid, ('?', '?'))
        isSeed = cid == seedId
        isNeighbor = cid in actualNeighbors
        hop = 'seed' if isSeed else ('1' if isNeighbor else '2+')
        nameStr = (name or '')[:60]
        print(f'  {rank:>4} {scores[i]:>10.6f} {hop:>4} {(etype or "")[:18]:<18} {nameStr}')


if __name__ == '__main__':
    main()
