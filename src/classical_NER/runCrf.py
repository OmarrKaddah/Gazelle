import json
import pickle
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from featureExtract import tokenize, posTag, tokenFeatures, loadGazetteer, isArabic
from config import EXTRACT_DIR


def loadModel(name='crf'):
    path = Path(__file__).resolve().parent / 'models' / f'{name}.pkl'

    crf = pickle.loads(path.read_bytes())

    return crf


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def bioToSpans(tokens, labels, chunkId, docName):
    spans = []
    current = None

    for tok, label in zip(tokens, labels):
        if label == 'B':
            if current:
                current['type'] = current['text']
                spans.append(current)
            current = {
                'chunkId': chunkId,
                'docName': docName,
                'text':    tok['word'],
                'start':   tok['start'],
                'end':     tok['end'],
                'score':   1.0,
            }
        elif label == 'I' and current:
            current['text'] += ' ' + tok['word']
            current['end']   = tok['end']
        else:
            if current:
                current['type'] = current['text']
                spans.append(current)
            current = None

    if current:
        current['type'] = current['text']
        spans.append(current)
    return spans


def predictChunk(crf, chunk, orgTriggers, moneyTriggers, monthNames):
    if not isArabic(chunk['text']):
        return []
    
    tokens = tokenize(chunk['text'])
    words  = [t['word'] for t in tokens]
    pos    = posTag(words)
    
    feats  = [
        tokenFeatures(tokens, pos, i, orgTriggers, moneyTriggers, monthNames)
        for i in range(len(tokens))
    ]
    
    labels = crf.predict([feats])[0]
    spans  = bioToSpans(tokens, labels, chunk['chunkId'], chunk['docName'])
    spans  = [s for s in spans if s['text'] not in moneyTriggers and s['text'] not in monthNames]
    non_o  = sum(1 for l in labels if l != 'O')
    if non_o:
        print(f"    chunk {chunk['chunkId']}: {len(tokens)} tokens, {non_o} entity tokens, {len(spans)} spans")
    return spans


def dumpEntities(entities, docName, modelName):
    Path(EXTRACT_DIR).mkdir(exist_ok=True)
    out = Path(f'{EXTRACT_DIR}/{docName}_entities.json')
    out.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"done")


def runDoc(crf, docName, orgTriggers, moneyTriggers, monthNames, modelName):
    
    chunks   = loadChunks(docName)
    print(f"{docName} — {len(chunks)} chunks")
    entities = []
    
    for chunk in chunks:
        entities.extend(predictChunk(crf, chunk, orgTriggers, moneyTriggers, monthNames))
    dumpEntities(entities, docName, modelName)
    print(f"  total: {len(entities)} entities")
    return entities


if __name__ == '__main__':
    
    nameArgs  = [a for a in sys.argv if a.startswith('--model=')]
    modelName = nameArgs[0].split('=', 1)[1] if nameArgs else 'crf'

    crf = loadModel(modelName)

    _, orgTriggers, moneyTriggers, monthNames = loadGazetteer()

    docsArgs = [a for a in sys.argv if a.startswith('--docs=')]
    if docsArgs:
        docs = [d.strip() for d in docsArgs[0].split('=', 1)[1].split(',')]
    else:
        # skip wikiann/anercorp — those are eval sets, not bank docs
        docs = sorted(p.stem for p in Path('chunks').glob('*.json')
                      if not p.stem.startswith('wikiann') and not p.stem.startswith('anercorp'))

    print(f" {len(docs)} documents: {docs}")

    all_entities = []
    for docName in docs:
        entities = runDoc(crf, docName, orgTriggers, moneyTriggers, monthNames, modelName)
        all_entities.extend(entities)

    print(f"done — {len(all_entities)} total entities across {len(docs)} documents")
