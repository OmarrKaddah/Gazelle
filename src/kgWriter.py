import json
import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv
from ontology import ENTITIES, RELATIONSHIPS


load_dotenv()
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def loadExtractions(docName):
    return json.loads(Path(f'extractions/{docName}.json').read_text(encoding='utf-8'))


def isValidEntity(entity):
    return entity.get('canonicalId') and entity.get('type') in ENTITIES


def buildTypeMap(extractions):
    typeMap = {}
    for entry in extractions:
        for entity in entry['entities']:
            if isValidEntity(entity):
                typeMap[entity['canonicalId']] = entity['type']
    return typeMap


def isValidRelationship(rel, typeMap):
    predicate = rel.get('predicate')
    if predicate not in RELATIONSHIPS:
        return False
    sub = rel.get('subject')
    obj = rel.get('object')
    if not sub or not obj:
        return False
    subjects, objects = RELATIONSHIPS[predicate]
    return typeMap.get(sub) in subjects and typeMap.get(obj) in objects


def setupSchema(tx):
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.docName IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonicalId IS UNIQUE")


def mergeDocument(tx, docName):
    tx.run("MERGE (d:Document {docName: $docName})", docName=docName)


def mergeChunk(tx, chunk):
    tx.run(
        """
        MATCH (d:Document {docName: $docName})
        MERGE (c:Chunk {chunkId: $chunkId})
        SET c.docName = $docName,
            c.sectionPath = $sectionPath,
            c.pages = $pages,
            c.text = $text,
            c.accessLevel = $accessLevel
        MERGE (c)-[:PART_OF]->(d)
        """,
        chunkId=chunk['chunkId'],
        docName=chunk['docName'],
        sectionPath=chunk['sectionPath'],
        pages=chunk['pages'],
        text=chunk['text'],
        accessLevel=chunk['accessLevel'],
    )


def mergeEntityWithMention(tx, entity, chunkId):
    tx.run(
        """
        MERGE (e:Entity {canonicalId: $id})
        ON CREATE SET e.canonicalName = $name, e.type = $type, e.aliases = $aliases
        ON MATCH SET e.aliases = REDUCE(acc = e.aliases, x IN $aliases |
            CASE WHEN x IN acc THEN acc ELSE acc + x END)
        WITH e
        MATCH (c:Chunk {chunkId: $chunkId})
        MERGE (e)-[:MENTIONED_IN]->(c)
        """,
        id=entity['canonicalId'],
        name=entity['canonicalName'],
        type=entity['type'],
        aliases=entity.get('aliases', []),
        chunkId=chunkId,
    )


def mergeRelationship(tx, rel, chunkId):
    predicate = rel['predicate']
    tx.run(
        f"""
        MATCH (s:Entity {{canonicalId: $sub}}), (o:Entity {{canonicalId: $obj}})
        MERGE (s)-[r:{predicate}]->(o)
        ON CREATE SET r.chunkIds = $chunkIds
        ON MATCH SET r.chunkIds = REDUCE(acc = r.chunkIds, x IN $chunkIds |
            CASE WHEN x IN acc THEN acc ELSE acc + x END)
        """,
        sub=rel['subject'],
        obj=rel['object'],
        chunkIds=[chunkId],
    )


def writeDoc(docName):
    chunks = loadChunks(docName)
    extractions = loadExtractions(docName)
    typeMap = buildTypeMap(extractions)
    realDocName = chunks[0]['docName']
    entCount = 0
    relCount = 0
    relSkipped = 0
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupSchema)
            session.execute_write(mergeDocument, realDocName)
            for chunk in chunks:
                session.execute_write(mergeChunk, chunk)
            for entry in extractions:
                chunkId = entry['chunkId']
                for entity in entry['entities']:
                    if not isValidEntity(entity):
                        continue
                    session.execute_write(mergeEntityWithMention, entity, chunkId)
                    entCount += 1
                for rel in entry['relationships']:
                    if not isValidRelationship(rel, typeMap):
                        relSkipped += 1
                        continue
                    session.execute_write(mergeRelationship, rel, chunkId)
                    relCount += 1
    print(f"Wrote {len(chunks)} chunks, {entCount} entity mentions, {relCount} relationship edges ({relSkipped} skipped as schema-invalid)")
