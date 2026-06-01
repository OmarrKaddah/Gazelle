import json
import pickle
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from featureExtract import tokenize, posTag, tokenFeatures, loadGazetteer


def loadModel():
    return pickle.loads(Path('models/crf.pkl').read_bytes())


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def bioToSpans(tokens, labels, chunkId, docName):
    spans = []
    current = None
    for tok, label in zip(tokens, labels):
        if label.startswith('B-'):
            if current:
                spans.append(current)
            current = {
                'chunkId': chunkId,
                'docName': docName,
                'text':    tok['word'],
                'type':    label[2:],
                'start':   tok['start'],
                'end':     tok['end'],
                'score':   1.0,
                'source':  'crf',
            }
        elif label.startswith('I-') and current:
            current['text'] += ' ' + tok['word']
            current['end']   = tok['end']
        else:
            if current:
                spans.append(current)
            current = None
    if current:
        spans.append(current)
    return spans


def predictChunk(crf, chunk, gazSets, orgTriggers, moneyTriggers, monthNames):
    tokens = tokenize(chunk['text'])
    words  = [t['word'] for t in tokens]
    pos    = posTag(words)
    feats  = [
        tokenFeatures(tokens, pos, i, gazSets, orgTriggers, moneyTriggers, monthNames)
        for i in range(len(tokens))
    ]
    labels = crf.predict([feats])[0]
    return bioToSpans(tokens, labels, chunk['chunkId'], chunk['docName'])


def dumpEntities(entities, docName):
    Path('extractions/crf').mkdir(parents=True, exist_ok=True)
    Path(f'extractions/crf/{docName}_crf_entities.json').write_text(
        json.dumps(entities, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def runDoc(crf, docName, gazSets, orgTriggers, moneyTriggers, monthNames):
    chunks   = loadChunks(docName)
    entities = []
    for chunk in chunks:
        entities.extend(predictChunk(crf, chunk, gazSets, orgTriggers, moneyTriggers, monthNames))
    dumpEntities(entities, docName)
    print(f"{docName}: {len(entities)} entities")
    return entities


if __name__ == '__main__':
    crf = loadModel()
    gazSets, orgTriggers, moneyTriggers, monthNames = loadGazetteer()
    docNames = [p.stem for p in Path('chunks').glob('*.json')]
    for docName in sorted(docNames):
        runDoc(crf, docName, gazSets, orgTriggers, moneyTriggers, monthNames)
