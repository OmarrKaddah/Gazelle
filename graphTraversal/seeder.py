import _bootstrap  # noqa: F401
import numpy as np
from neo4j import GraphDatabase
from embedding import embedQuery
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def loadEntityEmbeddings(docName):
    cypher = '''
    MATCH (e:Entity {docName: $docName})
    WHERE e.embedding IS NOT NULL
    RETURN e.canonicalId AS id, e.canonicalName AS name, e.embedding AS emb
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            records = list(session.run(cypher, docName=docName))
    idxToId = [r['id'] for r in records]
    idxToName = [r['name'] for r in records]
    embs = np.array([r['emb'] for r in records], dtype=np.float32)
    embs = embs / np.linalg.norm(embs, axis=1, keepdims=True)
    return idxToId, idxToName, embs


def seedFromQuery(query, idxToId, embs, topK=5):
    qVec = np.array(embedQuery(query), dtype=np.float32)
    qVec = qVec / np.linalg.norm(qVec)
    sims = embs @ qVec
    topIdx = np.argpartition(-sims, topK)[:topK]
    topIdx = topIdx[np.argsort(-sims[topIdx])]
    topSims = np.maximum(sims[topIdx], 0)
    mass = topSims / topSims.sum()
    return [(idxToId[i], float(s), float(m)) for i, s, m in zip(topIdx, topSims, mass)]
