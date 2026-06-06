import os
from collections import Counter, defaultdict
import networkx as nx
import matplotlib.pyplot as plt
from leiden import leiden
from clusterMetrics import nmi
from validateLeiden import adjacencyOf, footballGraph


OUT = 'figures'


def correctness(detected, truth):
    # map each detected community to its majority true label, then flag each node
    members = defaultdict(list)
    for node, c in enumerate(detected):
        members[c].append(truth[node])
    majority = {c: Counter(ts).most_common(1)[0][0] for c, ts in members.items()}
    return [truth[node] == majority[c] for node, c in enumerate(detected)]


def panel(name, G, truth, nodeLabels):
    nodes = list(G.nodes)
    detected = list(leiden(adjacencyOf(G)))
    correct = correctness(detected, truth)
    pos = nx.spring_layout(G, seed=1, k=0.35)
    palette = {k: plt.cm.tab20(i % 20) for i, k in enumerate(sorted(set(truth)))}

    fig, ax = plt.subplots(figsize=(20, 16))
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.12)
    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_size=260,
        node_color=[palette[t] for t in truth],
        edgecolors=['#15a015' if ok else '#d00000' for ok in correct],
        linewidths=2.5,
    )
    rightLabels = {u: nodeLabels[u] for i, u in enumerate(nodes) if correct[i]}
    wrongLabels = {u: nodeLabels[u] for i, u in enumerate(nodes) if not correct[i]}
    nx.draw_networkx_labels(G, pos, labels=rightLabels, ax=ax, font_size=5)
    nx.draw_networkx_labels(G, pos, labels=wrongLabels, ax=ax, font_size=7,
                            font_color='#d00000', font_weight='bold')
    ax.set_title(
        f'{name}: {sum(correct)}/{len(correct)} correctly grouped — '
        f'NMI {nmi(detected, truth):.3f}  '
        f'(fill = true label, green ring = correct, red ring = misgrouped)'
    )
    ax.axis('off')
    fig.savefig(f'{OUT}/{name}.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'wrote {OUT}/{name}.png  ({sum(correct)}/{len(correct)} correct)', flush=True)


def plotFootball():
    G, truth = footballGraph()
    names = {u: G.nodes[u]['label'] for u in G.nodes}
    panel('football', G, truth, names)


def plotKarate():
    G = nx.karate_club_graph()
    truth = [0 if G.nodes[u]['club'] == 'Mr. Hi' else 1 for u in G.nodes]
    names = {u: str(u) for u in G.nodes}
    panel('karate', G, truth, names)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    plotKarate()
    plotFootball()
