import _bootstrap  # noqa: F401
import re
import numpy as np
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def loadEntities():
    # Corpus-wide: every entity that has an embedding, across all docs. SYNONYM is an
    # identity-bridging layer over the unified entity graph, so it must span docs.
    cypher = '''
    MATCH (e:Entity)
    WHERE e.embedding IS NOT NULL
    RETURN e.canonicalId AS id, e.type AS type, e.canonicalName AS name, e.embedding AS emb
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            records = list(session.run(cypher))
    ids = [r['id'] for r in records]
    types = [r['type'] for r in records]
    tokens = [frozenset(re.findall(r'\w+', r['name'].lower())) for r in records]
    embs = np.array([r['emb'] for r in records], dtype=np.float32)
    embs = embs / np.linalg.norm(embs, axis=1, keepdims=True)
    return ids, types, tokens, embs


def findSynonymPairs(threshold=0.85, chunkSize=1000):
    ids, types, tokens, embs = loadEntities()
    pairs = []
    n = len(ids)
    for start in range(0, n, chunkSize):
        end = min(start + chunkSize, n)
        sims = embs[start:end] @ embs.T
        for localI in range(end - start):
            i = start + localI
            if not tokens[i]:
                continue
            for j in np.where(sims[localI] > threshold)[0]:
                if j <= i:
                    continue
                if types[i] != types[j] or not tokens[j]:
                    continue
                if not (tokens[i] <= tokens[j] or tokens[j] <= tokens[i]):
                    continue
                pairs.append((ids[i], ids[j], float(sims[localI, j])))
    return pairs


def writeSynonymEdges(threshold=0.85):
    pairs = findSynonymPairs(threshold)
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
