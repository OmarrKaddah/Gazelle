import _bootstrap  # noqa: F401
import sys
from seeder import loadEntityEmbeddings, seedFromQuery

docName = sys.argv[1]
query = ' '.join(sys.argv[2:])

idxToId, idxToName, embs = loadEntityEmbeddings(docName)
nameById = dict(zip(idxToId, idxToName))
seeds = seedFromQuery(query, idxToId, embs)

print(f'query : {query}')
print(f'corpus: {docName} ({len(idxToId)} entities)')
print(f'{"mass":>6}  {"cos":>5}  name')
for cid, sim, mass in seeds:
    print(f'{mass:6.3f}  {sim:5.3f}  {nameById[cid]}')
