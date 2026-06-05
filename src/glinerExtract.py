import json
from pathlib import Path
import torch
from gliner import GLiNER
from dotenv import load_dotenv
from ontology import ENTITIES
from config import GLINER_MODEL, GLINER_THRESHOLD

load_dotenv()

labels = list(ENTITIES.keys())
device = 'cuda' if torch.cuda.is_available() else 'cpu'

print(f"Loading GLiNER model: {GLINER_MODEL} on {device}", flush=True)
model = GLiNER.from_pretrained(GLINER_MODEL).to(device)
print(f"Model loaded. Threshold: {GLINER_THRESHOLD}", flush=True)


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def extractFromChunk(chunk):
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
