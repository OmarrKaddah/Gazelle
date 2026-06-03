import numpy as np
import networkx as nx
from leiden import leiden, modularity
from clusterMetrics import nmi

# networkx is used for graph construction and as a reference only — the
# algorithm under test (leiden, modularity) is our own.


def adjacencyOf(G):
    return nx.to_scipy_sparse_array(G, format='csr', dtype=np.float64)


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {name}{" — " + detail if detail else ""}')
    return condition


def communities(labels):
    groups = {}
    for node, c in enumerate(labels):
        groups.setdefault(c, []).append(node)
    return list(groups.values())


def testModularityMatchesNetworkx():
    print('test: our modularity matches networkx for a hand-set partition')
    G = nx.karate_club_graph()
    labels = [0 if G.nodes[i]['club'] == 'Mr. Hi' else 1 for i in G.nodes]
    ours = modularity(adjacencyOf(G), labels)
    ref = nx.community.modularity(G, [{i for i in G.nodes if labels[i] == c} for c in (0, 1)])
    return check('|ours - networkx| < 1e-9', abs(ours - ref) < 1e-9, f'ours={ours:.6f} nx={ref:.6f}')


def testTwoTriangles():
    print('test: two triangles joined by one edge split into exactly 2 communities')
    G = nx.Graph([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)])
    labels = leiden(adjacencyOf(G))
    comms = communities(labels)
    split = {frozenset(c) for c in comms}
    expected = {frozenset({0, 1, 2}), frozenset({3, 4, 5})}
    return check('communities == {0,1,2},{3,4,5}', split == expected, f'found={[sorted(c) for c in comms]}')


def testThreeCliqueRing():
    print('test: ring of three 4-cliques recovers 3 communities')
    G = nx.Graph()
    cliques = [range(0, 4), range(4, 8), range(8, 12)]
    for c in cliques:
        G.add_edges_from((a, b) for a in c for b in c if a < b)
    G.add_edges_from([(3, 4), (7, 8), (11, 0)])   # one bridge between consecutive cliques
    labels = leiden(adjacencyOf(G))
    return check('3 communities found', len(communities(labels)) == 3, f'n={len(communities(labels))}')


def testKarateModularity():
    print('test: karate-club partition reaches a sensible modularity')
    G = nx.karate_club_graph()
    labels = leiden(adjacencyOf(G))
    q = modularity(adjacencyOf(G), labels)
    louvain = nx.community.louvain_communities(G, seed=0)
    qLouvain = nx.community.modularity(G, louvain)
    return check('Q within 0.02 of networkx Louvain', q > qLouvain - 0.02, f'ours={q:.4f} louvain={qLouvain:.4f}')


def testKarateFactions():
    print('test: karate communities largely recover the two real factions')
    G = nx.karate_club_graph()
    truth = [0 if G.nodes[i]['club'] == 'Mr. Hi' else 1 for i in G.nodes]
    labels = leiden(adjacencyOf(G))
    score = nmi(list(labels), truth)
    return check('NMI vs factions > 0.5', score > 0.5, f'NMI={score:.3f}, {len(communities(labels))} communities')


def testCommunitiesConnected():
    print('test: every detected community is internally connected (the Leiden guarantee)')
    G = nx.karate_club_graph()
    labels = leiden(adjacencyOf(G))
    allConnected = all(nx.is_connected(G.subgraph(c)) for c in communities(labels))
    return check('all communities connected', allConnected)


def main():
    tests = [
        testModularityMatchesNetworkx,
        testTwoTriangles,
        testThreeCliqueRing,
        testKarateModularity,
        testKarateFactions,
        testCommunitiesConnected,
    ]
    results = []
    for t in tests:
        results.append(t())
        print()
    print(f'== {sum(results)}/{len(results)} passed ==')


if __name__ == '__main__':
    main()
