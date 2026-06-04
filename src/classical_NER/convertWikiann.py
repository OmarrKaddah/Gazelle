import json
import sys
import uuid
from pathlib import Path
from datasets import load_dataset

SENTENCES_PER_CHUNK = 10

LABEL_NAMES = ['O', 'B-PER', 'I-PER', 'B-ORG', 'I-ORG', 'B-LOC', 'I-LOC']

LABEL_MAP = {
    'PER': 'Person',
    'ORG': 'RegulatoryBody',
    'LOC': 'RegulatoryBody',
}


def loadSplit(split):
    print(f"[convertWikiann] loading wikiann ar — split: {split}")
    ds = load_dataset('wikiann', 'ar', split=split)
    sentences = []
    for ex in ds:
        pairs = [(tok, LABEL_NAMES[tag]) for tok, tag in zip(ex['tokens'], ex['ner_tags'])]
        sentences.append(pairs)
    print(f"[convertWikiann] {len(sentences)} sentences")
    return sentences


def buildChunkText(sentences):
    return ' '.join(word for sent in sentences for word, _ in sent)


def buildSpans(sentences):
    spans = []
    offset = 0
    for sent in sentences:
        current = None
        for word, label in sent:
            wlen = len(word)
            tag  = label[2:] if label.startswith(('B-', 'I-')) else None
            bio  = label[:2]  if label.startswith(('B-', 'I-')) else None
            etype = LABEL_MAP.get(tag) if tag else None

            if bio == 'B-' and etype:
                if current:
                    spans.append(current)
                current = {'start': offset, 'end': offset + wlen, 'type': etype}
            elif bio == 'I-' and current:
                current['end'] = offset + wlen
            else:
                if current:
                    spans.append(current)
                current = None

            offset += wlen + 1

        if current:
            spans.append(current)
            current = None

    return spans


def buildAnnotation(text, spans, chunkId, docName):
    result = [
        {
            'id': str(uuid.uuid4())[:8],
            'from_name': 'label',
            'to_name': 'text',
            'type': 'labels',
            'value': {
                'start':  s['start'],
                'end':    s['end'],
                'text':   text[s['start']:s['end']],
                'labels': [s['type']],
            },
        }
        for s in spans
    ]
    return {
        'data': {'text': text},
        'meta': {'chunkId': chunkId, 'docName': docName},
        'annotations': [{'result': result}],
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python convertWikiann.py <split> [docName]")
        print("  split: train | validation | test")
        print("  example: python convertWikiann.py train wikiann_train")
        sys.exit(1)

    split   = sys.argv[1]
    docName = sys.argv[2] if len(sys.argv) >= 3 else f'wikiann_{split}'

    sentences = loadSplit(split)

    groups = [
        sentences[i:i + SENTENCES_PER_CHUNK]
        for i in range(0, len(sentences), SENTENCES_PER_CHUNK)
    ]
    print(f"[convertWikiann] {len(groups)} chunks ({SENTENCES_PER_CHUNK} sentences each)")

    chunks      = []
    annotations = []
    for i, group in enumerate(groups):
        chunkId = f'{docName}-c{i+1:04d}'
        text    = buildChunkText(group)
        spans   = buildSpans(group)
        chunks.append({'chunkId': chunkId, 'docName': docName, 'text': text})
        annotations.append(buildAnnotation(text, spans, chunkId, docName))

    Path('chunks').mkdir(exist_ok=True)
    Path(f'chunks/{docName}.json').write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"[convertWikiann] wrote chunks/{docName}.json ({len(chunks)} chunks)")

    Path('annotations').mkdir(exist_ok=True)
    Path('annotations/wikiann_base.json').write_text(
        json.dumps(annotations, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    total_spans = sum(len(a['annotations'][0]['result']) for a in annotations)
    print(f"[convertWikiann] wrote annotations/wikiann_base.json ({total_spans} labeled spans)")

    gold = []
    for ann in annotations:
        chunkId = ann['meta']['chunkId']
        text    = ann['data']['text']
        for r in ann['annotations'][0]['result']:
            v = r['value']
            gold.append({
                'chunkId': chunkId,
                'docName': docName,
                'text':    text[v['start']:v['end']],
                'type':    v['labels'][0],
                'start':   v['start'],
                'end':     v['end'],
            })
    Path(f'annotations/gold_{docName}.json').write_text(
        json.dumps(gold, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"[convertWikiann] wrote annotations/gold_{docName}.json ({len(gold)} gold spans)")
    print(f"[convertWikiann] done")
