import json
import re
from collections import defaultdict
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EXTRACT_DIR


def loadChunks(docName):
                              
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def loadEntitySpans(docName):
                            
    return json.loads(Path(f'{EXTRACT_DIR}/{docName}_entities.json').read_text(encoding='utf-8'))



# Arabic normalization (Lucene ArabicNormalizer set): fold alef/ya/ta-marbuta variants and drop
# tatweel + diacritics, so variant surface forms merge to one canonical key. Digits are preserved.
_AR_DIACRITICS = re.compile('[ـً-ٰٟ]')  # tatweel, tashkeel, superscript alef
_AR_FOLD = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',  # أإآٱ -> ا
    'ى': 'ي',  # ى -> ي
    'ة': 'ه',  # ة -> ه
})


def canonicalKey(text):
                         
    text = _AR_DIACRITICS.sub('', text).translate(_AR_FOLD)
         
    return re.sub(r'\s+', ' ', text).strip().lower()


def canonicalId(docName, key, type):
                         
    slug = re.sub(r'\s+', '-', key)
              
    return f'{docName}-{slug}-{type.lower()}'


def groupEntities(docName, spans):
    grouped = {}
    for s in spans:
                    
        key = (canonicalKey(s['text']), s['type'])         
        if key not in grouped:
            grouped[key] = {
                'canonicalId': canonicalId(docName, key[0], key[1]),
                'canonicalName': s['text'].strip(),
                'type': s['type'],
                'docName': docName,
                'aliases': set(),
                'chunkIds': set(),
            }
        rec = grouped[key]
        surface = s['text'].strip()
                       
        if surface != rec['canonicalName']:
            rec['aliases'].add(surface)              
        rec['chunkIds'].add(s['chunkId'])
    for rec in grouped.values():             
        rec['aliases'] = sorted(rec['aliases'])            
        rec['chunkIds'] = sorted(rec['chunkIds'])
    return list(grouped.values())


def setupConstraints(tx):
    tx.run('CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.docName IS UNIQUE')
    tx.run('CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE')
    tx.run('CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonicalId IS UNIQUE')


def writeDocument(tx, docName):
    tx.run('MERGE (:Document {docName: $docName})', docName=docName)


def writeChunks(tx, docName, chunks):
    tx.run(
        '''
        UNWIND $chunks AS c
        MATCH (d:Document {docName: $docName})
        MERGE (chunk:Chunk {chunkId: c.chunkId})
        SET chunk += c
        MERGE (chunk)-[:PART_OF]->(d)
        ''',
        docName=docName,
        chunks=chunks,
    )


def writeEntities(tx, entities):
    tx.run(
        '''
        UNWIND $entities AS e
        MERGE (ent:Entity {canonicalId: e.canonicalId})
        ON CREATE SET ent.canonicalName = e.canonicalName,
                      ent.type = e.type,
                      ent.docName = e.docName,
                      ent.aliases = e.aliases
        ON MATCH SET ent.aliases = [a IN e.aliases WHERE NOT a IN ent.aliases] + ent.aliases
        WITH ent, e
        UNWIND e.chunkIds AS cid
        MATCH (c:Chunk {chunkId: cid})
        MERGE (ent)-[:MENTIONED_IN]->(c)
        ''',
        entities=entities,
    )


def writeCoMentions(tx, docName):
    result = tx.run(
        '''
        MATCH (e1:Entity {docName: $docName})-[:MENTIONED_IN]->(c:Chunk)<-[:MENTIONED_IN]-(e2:Entity {docName: $docName})
        WHERE e1.canonicalId < e2.canonicalId
        WITH e1, e2, count(DISTINCT c) AS weight
        MERGE (e1)-[r:COOCCURS_WITH]->(e2)
        SET r.count = weight
        RETURN count(r) AS edges
        ''',
        docName=docName,
    )
    return result.single()['edges']


def loadNameLookup(docName):
    cypher = '''
    MATCH (e:Entity {docName: $docName})
    RETURN e.canonicalId AS id, e.canonicalName AS name, e.aliases AS aliases
    '''
    lookup = {}
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            for r in session.run(cypher, docName=docName):
                for surface in [r['name']] + (r['aliases'] or []):
                    lookup.setdefault(surface.lower().strip(), r['id'])
    return lookup


def writeTripleEdges(docName):             
    triplesPath = Path(f'extractions/{docName}_triples.json')
    data = json.loads(triplesPath.read_text(encoding='utf-8'))
    lookup = loadNameLookup(docName)

    edgeData = defaultdict(lambda: {'count': 0, 'predicates': set()})
    raw = unmatched = selfRef = 0
    for entry in data:

        for triple in entry['triples']:

            if len(triple) != 3:
                continue

            raw += 1
            subText, pred, objText = triple
            subId = lookup.get(subText.lower().strip())
            objId = lookup.get(objText.lower().strip())
            if subId is None or objId is None:
                unmatched += 1

                continue

            if subId == objId:
                selfRef += 1
                continue
            
            key = (subId, objId)
            edgeData[key]['count'] += 1
            edgeData[key]['predicates'].add(pred)

    print(f'[triples] {raw} raw, {unmatched} unmatched (orphan endpoints), {selfRef} self-referential, {len(edgeData)} unique entity pairs')

    payload = [
        {'sub': sub, 'obj': obj, 'count': d['count'], 'predicates': sorted(d['predicates'])}
        for (sub, obj), d in edgeData.items()
    ]
    cypher = '''
    UNWIND $edges AS e
    MATCH (a:Entity {canonicalId: e.sub}), (b:Entity {canonicalId: e.obj})
    MERGE (a)-[r:TRIPLE]->(b)
    SET r.count = e.count, r.predicates = e.predicates
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, edges=payload))
    print(f'[triples] wrote {len(payload)} TRIPLE edges')


def buildEntityLayer(docName):
    chunks = loadChunks(docName)
    spans = loadEntitySpans(docName)
    entities = groupEntities(docName, spans)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupConstraints)
            session.execute_write(writeDocument, docName)
            session.execute_write(writeChunks, docName, chunks)
            session.execute_write(writeEntities, entities)
            edges = session.execute_write(writeCoMentions, docName)
    print(f'[kgBuild] {docName}: {len(chunks)} chunks, {len(entities)} entities, {len(spans)} mentions, {edges} co-mention edges')
