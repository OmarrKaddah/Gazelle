import _bootstrap  # noqa: F401
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm
from llmTriples import extractTriplesBatch


docName = sys.argv[1] if len(sys.argv) > 1 else 'musique'
BATCH_SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 5
BACKEND = sys.argv[3] if len(sys.argv) > 3 else 'ollama'
PARALLEL = int(sys.argv[4]) if len(sys.argv) > 4 else 1

CHUNKS_PATH = Path(f'chunks/{docName}.json')
SPANS_PATH = Path(f'extractions/{docName}_entities.json')
OUT_PATH = Path(f'extractions/{docName}_triples.json')
SAVE_EVERY = 25

chunks = json.loads(CHUNKS_PATH.read_text(encoding='utf-8'))
spans = json.loads(SPANS_PATH.read_text(encoding='utf-8'))

entityNamesByChunk = defaultdict(set)
for s in spans:
    entityNamesByChunk[s['chunkId']].add(s['text'].strip())

existing = json.loads(OUT_PATH.read_text(encoding='utf-8')) if OUT_PATH.exists() else []
done = {r['chunkId'] for r in existing}
pending = [c for c in chunks if c['chunkId'] not in done]
print(f'[triples] {docName}: {len(chunks)} total, {len(done)} done, {len(pending)} pending (batch={BATCH_SIZE}, backend={BACKEND}, parallel={PARALLEL})', flush=True)


def saveResults(results):
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


def chunked(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def processBatch(batchChunks):
    batchInput = [(c['text'], sorted(entityNamesByChunk[c['chunkId']])) for c in batchChunks]
    try:
        return batchChunks, extractTriplesBatch(batchInput, backend=BACKEND), None
    except Exception as e:
        return batchChunks, [], str(e)[:200]


results = list(existing)
failed = []
sinceLastSave = 0
bar = tqdm(total=len(pending), desc='extract', unit='chunk', file=sys.stdout)
with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
    futures = [pool.submit(processBatch, b) for b in chunked(pending, BATCH_SIZE)]
    for future in as_completed(futures):
        batchChunks, batchTriples, err = future.result()
        bar.update(len(batchChunks))
        if err is not None:
            for c in batchChunks:
                failed.append({'chunkId': c['chunkId'], 'error': err})
            bar.set_postfix(failed=len(failed))
            continue
        for c, triples in zip(batchChunks, batchTriples):
            results.append({
                'chunkId': c['chunkId'],
                'docName': c['docName'],
                'triples': [list(t) for t in triples],
            })
        sinceLastSave += len(batchChunks)
        if sinceLastSave >= SAVE_EVERY:
            saveResults(results)
            sinceLastSave = 0
bar.close()

saveResults(results)
print(f'[triples] done: {len(results)} chunks written, {len(failed)} failed', flush=True)
for f in failed[:10]:
    print(f'  [fail] {f["chunkId"]}: {f["error"]}', flush=True)
