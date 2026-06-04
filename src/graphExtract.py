import json
from pathlib import Path

from config import GRAPH_EXTRACT_BACKEND
from kgBuild import loadChunks
from llmTriples import callLLM
from ontology import ENTITIES


ENTITY_TYPE_GUIDE = "\n".join(f"- {name}: {desc}" for name, desc in ENTITIES.items())

EXTRACT_PROMPT = '''You are building a knowledge graph from a financial/regulatory document passage (often Arabic).

Allowed entity types:
{entityTypes}

From the PASSAGE extract:
1. "entities": each as {{"name": <exact surface form from the passage>, "type": <one allowed type>, "description": <one concise sentence describing the entity, grounded ONLY in the passage>}}
2. "relationships": for each pair of extracted entities that are clearly related, {{"source": <entity name>, "target": <entity name>, "description": <how they relate, one concise sentence>, "strength": <integer 1-10>}}

Rules:
- Use the entity's surface form from the passage as "name"; keep Arabic text in Arabic.
- Only extract entities whose type is in the allowed list. Only relationships where BOTH endpoints are extracted entities.
- Ground everything strictly in the passage. Do not invent facts.
- Output a single JSON object {{"entities": [...], "relationships": [...]}}. JSON only, no prose.

PASSAGE:
"""{text}"""
'''


def extractElements(chunkText, backend=GRAPH_EXTRACT_BACKEND):
    prompt = EXTRACT_PROMPT.format(entityTypes=ENTITY_TYPE_GUIDE, text=chunkText)
    return callLLM(prompt, backend=backend)


def parseElements(raw):
    data = json.loads(raw)
    entities = [
        (e['name'], e.get('type', ''), e.get('description', ''))
        for e in data.get('entities', [])
        if e.get('name')
    ]
    relationships = [
        (r['source'], r['target'], r.get('description', ''), r.get('strength', 1))
        for r in data.get('relationships', [])
        if r.get('source') and r.get('target')
    ]
    return {'entities': entities, 'relationships': relationships}


def extractDoc(docName, backend=GRAPH_EXTRACT_BACKEND):
    results = []
    for chunk in loadChunks(docName):
        elements = parseElements(extractElements(chunk['text'], backend))
        results.append({'chunkId': chunk['chunkId'], **elements})
    return results


def dumpElements(results, docName):
    Path('extractions').mkdir(exist_ok=True)
    Path(f'extractions/{docName}_graph.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8'
    )
