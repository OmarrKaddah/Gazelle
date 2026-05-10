import json
import os
from pathlib import Path
from gliner import GLiNER
from dotenv import load_dotenv
from ontology import ENTITIES


load_dotenv()

THRESHOLD = float(os.getenv('GLINER_THRESHOLD', '0.5'))
GLINER_MODEL = os.getenv('GLINER_MODEL', 'NAMAA-Space/gliner_arabic-v2.1')
labels = list(ENTITIES.keys())

print(f"Loading GLiNER model: {GLINER_MODEL}", flush=True)
model = GLiNER.from_pretrained(GLINER_MODEL)
print(f"Model loaded. Threshold: {THRESHOLD}", flush=True)


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def extractFromChunk(chunk):
    spans = model.predict_entities(chunk['text'], labels, threshold=THRESHOLD)
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


def extractEntities(docName):
    chunks = loadChunks(docName)
    entities = []
    for c in chunks:
        entities.extend(extractFromChunk(c))
    return entities


def dumpEntities(entities, docName):
    Path('extractions').mkdir(exist_ok=True)
    Path(f'extractions/{docName}_entities.json').write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
