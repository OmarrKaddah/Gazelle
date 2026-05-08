import _bootstrap  # noqa: F401
import json
import random
from pathlib import Path

random.seed(42)
SAMPLE_SIZE = 10  # chunks for gold-set hand-annotation


def loadAllChunks():
    chunks = []
    for f in Path('chunks').glob('*.json'):
        chunks.extend(json.loads(f.read_text(encoding='utf-8')))
    return chunks


def sectionRoot(chunk):
    return chunk['sectionPath'][0] if chunk['sectionPath'] else '_'


def stratifiedSample(chunks, n):
    byRoot = {}
    for c in chunks:
        byRoot.setdefault(sectionRoot(c), []).append(c)
    sample = []
    per = max(1, n // len(byRoot))
    for group in byRoot.values():
        sample.extend(random.sample(group, min(per, len(group))))
    return sample[:n]


def goldTemplate(chunk):
    return {
        'chunkId': chunk['chunkId'],
        'docName': chunk['docName'],
        'sectionPath': chunk['sectionPath'],
        'text': chunk['text'],
        'expectedEntities': [],       # [{type, text}]
        'expectedRelationships': [],  # [{subject, predicate, object}]
    }


chunks = loadAllChunks()
sample = stratifiedSample(chunks, SAMPLE_SIZE)
gold = [goldTemplate(c) for c in sample]
Path('gold').mkdir(exist_ok=True)
Path('gold/sample.json').write_text(
    json.dumps(gold, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
print(f"Sampled {len(gold)} chunks. Fill in expectedEntities/expectedRelationships in gold/sample.json.")
