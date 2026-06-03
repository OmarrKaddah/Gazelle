import time
import statistics
import numpy as np
import networkx as nx
from leiden import leiden, modularity
from clusterMetrics import nmi

# Tier-1 algorithm validation against ground-truth communities, measured by NMI.
# Three benchmarks:
#   LFR      — synthetic, planted communities, swept over the mixing parameter mu.
#   football — 115 college teams, 12 conferences = ground truth.
#   email-Eu — 1005 people, 42 departments = ground truth.
# networkx Louvain is the reference baseline throughout. networkx is used only to
# build/generate graphs and as that baseline; the algorithm under test is ours.


def adjacencyOf(G):
    return nx.to_scipy_sparse_array(G, format='csr', dtype=np.float64)


def louvainLabels(G):
    label = {}
    for c, nodes in enumerate(nx.community.louvain_communities(G, seed=0)):
        for u in nodes:
            label[u] = c
    return [label[u] for u in G.nodes]


def labelsFromAttribute(G, attr):
    ids = {}
    return [ids.setdefault(frozenset(G.nodes[u][attr]), len(ids)) for u in G.nodes]


# ── LFR: NMI vs mu, averaged over realizations ───────────────────

def lfrGraph(mu, seed):
    # max_community is capped so no single community swallows the graph, and the
    # degree is high enough that communities are dense and detectable.
    try:
        G = nx.LFR_benchmark_graph(
            n=500, tau1=3, tau2=1.5, mu=mu,
            average_degree=12, min_community=20, max_community=50,
            max_degree=50, seed=seed, max_iters=500,
        )
    except nx.ExceededMaxIterations:
        return None
    G = nx.Graph(G)                     # collapse the multi/self edges LFR adds
    G.remove_edges_from(nx.selfloop_edges(G))
    return G


def runLFR(reps=5):
    print('LFR — NMI vs mu (mean +/- std over realizations)', flush=True)
    print(f'  {"mu":>5} {"ours":>16} {"louvain":>16} {"reps":>5}', flush=True)
    for mu in (0.1, 0.2, 0.3, 0.4, 0.5):
        ours, louvain = [], []
        seed = 0
        while len(ours) < reps and seed < 50:
            G = lfrGraph(mu, seed)
            seed += 1
            if G is None:
                continue
            adj = adjacencyOf(G)
            truth = labelsFromAttribute(G, 'community')
            ours.append(nmi(list(leiden(adj)), truth))
            louvain.append(nmi(louvainLabels(G), truth))
        cell = lambda v: f'{statistics.mean(v):.3f}+/-{statistics.pstdev(v):.3f}'
        print(f'  {mu:>5} {cell(ours):>16} {cell(louvain):>16} {len(ours):>5}', flush=True)


# ── real-world labeled graphs ────────────────────────────────────

def footballGraph():
    G = nx.read_gml('datasets/football.gml', label='id')
    truth = [G.nodes[u]['value'] for u in G.nodes]   # conference id
    return G, truth


def emailGraph():
    dept = {}
    for line in open('datasets/email-labels.txt'):
        node, d = line.split()
        dept[int(node)] = int(d)
    G = nx.Graph()
    G.add_nodes_from(dept)
    for line in open('datasets/email.txt'):
        a, b = line.split()
        G.add_edge(int(a), int(b))
    G.remove_edges_from(nx.selfloop_edges(G))
    truth = [dept[u] for u in G.nodes]
    return G, truth


def evaluate(name, G, truth):
    adj = adjacencyOf(G)
    ours = leiden(adj)
    print(
        f'{name}: nodes={G.number_of_nodes()} truth_comms={len(set(truth))} '
        f'| ours NMI={nmi(list(ours), truth):.3f} '
        f'louvain NMI={nmi(louvainLabels(G), truth):.3f} '
        f'| Q(ours)={modularity(adj, ours):.3f} found={len(set(ours))}',
        flush=True,
    )


# ── Leiden vs Louvain: the connected-communities guarantee ───────
# NMI ties at the ceiling on easy graphs, so it doesn't show Leiden's real
# advantage. The advantage is structural: Louvain can output communities that
# are internally disconnected; Leiden's refinement makes that impossible. We
# measure the defect directly — what fraction of each method's communities are
# disconnected — plus modularity and runtime, on graphs large enough to expose it.

def communitiesFromLabels(labels):
    groups = {}
    for node, c in enumerate(labels):
        groups.setdefault(c, []).append(node)
    return list(groups.values())


def disconnectedFraction(G, communities):
    bad = sum(not nx.is_connected(G.subgraph(c)) for c in communities)
    return bad / len(communities)


def compare(name, G):
    nodes = list(G.nodes)

    t = time.perf_counter()
    ours = leiden(adjacencyOf(G))
    tOurs = time.perf_counter() - t
    oursComms = [[nodes[i] for i in c] for c in communitiesFromLabels(ours)]

    t = time.perf_counter()
    louvain = nx.community.louvain_communities(G, seed=0)
    tLouvain = time.perf_counter() - t

    print(f'{name}: n={G.number_of_nodes()} edges={G.number_of_edges()}', flush=True)
    for label, comms, secs in (('ours', oursComms, tOurs), ('louvain', louvain, tLouvain)):
        print(
            f'  {label:<8} comms={len(comms):4d}  disconnected={disconnectedFraction(G, comms):6.1%}'
            f'  Q={nx.community.modularity(G, [set(c) for c in comms]):.3f}  {secs:6.2f}s',
            flush=True,
        )


def runCompare():
    print('Leiden vs Louvain — disconnected-community rate, modularity, runtime', flush=True)
    compare('football', footballGraph()[0])
    compare('email-Eu', emailGraph()[0])
    bigLFR = lfrGraph(0.45, seed=1)
    compare('LFR n=500 mu=0.45', bigLFR)


def main():
    runLFR()
    print(flush=True)
    evaluate('football', *footballGraph())
    evaluate('email-Eu', *emailGraph())
    print(flush=True)
    runCompare()


if __name__ == '__main__':
    main()
