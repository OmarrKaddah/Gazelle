import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path


def loadChunks(docName):
    path = Path(f'chunks/{docName}.json')
    raw = json.loads(path.read_text(encoding='utf-8'))
    return {c['chunkId']: c for c in raw}


def loadEntities(docName):
    path = Path(f'extractions/{docName}_entities.json')
    return json.loads(path.read_text(encoding='utf-8'))


def buildAnnotation(chunkMeta, entities):
    text    = chunkMeta['text']
    chunkId = chunkMeta['chunkId']
    docName = chunkMeta['docName']

    result = [
        {
            'id':        str(uuid.uuid4())[:8],
            'from_name': 'label',
            'to_name':   'text',
            'type':      'labels',
            'value': {
                'start':  e['start'],
                'end':    e['end'],
                'text':   text[e['start']:e['end']],
                'labels': [e['type']],
            },
        }
        for e in entities
    ]
    return {
        'data':        {'text': text},
        'meta':        {'chunkId': chunkId, 'docName': docName},
        'annotations': [{'result': result}],
    }


def discoverDocNames():
    entityFiles = sorted(Path('extractions').glob('*_entities.json'))
    docNames = []
    for f in entityFiles:
        if f.is_file():
            docName = f.stem.replace('_entities', '')
            chunkFile = Path(f'chunks/{docName}.json')
            if chunkFile.exists():
                docNames.append(docName)
            else:
                print(f"skipping {f.name} — no matching chunks/{docName}.json")
    return docNames


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        docNames = sys.argv[1:]
    else:
        print("no args — scanning extractions/")
        docNames = discoverDocNames()
        if not docNames:
            print("no matching extraction+chunk pairs found")
            sys.exit(1)
        print(f"found: {docNames}")

    allAnnotations = []

    for docName in docNames:
        print(f"processing {docName}")
        chunkMap = loadChunks(docName)
        entities = loadEntities(docName)

        byChunk = defaultdict(list)
        for e in entities:
            byChunk[e['chunkId']].append(e)

        for chunkId, chunkMeta in chunkMap.items():
            ann = buildAnnotation(chunkMeta, byChunk[chunkId])
            allAnnotations.append(ann)

        total_spans = sum(len(byChunk[c]) for c in chunkMap)
        print(f"  {len(chunkMap)} chunks, {total_spans} entity spans")

    Path('annotations').mkdir(exist_ok=True)
    outPath = Path('annotations/corrected.json')
    existing = json.loads(outPath.read_text(encoding='utf-8')) if outPath.exists() else []
    existingIds = {(t['meta']['chunkId']) for t in existing if t.get('meta', {}).get('chunkId')}
    newTasks = [t for t in allAnnotations if t.get('meta', {}).get('chunkId') not in existingIds]
    merged = existing + newTasks
    outPath.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"merged: {len(existing)} existing + {len(newTasks)} new = {len(merged)} total tasks")
