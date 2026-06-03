import csv
import re
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


ICIJ_DIR = Path('Documents/icij')
BATCH = 5000

NODE_FILES = {
    'nodes-entities.csv': 'OffshoreEntity',
    'nodes-officers.csv': 'Officer',
    'nodes-intermediaries.csv': 'Intermediary',
    'nodes-addresses.csv': 'Address',
    'nodes-others.csv': 'Other',
}


def canonId(nodeId):
    return f'icij-{nodeId}'


def normalizeLink(link):
    s = re.sub(r'[^A-Za-z0-9]+', '_', (link or '').strip())
    return s.strip('_').upper() or 'LINKED_TO'


def readNodes(path, nodeType):
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodeId = row.get('node_id') or row.get('id')
            if not nodeId:
                continue
            yield {
                'canonicalId': canonId(nodeId),
                'canonicalName': row.get('name') or row.get('address') or nodeId,
                'type': nodeType,
                'jurisdiction': row.get('jurisdiction_description') or row.get('countries') or '',
                'sourceId': row.get('sourceID') or '',
            }


def readRels(path):
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            start = row.get('node_id_start') or row.get('START_ID')
            end = row.get('node_id_end') or row.get('END_ID')
            link = row.get('link') or row.get('rel_type') or 'linked_to'
            if not start or not end:
                continue
            yield {
                'start': canonId(start),
                'end': canonId(end),
                'predicate': normalizeLink(link),
            }


def chunked(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def setupSchema(tx):
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonicalId IS UNIQUE")


def upsertNodes(tx, rows):
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (e:Entity {canonicalId: row.canonicalId})
        SET e.canonicalName = row.canonicalName,
            e.type = row.type,
            e.jurisdiction = row.jurisdiction,
            e.sourceId = row.sourceId,
            e.docName = 'icij'
        """,
        rows=rows,
    )


def upsertRelsForPredicate(tx, predicate, rows):
    tx.run(
        f"""
        UNWIND $rows AS row
        MATCH (s:Entity {{canonicalId: row.start}})
        MATCH (o:Entity {{canonicalId: row.end}})
        MERGE (s)-[:`{predicate}`]->(o)
        """,
        rows=rows,
    )


def loadAll():
    if not ICIJ_DIR.exists():
        raise FileNotFoundError(f'Place ICIJ CSVs in {ICIJ_DIR.resolve()}')

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupSchema)

            for fname, nodeType in NODE_FILES.items():
                path = ICIJ_DIR / fname
                if not path.exists():
                    print(f'skip missing {fname}')
                    continue
                total = 0
                for batch in chunked(readNodes(path, nodeType), BATCH):
                    session.execute_write(upsertNodes, batch)
                    total += len(batch)
                print(f'{fname}: {total} nodes')

            relPath = ICIJ_DIR / 'relationships.csv'
            byPred = {}
            relTotal = 0
            for rel in readRels(relPath):
                byPred.setdefault(rel['predicate'], []).append(rel)
                if len(byPred[rel['predicate']]) >= BATCH:
                    session.execute_write(upsertRelsForPredicate, rel['predicate'], byPred[rel['predicate']])
                    relTotal += len(byPred[rel['predicate']])
                    byPred[rel['predicate']] = []
            for predicate, rows in byPred.items():
                if rows:
                    session.execute_write(upsertRelsForPredicate, predicate, rows)
                    relTotal += len(rows)
            print(f'relationships.csv: {relTotal} edges across {len(byPred)} predicates')
