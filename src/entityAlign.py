import re
import numpy as np
from neo4j import GraphDatabase
from embedding import embedTexts
from ontology import RELATIONSHIPS
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DB, SIM_THRESHOLD, SKIP_SIM_TYPES


def normalizeArabic(text):
    text = re.sub(r'[ً-ٟ]', '', text)    # strip tashkeel
    text = re.sub(r'[أإآ]', 'ا', text)   # أ إ آ → ا
    text = re.sub(r'ى', 'ي', text)        # ى → ي
    return re.sub(r'\s+', ' ', text).strip()


def loadEntities(tx):
    res = tx.run("""
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(c:Chunk)
        RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type,
               e.aliases AS aliases, count(c) AS mentions
    """)
    return [dict(r) for r in res]


def pairwiseCos(vecs):
    mat = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    mat = mat / np.maximum(norms, 1e-9)
    return (mat @ mat.T).astype(float)


def findClusters(entities, embeddings, threshold):
    n = len(entities)
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    normNames = [normalizeArabic(e['name']) for e in entities]

    for i in range(n):
        for j in range(i + 1, n):
            if entities[i]['type'] != entities[j]['type']:
                continue
            if normNames[i] == normNames[j]:
                parent[root(i)] = root(j)

    simMat = pairwiseCos(embeddings)
    for i in range(n):
        if entities[i]['type'] in SKIP_SIM_TYPES:
            continue
        for j in range(i + 1, n):
            if entities[j]['type'] in SKIP_SIM_TYPES:
                continue
            if entities[i]['type'] != entities[j]['type']:
                continue
            if simMat[i, j] >= threshold:
                parent[root(i)] = root(j)

    clusters: dict = {}
    for i in range(n):
        clusters.setdefault(root(i), []).append(i)
    return [g for g in clusters.values() if len(g) > 1]


def redirectMentions(tx, dupIds, canonId):
    tx.run("""
        MATCH (dup:Entity) WHERE dup.canonicalId IN $dupIds
        MATCH (dup)-[:MENTIONED_IN]->(c:Chunk)
        MATCH (canon:Entity {canonicalId: $canonId})
        MERGE (canon)-[:MENTIONED_IN]->(c)
    """, dupIds=dupIds, canonId=canonId)


def redirectRelType(tx, dupIds, canonId, relType):
    tx.run(f"""
        MATCH (dup:Entity) WHERE dup.canonicalId IN $dupIds
        MATCH (dup)-[r:{relType}]->(o:Entity)
        WHERE o.canonicalId <> $canonId
        MATCH (canon:Entity {{canonicalId: $canonId}})
        MERGE (canon)-[nr:{relType}]->(o)
        ON CREATE SET nr.chunkIds = r.chunkIds
        ON MATCH SET nr.chunkIds = REDUCE(acc = nr.chunkIds, x IN r.chunkIds |
            CASE WHEN x IN acc THEN acc ELSE acc + x END)
    """, dupIds=dupIds, canonId=canonId)
    tx.run(f"""
        MATCH (dup:Entity) WHERE dup.canonicalId IN $dupIds
        MATCH (s:Entity)-[r:{relType}]->(dup)
        WHERE s.canonicalId <> $canonId
        MATCH (canon:Entity {{canonicalId: $canonId}})
        MERGE (s)-[nr:{relType}]->(canon)
        ON CREATE SET nr.chunkIds = r.chunkIds
        ON MATCH SET nr.chunkIds = REDUCE(acc = nr.chunkIds, x IN r.chunkIds |
            CASE WHEN x IN acc THEN acc ELSE acc + x END)
    """, dupIds=dupIds, canonId=canonId)


def updateAliases(tx, canonId, aliases):
    tx.run("""
        MATCH (e:Entity {canonicalId: $canonId})
        SET e.aliases = REDUCE(acc = e.aliases, x IN $aliases |
            CASE WHEN x IN acc THEN acc ELSE acc + x END)
    """, canonId=canonId, aliases=aliases)


def deleteEntities(tx, dupIds):
    tx.run(
        "MATCH (e:Entity) WHERE e.canonicalId IN $dupIds DETACH DELETE e",
        dupIds=dupIds,
    )


def mergeCluster(session, entities, group):
    canonical = max(group, key=lambda i: (entities[i]['mentions'], len(entities[i]['name'])))
    canonId = entities[canonical]['id']
    dupIds = [entities[i]['id'] for i in group if i != canonical]
    aliases = [entities[i]['name'] for i in group] + [
        a for i in group for a in (entities[i]['aliases'] or [])
    ]
    session.execute_write(redirectMentions, dupIds, canonId)
    for relType in RELATIONSHIPS:
        session.execute_write(redirectRelType, dupIds, canonId, relType)
    session.execute_write(updateAliases, canonId, aliases)
    session.execute_write(deleteEntities, dupIds)
    merged = [entities[i]['name'] for i in group if i != canonical]
    print(f"Merged into '{entities[canonical]['name']}': {merged}", flush=True)


def deduplicate(threshold=SIM_THRESHOLD):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session(database=NEO4J_DB) as session:
            entities = session.execute_read(loadEntities)
    print(f"Loaded {len(entities)} entities", flush=True)
    embeddings = embedTexts([e['name'] for e in entities])
    clusters = findClusters(entities, embeddings, threshold)
    print(f"Found {len(clusters)} duplicate clusters", flush=True)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session(database=NEO4J_DB) as session:
            for cluster in clusters:
                mergeCluster(session, entities, cluster)
    print("Done", flush=True)
