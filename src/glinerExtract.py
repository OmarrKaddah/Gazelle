import json
import os
from pathlib import Path
from tqdm import tqdm
from gliner import GLiNER
from dotenv import load_dotenv
from ontology import ENTITIES
from config import GLINER_MODEL, GLINER_THRESHOLD

load_dotenv()

THRESHOLD = float(os.getenv('GLINER_THRESHOLD', '0.5'))
GLINER_MODEL = os.getenv('GLINER_MODEL', 'NAMAA-Space/gliner_arabic-v2.1')
labels = list(ENTITIES.keys())

print(f"Loading GLiNER model: {GLINER_MODEL}", flush=True)
model = GLiNER.from_pretrained(GLINER_MODEL)
print(f"Model loaded. Threshold: {THRESHOLD}", flush=True)


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def extractFromChunk(chunk, lang):
    model = getModel(lang)
    labels = getLabels(lang)
    spans = model.predict_entities(chunk['text'], labels, threshold=GLINER_THRESHOLD)
    return [
        {
            'chunkId': chunk['chunkId'],
            'docName': chunk['docName'],
            'text': s['text'],
            'type': s['label'],
            'start': s['start'],
            'end': s['end'],
            'score': s['score'],
        }
        for s in spans
    ]


def extractEntities(docName, lang='ar'):
    chunks = loadChunks(docName)
    print(f"[gliner] {docName}: {len(chunks)} chunks", flush=True)
    entities = []
    bar = tqdm(chunks, desc=f"{docName}", unit="chunk", file=sys.stdout)
    for c in bar:
        spans = extractFromChunk(c, lang)
        entities.extend(spans)
        bar.set_postfix(entities=len(entities))
    return entities


def dumpEntities(entities, docName):
    Path('extractions').mkdir(exist_ok=True)
    Path(f'extractions/{docName}_entities.json').write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
