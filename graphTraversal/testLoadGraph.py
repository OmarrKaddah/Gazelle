import _bootstrap
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from loadGraph import loadAdjacency


SEED_EDGES = [
    ('a', 'b'),
    ('a', 'c'),
    ('b', 'c'),
    ('b', 'd'),
    ('c', 'd'),
    ('d', 'e'),
]
NODES = ['a', 'b', 'c', 'd', 'e']
NEIGHBORS = {
    'a': {'b', 'c'},
    'b': {'a', 'c', 'd'},
    'c': {'a', 'b', 'd'},
    'd': {'b', 'c', 'e'},
    'e': {'d'},
}


def writeFixture():
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.run("MATCH (n:PprTest) DETACH DELETE n")
            for nid in NODES:
                session.run("CREATE (:PprTest {id: $id})", id=nid)
            for s, d in SEED_EDGES:
                session.run(
                    """
                    MATCH (s:PprTest {id: $s}), (d:PprTest {id: $d})
                    CREATE (s)-[:LINK]->(d)
                    """,
                    s=s, d=d,
                )


def deleteFixture():
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.run("MATCH (n:PprTest) DETACH DELETE n")


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {name}{" — " + detail if detail else ""}')
    return condition


def testRoundTrip():
    print('test: id ↔ index round-trips')
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    _, idToIdx, idxToId = loadAdjacency(query)
    ok = all(idxToId[idToIdx[nid]] == nid for nid in NODES)
    return check('idxToId[idToIdx[x]] == x for all nodes', ok)


def testNodeCount():
    print('test: every node appears in the index')
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    _, idToIdx, _ = loadAdjacency(query)
    return check(
        f'index has {len(NODES)} entries',
        len(idToIdx) == len(NODES),
        f'got {len(idToIdx)}',
    )


def testEdgeCountUndirected():
    print('test: undirected matrix has 2× edge count non-zeros')
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    adj, _, _ = loadAdjacency(query, undirected=True)
    expected = 2 * len(SEED_EDGES)
    return check(
        f'nnz == {expected}',
        adj.nnz == expected,
        f'got {adj.nnz}',
    )


def testEdgeCountDirected():
    print('test: directed matrix has exactly edge count non-zeros')
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    adj, _, _ = loadAdjacency(query, undirected=False)
    return check(
        f'nnz == {len(SEED_EDGES)}',
        adj.nnz == len(SEED_EDGES),
        f'got {adj.nnz}',
    )


def testSymmetric():
    print('test: undirected matrix is symmetric')
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    adj, _, _ = loadAdjacency(query, undirected=True)
    diff = (adj - adj.T)
    return check('A == Aᵀ', diff.nnz == 0)


def testNeighborsMatch():
    print("test: each row's non-zero columns equal that node's neighbors")
    query = "MATCH (s:PprTest)-[:LINK]->(d:PprTest) RETURN s.id AS src, d.id AS dst"
    adj, idToIdx, idxToId = loadAdjacency(query, undirected=True)
    ok = True
    details = []
    for nid in NODES:
        row = adj.getrow(idToIdx[nid]).indices
        actual = {idxToId[i] for i in row}
        expected = NEIGHBORS[nid]
        if actual != expected:
            ok = False
            details.append(f'{nid}: got {actual}, expected {expected}')
    return check('neighbors match for all nodes', ok, '; '.join(details))


def main():
    print('writing fixture...')
    writeFixture()
    try:
        tests = [
            testRoundTrip,
            testNodeCount,
            testEdgeCountUndirected,
            testEdgeCountDirected,
            testSymmetric,
            testNeighborsMatch,
        ]
        results = []
        for t in tests:
            results.append(t())
            print()
        passed = sum(results)
        total = len(results)
        print(f'== {passed}/{total} passed ==')
    finally:
        print('cleaning up fixture...')
        deleteFixture()


if __name__ == '__main__':
    main()
