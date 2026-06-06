import json
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from ontology import ENTITIES


load_dotenv()
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
OLLAMA_TEXT_MODEL = os.getenv('OLLAMA_TEXT_MODEL', 'qwen2.5:72b-instruct-q4_K_M')


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def buildEntityExtractionPrompt(chunkText):
    entity_types = list(ENTITIES.keys())
    type_descriptions = '\n'.join(
        f'  - {t}: {ENTITIES[t]}' for t in entity_types
    )

    return f"""You are an expert at extracting entities from Arabic banking and financial regulatory documents.

Extract ALL entities from the text below. For each entity, identify:
1. The exact text span
2. The entity type (must be one of the types listed)

ENTITY TYPES:
{type_descriptions}

RULES:
- Extract every entity you can identify
- Use only the entity types listed above
- Be inclusive (extract more rather than less)
- Return as valid JSON
- If no entities found, return {{"entities": []}}

TEXT TO EXTRACT FROM:
{chunkText}

RESPONSE (JSON only):
{{"entities": [
  {{"text": "entity text", "type": "EntityType", "confidence": 0.95}},
  ...
]}}
"""


def callOllamaForEntities(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_TEXT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def extractEntitiesFromChunk(chunk):
    prompt = buildEntityExtractionPrompt(chunk['text'])
    raw = callOllamaForEntities(prompt)
    parsed = json.loads(raw)
    
    entities = []
    for ent in parsed.get('entities', []):
        if ent.get('type') not in ENTITIES:
            continue
        
        entities.append({
            'chunkId': chunk['chunkId'],
            'docName': chunk['docName'],
            'text': ent.get('text', '').strip(),
            'type': ent.get('type'),
            'score': ent.get('confidence', 0.8),
            'start': 0,  # LLM doesn't give position, set to 0
            'end': 0,
        })
    
    return entities


def extractEntities(docName):
    chunks = loadChunks(docName)
    entities = []
    
    for i, c in enumerate(chunks):
        chunk_ents = extractEntitiesFromChunk(c)
        entities.extend(chunk_ents)
        print(f"[{i+1}/{len(chunks)}] {c['chunkId']}: {len(chunk_ents)} entities", flush=True)
    
    return entities   






def dumpEntities(entities, docName):
    Path('extractions').mkdir(exist_ok=True)
    
    Path(f'extractions/{docName}_entities.json').write_text(
        json.dumps(entities, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )




