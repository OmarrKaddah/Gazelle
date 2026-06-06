import _bootstrap  # noqa: F401
import json
import re
import html
from pathlib import Path
from chunker import countTokens
from config import CHUNK_TARGET_TOKENS

# AP News (BenchmarkQED) -> chunks/apnews.json, the same chunk schema the rest of
# the pipeline consumes (musique/loadChunks.py is the sibling for MuSiQue). Each
# article is AP NITF JSON: text in body_nitf (<p> blocks), title in headline,
# stable id in altids.itemid. Articles are long, so we pack their paragraphs to
# CHUNK_TARGET_TOKENS instead of one-chunk-per-doc.
#
# Get the corpus first (in the benchmark-qed venv):
#   benchmark-qed data download AP_news sensemaking/data/ap_news
# which unzips the per-article JSONs under <dir>/raw_data/.

LIMIT = 200  # number of articles; set to None for the full 1,397
RAW = Path(__file__).resolve().parent / 'data' / 'ap_news'
OUT = Path(__file__).resolve().parent.parent / 'chunks' / 'apnews.json'


def articleFiles():
    return sorted(RAW.rglob('*.json'))


def paragraphs(nitf):
    blocks = re.findall(r'<p>(.*?)</p>', nitf or '', flags=re.S)
    out = []
    for b in blocks:
        text = html.unescape(re.sub(r'<[^>]+>', '', b))
        text = text.replace('�', '—')     # AP em-dash lands as the replacement char
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            out.append(text)
    return out


def packParagraphs(paras, target):
    chunks, current, tokens = [], [], 0
    for p in paras:
        pTokens = countTokens(p)
        if current and tokens + pTokens > target:
            chunks.append(' '.join(current))
            current, tokens = [], 0
        current.append(p)
        tokens += pTokens
    if current:
        chunks.append(' '.join(current))
    return chunks


def buildChunks(files):
    rows = []
    for f in files:
        art = json.loads(f.read_text(encoding='utf-8-sig'))
        itemid = art['altids']['itemid']
        headline = art.get('headline') or art.get('title') or ''
        paras = packParagraphs(paragraphs(art.get('body_nitf', '')), CHUNK_TARGET_TOKENS)
        for i, body in enumerate(paras):
            rows.append({
                'chunkId': f'apnews-{itemid}-{i}',
                'docName': 'apnews',
                'sectionPath': [headline],
                'pages': [],
                'text': f'{headline}: {body}' if i == 0 else body,
                'elementIds': [],
                'accessLevel': 'public',
            })
    return rows


def main():
    files = articleFiles()
    files = files if LIMIT is None else files[:LIMIT]
    chunks = buildChunks(files)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding='utf-8')
    scope = 'all' if LIMIT is None else f'first {LIMIT}'
    print(f'{scope}: {len(files)} articles -> {len(chunks)} chunks -> {OUT}')


if __name__ == '__main__':
    main()
