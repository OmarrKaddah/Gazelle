import json
import sys
import uuid
from pathlib import Path

THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5


def loadChunks():
    chunks = {}
    for path in sorted(Path('chunks').glob('*.json')):
        for chunk in json.loads(path.read_text(encoding='utf-8')):
            chunks[chunk['chunkId']] = chunk
    return chunks


def loadEntities():
    byChunk = {}
    for path in sorted(Path('extractions').glob('*_entities.json')):
        for e in json.loads(path.read_text(encoding='utf-8')):
            if e.get('score', 0) < THRESHOLD:
                continue
            byChunk.setdefault(e['chunkId'], []).append(e)
    return byChunk


def buildResult(entity):
    return {
        'id': str(uuid.uuid4())[:8],
        'from_name': 'label',
        'to_name': 'text',
        'type': 'labels',
        'value': {
            'start': entity['start'],
            'end': entity['end'],
            'text': entity['text'],
            'labels': [entity['type']],
        },
    }


def buildTask(chunk, entities):
    return {
        'data': {
            'text': chunk['text'],
        },
        'meta': {
            'chunkId': chunk['chunkId'],
            'docName': chunk['docName'],
        },
        'predictions': [
            {
                'model_version': 'gliner',
                'result': [buildResult(e) for e in entities],
            }
        ],
    }


def dumpTasks(tasks):
    Path('annotations').mkdir(exist_ok=True)
    out = Path('annotations/ls_import.json')
    out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote {len(tasks)} tasks -> {out}")


if __name__ == '__main__':
    chunks = loadChunks()
    byChunk = loadEntities()

    tasks = []
    for chunkId, entities in sorted(byChunk.items()):
        if chunkId not in chunks:
            continue
        tasks.append(buildTask(chunks[chunkId], entities))

    dumpTasks(tasks)
    total_spans = sum(len(t['predictions'][0]['result']) for t in tasks)
    print(f"Total pre-labeled spans: {total_spans}")
    print(f"Avg spans per chunk: {total_spans / len(tasks):.1f}" if tasks else "No tasks.")
