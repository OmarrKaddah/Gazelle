from neo4j import GraphDatabase
from embedding import embedTexts
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBED_DIM, ENTITY_EMBED_BATCH


def setupEntityIndex(tx):
    tx.run(f"""
        CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
        FOR (e:Entity) ON (e.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {EMBED_DIM},
            `vector.similarity_function`: 'cosine'
        }}}}
    """)


def loadPending(tx):
    res = tx.run("""
        MATCH (e:Entity)
        WHERE e.embedding IS NULL
        RETURN e.canonicalId AS id, e.canonicalName AS name, e.aliases AS aliases
    """)
    return [dict(r) for r in res]


def writeEmbedding(tx, canonicalId, embedding):
    tx.run(
        "MATCH (e:Entity {canonicalId: $id}) SET e.embedding = $emb",
        id=canonicalId,
        emb=embedding,
    )


# Concatenate canonical name + aliases so semantically equivalent surface forms
# pull the entity's vector toward all of them, not just the first-seen variant.
def buildEmbedText(entity):
    parts = [entity['name']] + (entity['aliases'] or [])
    return ' / '.join(dict.fromkeys(p for p in parts if p))


def embedWithSkip(texts):
    try:
        return embedTexts(texts)
    except RuntimeError:
        if len(texts) == 1:
            print(f"[skip] {texts[0][:60]}", flush=True)
            return [None]
        mid = len(texts) // 2
        return embedWithSkip(texts[:mid]) + embedWithSkip(texts[mid:])


def embedEntities():
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupEntityIndex)
            entities = session.execute_read(loadPending)
            print(f"Embedding {len(entities)} entities", flush=True)
            skipped = 0
            for i in range(0, len(entities), ENTITY_EMBED_BATCH):
                batch = entities[i:i + ENTITY_EMBED_BATCH]
                texts = [buildEmbedText(e) for e in batch]
                embs = embedWithSkip(texts)
                for entity, emb in zip(batch, embs):
                    if emb is None:
                        skipped += 1
                        continue
                    session.execute_write(writeEmbedding, entity['id'], emb)
                print(f"Embedded {min(i + ENTITY_EMBED_BATCH, len(entities))}/{len(entities)} ({skipped} skipped)", flush=True)
