import _bootstrap  # noqa: F401
import sys
import numpy as np
from seeder import loadEntityEmbeddings, seedFromQuery
from loadGraph import loadAdjacency
from ppr import ppr
from retrieve import buildSeedVector, loadEntityGraph


docName = sys.argv[1]
query = sys.argv[2]
needles = sys.argv[3:]

idxToIdEmb, idxToNameEmb, embs = loadEntityEmbeddings(docName)
seeds = seedFromQuery(query, idxToIdEmb, embs)

adjacency, idToIdx, idxToId = loadEntityGraph(docName)
seedVec = buildSeedVector(seeds, idToIdx)
scores = ppr(adjacency, seedVec)

degrees = np.asarray(adjacency.sum(axis=1)).flatten()

nameById = dict(zip(idxToIdEmb, idxToNameEmb))

print(f'query: {query}')
print(f'graph: {len(idxToId)} entities')
print()
print('PPR score distribution:')
print(f'  max:   {scores.max():.5f}')
print(f'  p99:   {np.percentile(scores, 99):.5f}')
print(f'  p95:   {np.percentile(scores, 95):.5f}')
print(f'  p50:   {np.percentile(scores, 50):.5f}')
print()
print('seeds:')
for cid, sim, mass in seeds:
    idx = idToIdx.get(cid)
    if idx is None:
        print(f'  [not in graph] mass={mass:.3f}  {nameById.get(cid, cid)}')
        continue
    print(f'  score={scores[idx]:.5f}  mass={mass:.3f}  deg={int(degrees[idx]):4d}  rank={int((scores > scores[idx]).sum())+1:5d}  {nameById.get(cid, cid)}')
print()
print(f'probes for {needles}:')
for needle in needles:
    matches = [(i, cid, nameById.get(cid, cid)) for i, cid in enumerate(idxToId) if needle.lower() in nameById.get(cid, '').lower()]
    if not matches:
        print(f'  [no match for {needle}]')
        continue
    for i, cid, name in matches[:5]:
        print(f'  score={scores[i]:.5f}  deg={int(degrees[i]):4d}  rank={int((scores > scores[i]).sum())+1:5d}  {name}')
