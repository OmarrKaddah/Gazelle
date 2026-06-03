import _bootstrap  # noqa: F401
import sys
from retrieve import RetrievalIndex

docName = sys.argv[1]
query = ' '.join(sys.argv[2:])

index = RetrievalIndex(docName)
seeds, chunks = index.retrieve(query)

print(f'query : {query}')
print(f'corpus: {docName}')
print()
print('seeds:')
for cid, sim, mass in seeds:
    print(f'  {mass:.3f}  cos={sim:.3f}  {cid}')
print()
print(f'top {len(chunks)} chunks:')
for c in chunks:
    print(f'  score={c["score"]:.5f}  {c["chunkId"]}')
    contribs = ', '.join(f'{cid}({s:.4f})' for cid, s in c['contributors'])
    print(f'    contributors: {contribs}')
    print(f'    text: {c["text"][:240]}...')
    print()
