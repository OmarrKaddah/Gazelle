import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import GRAPH_EXTRACT_BACKEND, GRAPH_EXTRACT_WORKERS, EXTRACT_DIR
from kgBuild import loadChunks
from llmTriples import callLLM
from ontology import ontologyFor


def buildEntityGuide(entities):
    return "\n".join(f"- {name}: {desc}" for name, desc in entities.items())


EXTRACT_PROMPT = '''You are building a knowledge graph from a document passage (a financial/regulatory text, often Arabic; or a general-knowledge English passage).

Allowed entity types:
{entityTypes}

From the PASSAGE extract:
1. "entities": each as {{"name": <exact surface form from the passage>, "type": <one allowed type>, "description": <one concise sentence describing the entity, grounded ONLY in the passage>}}
2. "relationships": for each pair of extracted entities that are clearly related, {{"source": <entity name>, "target": <entity name>, "predicate": <1-3 word relation label, e.g. "issued", "regulates", "amends">, "description": <how they relate, one concise sentence>}}

Rules:
- Use the entity's surface form from the passage as "name"; keep Arabic text in Arabic.
- Only extract entities whose type is in the allowed list. Only relationships where BOTH endpoints are extracted entities.
- Ground everything strictly in the passage. Do not invent facts.
- Output a single JSON object {{"entities": [...], "relationships": [...]}}. JSON only, no prose.

PASSAGE:
"""{text}"""
'''


def extractElements(chunkText, entityGuide, backend=GRAPH_EXTRACT_BACKEND):
    prompt = EXTRACT_PROMPT.format(entityTypes=entityGuide, text=chunkText)
    return callLLM(prompt, backend=backend)


def salvageJson(raw):

    raw = raw.strip()
    start, end = raw.find('{'), raw.rfind('}')
    return raw[start:end + 1] if start != -1 and end > start else raw


def parseElements(raw):
    data = json.loads(salvageJson(raw))
    entities = [
        (e['name'], e.get('type', ''), e.get('description', ''))
        for e in data.get('entities', [])
        if e.get('name')
    ]

    relationships = [
        (r['source'], r['target'], r.get('predicate', ''), r.get('description', ''), r.get('strength', 1))
        for r in data.get('relationships', [])
        if r.get('source') and r.get('target')
    ]

    return {'entities': entities, 'relationships': relationships}


def extractChunk(chunk, entityGuide, backend):

    for attempt in range(3):
        raw = extractElements(chunk['text'], entityGuide, backend)
        try:
            elements = parseElements(raw)
            return {'chunkId': chunk['chunkId'], **elements}
        except json.JSONDecodeError:
            if attempt == 2:
                print(f'  [warn] {chunk["chunkId"]}: unparseable JSON after 3 tries, storing empty', flush=True)
                return {'chunkId': chunk['chunkId'], 'entities': [], 'relationships': []}


def loadPartial(docName):
    p = Path(f'{EXTRACT_DIR}/{docName}_graph.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []


def extractDoc(docName, backend=GRAPH_EXTRACT_BACKEND):
    chunks = loadChunks(docName)
    entityGuide = buildEntityGuide(ontologyFor(docName))
    total = len(chunks)
    results = loadPartial(docName)
    done = {r['chunkId'] for r in results}
    todo = [c for c in chunks if c['chunkId'] not in done]
    print(f'  {len(done)} already done, {len(todo)} to extract', flush=True)
    with ThreadPoolExecutor(max_workers=GRAPH_EXTRACT_WORKERS) as pool:
        futures = [pool.submit(extractChunk, c, entityGuide, backend) for c in todo]
        for fut in as_completed(futures):
            results.append(fut.result())
            if len(results) % 20 == 0:
                dumpElements(results, docName)
            r = results[-1]
            print(f'  {len(results)}/{total}  {len(r["entities"])} ents, {len(r["relationships"])} rels', flush=True)
    dumpElements(results, docName)
    return results


def dumpElements(results, docName):

    # atomic write so a Ctrl-C mid-flush can never corrupt the resume checkpoint

    Path(EXTRACT_DIR).mkdir(exist_ok=True)

    path = Path(f'{EXTRACT_DIR}/{docName}_graph.json')
    tmp = path.with_suffix('.json.tmp')
    
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


