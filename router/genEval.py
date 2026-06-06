import _bootstrap  # noqa: F401
import os
import re
import json
import random
import requests
from concurrent.futures import ThreadPoolExecutor
from config import OPENROUTER_URL, OPENROUTER_API_KEY
from routerFeatures import normalizeText

# Generates a FRESH held-out router eval set with DeepSeek V3 over real corpus
# excerpts: {local,global} x {en,ar}, natural varied phrasing (NOT templates), so
# it can honestly test the global + Arabic cells that no on-disk data covers and
# that the synthetic training set leaked. Labels = generation intent; a second LLM
# (the llama-3.3-70b router judge) cross-checks every question for an honest
# agreement number. The CBE corpus is ~all Arabic (26/27 docs), so the set is
# Arabic-dominant by design; English is the smaller cross-lingual comparison arm.
# Output: router/data/holdout_llm.jsonl.

GEN_MODEL = 'deepseek/deepseek-chat'
OUT = 'router/data/holdout_llm.jsonl'
PER_EXCERPT = 6          # questions per intent per excerpt
AR_EXCERPTS = 24         # Arabic regulatory excerpts (deployment reality → dominant)
EN_NEWS_EXCERPTS = 8     # English news excerpts (apnews)
EN_REG_EXCERPTS = 6      # English regulatory excerpts (the one EN CBE doc)
MIN_CHARS, MAX_CHARS = 220, 1400
SEED = 17

arRe = re.compile(r'[؀-ۿ]')


def arRatio(s):
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(bool(arRe.match(c)) for c in letters) / len(letters)

INTENT_DEF = {
    'local': ('a SPECIFIC question answerable from one fact, entity, number, date, '
              'figure, definition, or single passage'),
    'global': ('a CORPUS-WIDE sensemaking question about themes, trends, patterns, '
               'comparisons, or an overall summary across many documents'),
}

GEN_PROMPT = '''You write evaluation questions for a retrieval system over {domain} documents.

Below is a real excerpt from the corpus (for grounding the topic only — do NOT quote it):
"""{excerpt}"""

Write {n} DISTINCT {intent_name} questions in {lang_name}.
A {intent_name} question is {intent_def}.

Hard requirements:
- Sound like {n} DIFFERENT real users — vary sentence structure, opening words, length, and register. No shared template.
- {lang_name} only. Natural, fluent {lang_name}.
- Do NOT reuse the same opening phrase twice. Do NOT add labels, numbering, or commentary.
- Stay on the document domain ({domain}) but you may range beyond this single excerpt.

Return JSON only: {{"questions": ["...", "..."]}} with exactly {n} strings.'''

LANG_NAME = {'en': 'English', 'ar': 'Arabic'}


def callGen(prompt, temperature):
    payload = {
        'model': GEN_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temperature,
        'response_format': {'type': 'json_object'},
        'provider': {'sort': 'throughput'},
    }
    headers = {'Authorization': f'Bearer {OPENROUTER_API_KEY}'}
    resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f'{resp.status_code}: {resp.text[:300]}')
    return resp.json()['choices'][0]['message']['content']


def chunkTexts(files):
    texts = []
    for f in files:
        for c in json.load(open(f'chunks/{f}', encoding='utf-8')):
            t = c.get('text', '').strip()
            if MIN_CHARS <= len(t) <= MAX_CHARS and not t.startswith('|'):
                texts.append(t)
    return texts


def corpusExcerpts():
    # split chunk docs by actual script (filenames are unreliable), sample per cell
    arFiles, enFiles = [], []
    for f in sorted(os.listdir('chunks')):
        d = json.load(open(f'chunks/{f}', encoding='utf-8'))
        sample = ' '.join(c.get('text', '') for c in d)[:5000]
        (arFiles if arRatio(sample) > 0.5 else enFiles).append(f)

    arPool = chunkTexts(arFiles)
    enRegPool = chunkTexts(enFiles)
    enNewsPool = [r['text'].strip() for r in json.load(open('apnews.json', encoding='utf-8'))
                  if MIN_CHARS <= len(r['text'].strip()) <= MAX_CHARS]
    for pool in (arPool, enRegPool, enNewsPool):
        random.shuffle(pool)
    return arPool[:AR_EXCERPTS], enNewsPool[:EN_NEWS_EXCERPTS], enRegPool[:EN_REG_EXCERPTS]


def generateCell(excerpts, lang, intent, domain):
    out = []
    for excerpt in excerpts:
        prompt = GEN_PROMPT.format(
            domain=domain, excerpt=excerpt, n=PER_EXCERPT,
            intent_name=intent, intent_def=INTENT_DEF[intent],
            lang_name=LANG_NAME[lang])
        raw = callGen(prompt, temperature=0.95)
        qs = json.loads(raw).get('questions', [])
        for q in qs:
            q = q.strip()
            if q:
                out.append({'text': q, 'label': intent, 'lang': lang, 'domain': domain})
    return out


def dedup(rows):
    seen, kept = set(), []
    for r in rows:
        key = (r['lang'], normalizeText(r['text']))
        if key not in seen:
            seen.add(key)
            kept.append(r)
    return kept


def judge(rows):
    from router import routeQuery  # imported here: needs OPENROUTER plumbing, same dir

    def one(r):
        try:
            return routeQuery(r['text'], backend='openrouter')
        except Exception as e:
            return f'error:{type(e).__name__}'

    with ThreadPoolExecutor(max_workers=8) as pool:
        verdicts = list(pool.map(one, rows))
    for r, v in zip(rows, verdicts):
        r['judge'] = v
        r['agree'] = (v == r['label'])
    return rows


def main():
    random.seed(SEED)
    arEx, enNewsEx, enRegEx = corpusExcerpts()
    cells = [
        ('ar', 'central-bank regulatory', arEx),
        ('en', 'news finance/regulatory', enNewsEx),
        ('en', 'central-bank regulatory', enRegEx),
    ]

    rows = []
    for lang, domain, excerpts in cells:
        for intent in ('local', 'global'):
            cell = generateCell(excerpts, lang, intent, domain)
            print(f'  {lang}/{domain}/{intent}: {len(cell)} questions', flush=True)
            rows.extend(cell)

    rows = dedup(rows)
    print(f'after dedup: {len(rows)}', flush=True)
    rows = judge(rows)
    agree = sum(r['agree'] for r in rows)
    print(f'generator-vs-llama agreement: {agree}/{len(rows)} = {agree / len(rows):.3f}', flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'wrote {OUT}', flush=True)


if __name__ == '__main__':
    main()
