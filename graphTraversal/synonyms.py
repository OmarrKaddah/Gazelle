import _bootstrap  # noqa: F401
import re
import numpy as np
from neo4j import GraphDatabase
from seeder import loadEntityEmbeddings
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def loadEntityMeta(docName):
    cypher = '''
    MATCH (e:Entity {docName: $docName})
    WHERE e.embedding IS NOT NULL
    RETURN e.canonicalId AS id, e.type AS type, e.canonicalName AS name
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            records = list(session.run(cypher, docName=docName))
    out = {}
    for r in records:
        out[r['id']] = {
            'type': r['type'],
            'tokens': frozenset(re.findall(r'\w+', r['name'].lower())),
        }
    return out


def findSynonymPairs(docName, threshold=0.85, chunkSize=1000):
    entIds, _, embs = loadEntityEmbeddings(docName)
    meta = loadEntityMeta(docName)
    pairs = []
    n = len(entIds)
    for start in range(0, n, chunkSize):
        end = min(start + chunkSize, n)
        sims = embs[start:end] @ embs.T
        for localI in range(end - start):
            i = start + localI
            mI = meta[entIds[i]]
            if not mI['tokens']:
                continue
            for j in np.where(sims[localI] > threshold)[0]:
                if j <= i:
                    continue
                mJ = meta[entIds[j]]
                if mI['type'] != mJ['type'] or not mJ['tokens']:
                    continue
                if not (mI['tokens'] <= mJ['tokens'] or mJ['tokens'] <= mI['tokens']):
                    continue
                pairs.append((entIds[i], entIds[j], float(sims[localI, j])))
    return pairs


def writeSynonymEdges(docName, threshold=0.85):
    pairs = findSynonymPairs(docName, threshold)
    print(f'[synonyms] found {len(pairs)} pairs at threshold {threshold}')
    payload = [{'a': a, 'b': b, 'cosine': c} for a, b, c in pairs]
    cypher = '''
    UNWIND $pairs AS p
    MATCH (a:Entity {canonicalId: p.a}), (b:Entity {canonicalId: p.b})
    MERGE (a)-[r:SYNONYM]->(b)
    SET r.cosine = p.cosine
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, pairs=payload))
    print(f'[synonyms] wrote {len(pairs)} SYNONYM edges')
