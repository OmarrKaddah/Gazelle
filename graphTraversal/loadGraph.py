import _bootstrap
from scipy.sparse import csr_matrix
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def fetchEdges(query, **params):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            res = session.run(query, **params)
            records = list(res)
    if not records:
        return []
    hasWeight = 'weight' in records[0].keys()
    return [(r['src'], r['dst'], float(r['weight']) if hasWeight else 1.0) for r in records]


def buildIndex(edges):
    ids = set()
    for s, d, _ in edges:
        ids.add(s)
        ids.add(d)
    idxToId = sorted(ids)
    idToIdx = {i: k for k, i in enumerate(idxToId)}
    return idToIdx, idxToId


def buildAdjacency(edges, idToIdx, undirected=True):
    rows, cols, data = [], [], []
    for s, d, w in edges:
        i, j = idToIdx[s], idToIdx[d]
        rows.append(i)
        cols.append(j)
        data.append(w)
        if undirected:
            rows.append(j)
            cols.append(i)
            data.append(w)
    n = len(idToIdx)
    return csr_matrix((data, (rows, cols)), shape=(n, n))


def loadAdjacency(query, undirected=True, **params):
    edges = fetchEdges(query, **params)
    idToIdx, idxToId = buildIndex(edges)
    adjacency = buildAdjacency(edges, idToIdx, undirected=undirected)
    return adjacency, idToIdx, idxToId
