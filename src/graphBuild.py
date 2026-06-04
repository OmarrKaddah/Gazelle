import json
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from kgBuild import canonicalId, canonicalKey, loadChunks, setupConstraints, writeChunks, writeDocument


def loadElements(docName):
    return json.loads(Path(f'extractions/{docName}_graph.json').read_text(encoding='utf-8'))


def mergeEntities(docName, instances):
    grouped = {}
    for inst in instances:
        for name, type, desc in inst['entities']:
            key = (canonicalKey(name), type)
            if key not in grouped:
                grouped[key] = {
                    'canonicalId': canonicalId(docName, key[0], type),
                    'canonicalName': name.strip(),
                    'type': type,
                    'docName': docName,
                    'descriptions': [],
                    'aliases': set(),
                    'chunkIds': set(),
                }
            rec = grouped[key]
            if desc:
                rec['descriptions'].append(desc)
            surface = name.strip()
            if surface != rec['canonicalName']:
                rec['aliases'].add(surface)
            rec['chunkIds'].add(inst['chunkId'])
    for rec in grouped.values():
        rec['description'] = ' '.join(dict.fromkeys(rec.pop('descriptions')))
        rec['aliases'] = sorted(rec['aliases'])
        rec['chunkIds'] = sorted(rec['chunkIds'])
    return list(grouped.values())


def buildNameLookup(entities):
    lookup = {}
    for e in entities:
        for surface in [e['canonicalName']] + e['aliases']:
            lookup.setdefault(canonicalKey(surface), e['canonicalId'])
    return lookup


def mergeRelationships(instances, lookup):
    edges = defaultdict(lambda: {'weight': 0, 'descriptions': set()})
    raw = unmatched = selfRef = 0
    for inst in instances:
        for src, dst, desc, _strength in inst['relationships']:
            raw += 1
            srcId = lookup.get(canonicalKey(src))
            dstId = lookup.get(canonicalKey(dst))
            if srcId is None or dstId is None:
                unmatched += 1
                continue
            if srcId == dstId:
                selfRef += 1
                continue
            edge = edges[(srcId, dstId)]
            edge['weight'] += 1
            if desc:
                edge['descriptions'].add(desc)
    print(f'[graphBuild] {raw} raw rels, {unmatched} unmatched (orphan endpoints), {selfRef} self-referential, {len(edges)} unique pairs')
    return [
        {'src': src, 'dst': dst, 'weight': d['weight'], 'description': ' '.join(sorted(d['descriptions']))}
        for (src, dst), d in edges.items()
    ]


def writeEntities(tx, entities):
    tx.run(
        '''
        UNWIND $entities AS e
        MERGE (ent:Entity {canonicalId: e.canonicalId})
        ON CREATE SET ent.canonicalName = e.canonicalName, ent.type = e.type,
                      ent.docName = e.docName, ent.description = e.description, ent.aliases = e.aliases
        ON MATCH SET ent.description = e.description,
                     ent.aliases = [a IN e.aliases WHERE NOT a IN ent.aliases] + ent.aliases
        WITH ent, e
        UNWIND e.chunkIds AS cid
        MATCH (c:Chunk {chunkId: cid})
        MERGE (ent)-[:MENTIONED_IN]->(c)
        ''',
        entities=entities,
    )


def writeRelated(tx, edges):
    tx.run(
        '''
        UNWIND $edges AS e
        MATCH (a:Entity {canonicalId: e.src}), (b:Entity {canonicalId: e.dst})
        MERGE (a)-[r:RELATED]->(b)
        SET r.weight = e.weight, r.description = e.description
        ''',
        edges=edges,
    )


def writeGraph(docName, entities, edges, chunks):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupConstraints)
            session.execute_write(writeDocument, docName)
            session.execute_write(writeChunks, docName, chunks)
            session.execute_write(writeEntities, entities)
            session.execute_write(writeRelated, edges)


def buildGraph(docName):
    instances = loadElements(docName)
    chunks = loadChunks(docName)
    entities = mergeEntities(docName, instances)
    edges = mergeRelationships(instances, buildNameLookup(entities))
    writeGraph(docName, entities, edges, chunks)
    print(f'[graphBuild] {docName}: {len(entities)} entities, {len(edges)} RELATED edges')
