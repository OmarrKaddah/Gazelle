import numpy as np
from scipy.sparse import csr_matrix
from collections import defaultdict

# Leiden community detection (Traag, Waltman, van Eck 2019), from scratch.
#
# Three passes per level, then aggregate and repeat:
#   1. local move   — Louvain greedy: move each node to the neighbouring
#                     community that most increases modularity.
#   2. refinement   — split each community into connected sub-communities by
#                     re-running local move *restricted to inside the community*,
#                     starting from singletons. This is the step Louvain lacks;
#                     it guarantees every final community is internally connected.
#   3. aggregation  — collapse each sub-community to one node, then start the
#                     next level's local move from the *unrefined* communities.
#
# Deviation from the paper: refinement is greedy, not randomised. The connected
# guarantee comes from only ever merging along an existing edge, not from the
# randomness, so we keep determinism (reproducible tests) and lose only a little
# partition-quality exploration.


def degrees(adj):
    return np.asarray(adj.sum(axis=1)).ravel()


def modularity(adj, labels, resolution=1.0):
    deg = degrees(adj)
    twoM = deg.sum()
    inside = defaultdict(float)   # 2 * internal weight per community
    total = defaultdict(float)    # total degree per community
    coo = adj.tocoo()
    for i, j, w in zip(coo.row, coo.col, coo.data):
        if labels[i] == labels[j]:
            inside[labels[i]] += w
    for node, c in enumerate(labels):
        total[c] += deg[node]
    return sum(inside[c] / twoM - resolution * (total[c] / twoM) ** 2 for c in total)


def bestCommunity(adj, labels, total, deg, twoM, i, resolution, allowed):
    # weight from node i to each candidate community, then pick the community
    # (including i's current one) with the largest modularity gain.
    ki = deg[i]
    toComm = defaultdict(float)
    for p in range(adj.indptr[i], adj.indptr[i + 1]):
        j = adj.indices[p]
        if j != i and (allowed is None or allowed[j] == allowed[i]):
            toComm[labels[j]] += adj.data[p]
    ci = labels[i]
    total[ci] -= ki
    best, bestGain = ci, toComm[ci] - resolution * ki * total[ci] / twoM
    for c, w in toComm.items():
        gain = w - resolution * ki * total[c] / twoM
        if gain > bestGain + 1e-12:
            best, bestGain = c, gain
    total[best] += ki
    return best


def localMove(adj, labels, resolution, allowed=None):
    deg = degrees(adj)
    twoM = deg.sum()
    total = defaultdict(float)
    for node, c in enumerate(labels):
        total[c] += deg[node]
    moved = True
    changed = False
    while moved:
        moved = False
        for i in range(adj.shape[0]):
            target = bestCommunity(adj, labels, total, deg, twoM, i, resolution, allowed)
            if target != labels[i]:
                labels[i] = target
                moved = changed = True
    return labels, changed


def refine(adj, parent, resolution):
    # every node starts in its own sub-community; merges are only allowed inside
    # the parent community (allowed=parent), so each sub-community stays connected.
    sub = np.arange(adj.shape[0])
    sub, _ = localMove(adj, sub, resolution, allowed=parent)
    return sub


def aggregate(adj, sub):
    order = sorted(set(sub))
    remap = {c: k for k, c in enumerate(order)}
    new = np.array([remap[c] for c in sub])
    coo = adj.tocoo()
    rows = new[coo.row]
    cols = new[coo.col]
    agg = csr_matrix((coo.data, (rows, cols)), shape=(len(order), len(order)))
    agg.sum_duplicates()   # internal edges fold into the diagonal -> degree preserved
    return agg, new


def relabel(labels):
    remap = {}
    out = np.empty(len(labels), dtype=int)
    for i, c in enumerate(labels):
        out[i] = remap.setdefault(c, len(remap))
    return out


def projectDown(part, nodeToOrig, n):
    out = np.empty(n, dtype=int)
    for node, origs in enumerate(nodeToOrig):
        for o in origs:
            out[o] = part[node]
    return out


def leidenHierarchy(adj, resolution=1.0):
    # every outer pass coarsens the partition, so the sequence of partitions IS
    # the community hierarchy: finest first, root (fewest communities) last.
    n = adj.shape[0]
    work = adj                              # current aggregated graph
    nodeToOrig = [[i] for i in range(n)]    # original nodes behind each work-node
    part = np.arange(n)                     # where this level's local move starts
    levels = []
    bestQ = -1.0
    while True:
        part, _ = localMove(work, part.copy(), resolution)
        part = relabel(part)
        proj = projectDown(part, nodeToOrig, n)
        q = modularity(adj, proj, resolution)
        if q <= bestQ + 1e-9:
            break
        bestQ = q
        levels.append(relabel(proj))

        sub = refine(work, part, resolution)
        work, newSub = aggregate(work, sub)
        nextOrig = [[] for _ in range(work.shape[0])]
        nextPart = np.empty(work.shape[0], dtype=int)
        for node in range(len(newSub)):
            nextOrig[newSub[node]].extend(nodeToOrig[node])
            nextPart[newSub[node]] = part[node]   # sub-community keeps its parent
        nodeToOrig, part = nextOrig, relabel(nextPart)
    return levels


def leiden(adj, resolution=1.0):
    return leidenHierarchy(adj, resolution)[-1]   # flat partition = root level