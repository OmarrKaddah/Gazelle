import _bootstrap  # noqa: F401
import json
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from llmTriples import extractTriples


DOC = 'musique'
N = 5
BACKEND = sys.argv[1] if len(sys.argv) > 1 else 'ollama'

chunks = json.loads(Path(f'chunks/{DOC}.json').read_text(encoding='utf-8'))
spans = json.loads(Path(f'extractions/{DOC}_entities.json').read_text(encoding='utf-8'))

entityNamesByChunk = defaultdict(set)
for s in spans:
    entityNamesByChunk[s['chunkId']].add(s['text'].strip())

for chunk in chunks[:N]:
    names = sorted(entityNamesByChunk[chunk['chunkId']])
    print()
    print(f'=== {chunk["chunkId"]} ({len(names)} entities) ===')
    print(f'text: {chunk["text"][:240]}...')
    print(f'entities ({len(names)}): {names[:8]}{"..." if len(names) > 8 else ""}')
    try:
        triples = extractTriples(chunk['text'], names, backend=BACKEND)
    except Exception:
        print('  [error]')
        traceback.print_exc()
        continue
    print(f'triples ({len(triples)}):')
    for s, p, o in triples:
        print(f'  ({s!r:35s}) -[{p!r}]-> ({o!r})')
