import networkx as nx
from leiden import leiden, modularity
from clusterMetrics import nmi
from validateLeiden import adjacencyOf, evaluate




def coraGraph():
    label = {}
    for line in open('datasets/cora/cora.content'):
        parts = line.split()
        label[parts[0]] = parts[-1]          # paper_id -> subject class
    G = nx.Graph()
    G.add_nodes_from(label)
    for line in open('datasets/cora/cora.cites'):
        a, b = line.split()
        if a in label and b in label:
            G.add_edge(a, b)
    truth = [label[u] for u in G.nodes]
    return G, truth


def resolutionSweep(G, truth):

    print('cora — NMI vs resolution (lower = fewer, bigger communities)', flush=True)
    adj = adjacencyOf(G)
    for r in (0.2, 0.4, 0.6, 0.8, 1.0):
        labels = leiden(adj, resolution=r)
        print(f'  res={r:>3}  found={len(set(labels)):3d}  NMI={nmi(list(labels), truth):.3f}', flush=True)


if __name__ == '__main__':
    G, truth = coraGraph()
    evaluate('cora', G, truth)
    print(flush=True)
    resolutionSweep(G, truth)
