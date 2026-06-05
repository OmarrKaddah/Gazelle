import json
import hashlib
from pathlib import Path


LIMIT = 200  # set to None for the full dev set
DEV = Path(__file__).resolve().parent / 'data' / 'dev.json'
OUT = Path(__file__).resolve().parent.parent / 'chunks' / '2wiki.json'


def loadExamples():
    rows = json.loads(DEV.read_text(encoding='utf-8'))
    return rows if LIMIT is None else rows[:LIMIT]


def paragraphText(sentences):
    # 2Wiki context paragraphs are a title + list of sentence strings; the sentences
    # already carry their own spacing, so a bare join reproduces the source passage.
    return ''.join(sentences).strip()


def chunkId(text):
    return '2wiki-' + hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


def buildChunks(examples):
    seen = {}
    for ex in examples:
        for title, sentences in ex.get('context', []):
            text = paragraphText(sentences)
            if not text:
                continue
            cid = chunkId(text)
            if cid not in seen:
                seen[cid] = {
                    'chunkId': cid,
                    'docName': '2wiki',
                    'sectionPath': [title],
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
    print(f'{scope}: {len(examples)} examples -> {len(chunks)} unique chunks -> {OUT}')


if __name__ == '__main__':
    main()
