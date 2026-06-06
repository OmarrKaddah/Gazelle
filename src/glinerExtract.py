import json
import sys
from pathlib import Path
from tqdm import tqdm
from gliner import GLiNER
from dotenv import load_dotenv
from ontology import ENTITIES
from config import GLINER_MODEL, GLINER_MODEL_EN, GLINER_THRESHOLD, EXTRACT_DIR

_models = {}




def getModel(lang):
    name = GLINER_MODEL_EN if lang == 'en' else GLINER_MODEL
    if name not in _models:
        print(f"Loading GLiNER model: {name}", flush=True)
        _models[name] = GLiNER.from_pretrained(name)
    return _models[name]




def getLabels(lang):
    return list(ENTITIES.keys())



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
    Path(EXTRACT_DIR).mkdir(exist_ok=True)
    Path(f'{EXTRACT_DIR}/{docName}_entities.json').write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
