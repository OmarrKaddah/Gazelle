import json
import hashlib
from pathlib import Path


LIMIT = 200  # set to None for the full dev set
DEV = Path(__file__).resolve().parent / 'data' / 'musique_ans_v1.0_dev.jsonl'
OUT = Path(__file__).resolve().parent.parent / 'chunks' / 'musique.json'


def loadExamples():
    rows = [json.loads(l) for l in DEV.read_text(encoding='utf-8').splitlines() if l.strip()]
    return rows if LIMIT is None else rows[:LIMIT]


def chunkId(text):
    return 'musique-' + hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


def buildChunks(examples):
    seen = {}
    for ex in examples:
        for p in ex.get('paragraphs', []):
            text = p.get('paragraph_text', '')
            if not text:
                continue
            cid = chunkId(text)
            if cid not in seen:
                seen[cid] = {
                    'chunkId': cid,
                    'docName': 'musique',
                    'sectionPath': [p.get('title', '')],
                    'pages': [],
                    'text': text,
                    'elementIds': [],
                    'accessLevel': 'public',
                }
    return list(seen.values())


def main():
    examples = loadExamples()
    chunks = buildChunks(examples)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding='utf-8')
    scope = 'full dev' if LIMIT is None else f'first {LIMIT}'
    print(f'{scope}: {len(examples)} examples → {len(chunks)} unique chunks → {OUT}')


if __name__ == '__main__':
    main()
