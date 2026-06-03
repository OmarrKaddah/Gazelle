import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from pathlib import Path
from dotenv import load_dotenv
from ontology import ENTITIES, RELATIONSHIPS


load_dotenv()

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
OLLAMA_TEXT_MODEL = os.getenv('OLLAMA_TEXT_MODEL', 'qwen2.5:72b-instruct-q4_K_M')
OLLAMA_EXTRACT_MODEL = os.getenv('OLLAMA_EXTRACT_MODEL', OLLAMA_TEXT_MODEL)
PARALLEL_CHUNKS = int(os.getenv('OLLAMA_NUM_PARALLEL', '4'))


def slugify(text):
    return re.sub(r'\s+', '-', text.strip()).lower()


def normalizeArabic(text):
    text = re.sub(r'[ً-ٟ]', '', text)             # strip tashkeel
    text = re.sub(r'[أإآ]', 'ا', text)  # أ إ آ → ا
    text = re.sub(r'ى', 'ي', text)                 # ى → ي
    return re.sub(r'\s+', ' ', text).strip()


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def loadGlinerRaw(docName):
    return json.loads(Path(f'extractions/{docName}_entities.json').read_text(encoding='utf-8'))


def canonicalizeEntities(rawEntities):
    grouped = {}
    for e in rawEntities:
        if e['type'] not in ENTITIES:
            continue
        text = e['text'].strip()
        key = (normalizeArabic(text), e['type'])
        if key not in grouped:
            grouped[key] = {
                'canonicalId': slugify(key[0]) + '-' + e['type'].lower(),
                'canonicalName': text,
                'type': e['type'],
                'aliases': [],
                'chunkIds': set(),
            }
        else:
            existing = grouped[key]
            if text != existing['canonicalName'] and text not in existing['aliases']:
                existing['aliases'].append(text)
        grouped[key]['chunkIds'].add(e['chunkId'])
    out = []
    for v in grouped.values():
        v['chunkIds'] = sorted(v['chunkIds'])
        out.append(v)
    return out


def buildRelationshipSpec():
    lines = [
        f"- {name}: {'|'.join(subjects)} -> {'|'.join(objects)}"
        for name, (subjects, objects) in RELATIONSHIPS.items()
    ]
    return "RELATIONSHIP TYPES (subject -> object — direction matters!):\n" + "\n".join(lines)


def formatEntitiesForPrompt(entities):
    return "\n".join(
        f"- {e['canonicalId']} ({e['type']}) = {e['canonicalName']}"
        for e in entities
    )


PROMPT_TEMPLATE = """You extract ONLY relationships between entities from Arabic banking and financial regulatory text.

{relSpec}

DIRECTION RULES:
- License/Document ISSUED_BY RegulatoryBody/Person (NOT the other way)
- Document EFFECTIVE_FROM Date (NOT Date -> Document)
- Article PART_OF Law (NOT Law -> Article)
- Law/Article GOVERNS BankingInstitution (NOT RegulatoryBody)

ENTITIES IN THIS TEXT (use ONLY these canonicalIds as subjects/objects):
{entities}

RULES:
- Only emit a relationship if the TEXT explicitly states or strongly implies it.
- Use only the canonicalIds listed above. Do not invent entities.
- Skip relationships whose subject/object types don't match the schema.

OUTPUT — strictly this JSON shape, nothing else:
{{
  "relationships": [{{"subject": "canonicalId", "predicate": "string", "object": "canonicalId"}}]
}}

TEXT:
{text}
"""


def buildPrompt(chunkText, entities):
    return PROMPT_TEMPLATE.format(
        relSpec=buildRelationshipSpec(),
        entities=formatEntitiesForPrompt(entities) if entities else "(none)",
        text=chunkText,
    )


def callOllama(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_EXTRACT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def extractRelationships(chunkText, entities):
    if not entities:
        return []
    prompt = buildPrompt(chunkText, entities)
    raw = callOllama(prompt)
    parsed = json.loads(raw)
    return parsed.get('relationships', [])


def stripChunkIds(entity):
    return {k: v for k, v in entity.items() if k != 'chunkIds'}


def extractDoc(docName):
    chunks = loadChunks(docName)
    rawGliner = loadGlinerRaw(docName)
    canonical = canonicalizeEntities(rawGliner)

    entitiesByChunk = {}
    for ent in canonical:
        for cid in ent['chunkIds']:
            entitiesByChunk.setdefault(cid, []).append(ent)

    results: list = [None] * len(chunks)

    def processChunk(i, chunk):
        chunkEnts = entitiesByChunk.get(chunk['chunkId'], [])
        rels = extractRelationships(chunk['text'], chunkEnts)
        return i, {
            'chunkId': chunk['chunkId'],
            'entities': [stripChunkIds(e) for e in chunkEnts],
            'relationships': rels,
        }

    with ThreadPoolExecutor(max_workers=PARALLEL_CHUNKS) as pool:
        futures = {pool.submit(processChunk, i, c): i for i, c in enumerate(chunks)}
        done = 0
        for fut in as_completed(futures):
            i, result = fut.result()
            results[i] = result
            done += 1
            print(
                f"[{done}/{len(chunks)}] {chunks[i]['chunkId']}: "
                f"{len(result['entities'])} ents, {len(result['relationships'])} rels",
                flush=True,
            )
    return results


def dumpExtractions(results, docName):
    Path('extractions').mkdir(exist_ok=True)
    Path(f'extractions/{docName}.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
