import json
import time
import requests
from config import (
    OLLAMA_URL,
    GROQ_URL, GROQ_API_KEY,
    OPENROUTER_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL,
    GEMINI_URL, GEMINI_API_KEY, GEMINI_MODEL,
)


BACKENDS = {
    'ollama': {
        'url': OLLAMA_URL,
        'model': 'llama3.1:8b',
        'headers': {},
        'extra': {'keep_alive': '60m'},
    },
    'groq': {
        'url': GROQ_URL,
        'model': 'llama-3.1-8b-instant',
        'headers': {'Authorization': f'Bearer {GROQ_API_KEY}'},
        'extra': {},
    },
    'openrouter': {
        'url': OPENROUTER_URL,
        'model': OPENROUTER_MODEL,
        'headers': {'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
        'extra': {},
    },
    'gemini': {
        'url': GEMINI_URL,
        'model': GEMINI_MODEL,
        'headers': {'Authorization': f'Bearer {GEMINI_API_KEY}'},
        'extra': {},
    },
}

BATCH_TEMPLATE = '''Extract relationship triples from each of the {n} passages below.
Output a JSON object: {{"passages": [[triples for passage 1], [triples for passage 2], ...]}} with EXACTLY {n} inner lists in order. Each triple is [subject, predicate, object]. Each triple should contain at least one — preferably two — of that passage's named entities. Resolve pronouns to specific names. No prose, JSON only.

{passages}
'''


def buildBatchPrompt(passages):
    parts = []
    for i, (text, names) in enumerate(passages, 1):
        parts.append(f'=== Passage {i} ===')
        parts.append(f'Text: """{text}"""')
        parts.append(f'Named entities: {json.dumps(names, ensure_ascii=False)}')
        parts.append('')
    return BATCH_TEMPLATE.format(n=len(passages), passages='\n'.join(parts))


def callLLM(prompt, backend='ollama'):
    cfg = BACKENDS[backend]
    payload = {
        'model': cfg['model'],
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        **cfg['extra'],
    }
    for attempt in range(3):
        resp = requests.post(cfg['url'], json=payload, headers=cfg['headers'], timeout=600)
        if resp.status_code == 429 and attempt < 2:
            wait = float(resp.headers.get('Retry-After', 5))
            time.sleep(wait + 1)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f'{resp.status_code}: {resp.text[:400]}')
        return resp.json()['choices'][0]['message']['content']


def parseBatchTriples(raw, expectedCount):
    parsed = json.loads(raw)
    passages = parsed.get('passages', [])
    out = []
    for i in range(expectedCount):
        if i < len(passages) and isinstance(passages[i], list):
            out.append([tuple(t) for t in passages[i] if isinstance(t, list) and len(t) == 3])
        else:
            out.append([])
    return out


def extractTriplesBatch(passages, backend='ollama'):
    raw = callLLM(buildBatchPrompt(passages), backend=backend)
    return parseBatchTriples(raw, len(passages))


def extractTriples(chunkText, entityNames, backend='ollama'):
    return extractTriplesBatch([(chunkText, entityNames)], backend=backend)[0]
