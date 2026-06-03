import _bootstrap  # noqa: F401
import json
import re
import sys
import numpy as np
from collections import Counter
from pathlib import Path
from tqdm import tqdm
from kgBuild import loadNameLookup
from seeder import loadEntityEmbeddings
from embedding import embedTexts


docName = sys.argv[1] if len(sys.argv) > 1 else 'musique'
EMBED_BATCH = 32

data = json.loads(Path(f'extractions/{docName}_triples.json').read_text(encoding='utf-8'))
lookup = loadNameLookup(docName)

print(f'[diag] collecting unique unmatched endpoints...', flush=True)
seen = set()
for entry in data:
    for triple in entry['triples']:
        if len(triple) != 3:
            continue
        for end in (triple[0], triple[2]):
            norm = end.lower().strip()
            if norm and norm not in lookup:
                seen.add(end)
orphans = sorted(seen)
print(f'[diag] {len(orphans)} unique unmatched endpoints', flush=True)

print(f'[diag] loading entity embeddings...', flush=True)
entityIds, entityNames, entityEmbs = loadEntityEmbeddings(docName)
print(f'[diag] {len(entityIds)} entity embeddings', flush=True)


def tokensOf(text):
    return frozenset(re.findall(r'\w+', text.lower()))


entityTokens = [tokensOf(n) for n in entityNames]


def subsetMatch(text):
    toks = tokensOf(text)
    if not toks:
        return None
    for i, etoks in enumerate(entityTokens):
        if etoks and toks <= etoks and toks != etoks:
            return entityNames[i]
    for i, etoks in enumerate(entityTokens):
        if etoks and etoks <= toks and toks != etoks:
            return entityNames[i]
    return None


subsetHits = {}
needEmbed = []
for orphan in orphans:
    m = subsetMatch(orphan)
    if m is not None:
        subsetHits[orphan] = m
    else:
        needEmbed.append(orphan)

print(f'[diag] {len(subsetHits)} caught by token-subset, {len(needEmbed)} need embedding check', flush=True)

embMatches = {}  # orphan -> (bestName, bestSim)
print(f'[diag] embedding {len(needEmbed)} orphans...', flush=True)
for i in tqdm(range(0, len(needEmbed), EMBED_BATCH), desc='embed', file=sys.stdout):
    batch = needEmbed[i:i + EMBED_BATCH]
    try:
        embs = embedTexts(batch)
    except RuntimeError:
        continue
    arr = np.array(embs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    sims = arr @ entityEmbs.T
    for j, orphan in enumerate(batch):
        bestIdx = int(np.argmax(sims[j]))
        embMatches[orphan] = (entityNames[bestIdx], float(sims[j, bestIdx]))

# Tier the embedding matches
tiers = [
    ('emb>=0.95', 0.95, 1.01),
    ('emb 0.90-0.95', 0.90, 0.95),
    ('emb 0.85-0.90', 0.85, 0.90),
    ('emb 0.80-0.85', 0.80, 0.85),
    ('emb <0.80 (novel)', 0.0, 0.80),
]

buckets = Counter()
buckets['subset'] = len(subsetHits)
tierMembers = {name: [] for name, _, _ in tiers}
for orphan, (best, sim) in embMatches.items():
    for name, lo, hi in tiers:
        if lo <= sim < hi:
            buckets[name] += 1
            tierMembers[name].append((orphan, best, sim))
            break

total = sum(buckets.values())
print()
print(f'unique unmatched endpoints: {len(orphans)}')
print()
print(f'  {"subset":17s}  {buckets["subset"]:6d}  ({100*buckets["subset"]/max(total,1):5.1f}%)')
for name, _, _ in tiers:
    n = buckets.get(name, 0)
    pct = 100 * n / max(total, 1)
    print(f'  {name:17s}  {n:6d}  ({pct:5.1f}%)')
print()

# Show samples from each bucket so user can judge precision
def printSamples(label, items, n=8):
    print(f'sample {label}:')
    for orphan, best, sim in items[:n]:
        print(f'  {sim:.3f}  {orphan!r:40s} -> {best!r}')
    print()

for name, _, _ in tiers:
    if tierMembers[name]:
        printSamples(name, tierMembers[name])

# Also show some subset hits for sanity
print('sample subset hits:')
for orphan, best in list(subsetHits.items())[:8]:
    print(f'         {orphan!r:40s} -> {best!r}')
