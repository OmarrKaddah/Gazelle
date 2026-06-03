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


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python extractionsToCorrections.py <docName> [docName2 ...]")
        print("  reads:  extractions/{docName}_entities.json + chunks/{docName}.json")
        print("  writes: annotations/corrected.json")
        sys.exit(1)

    docNames = sys.argv[1:]
    allAnnotations = []

    for docName in docNames:
        print(f"[extractionsToCorrections] processing {docName}")
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
    Path('annotations/corrected.json').write_text(
        json.dumps(allAnnotations, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"[extractionsToCorrections] wrote annotations/corrected.json ({len(allAnnotations)} tasks)")
