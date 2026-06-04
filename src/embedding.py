import json
import requests
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBED_DIM, CHUNK_EMBED_BATCH, OLLAMA_EMBED_URL, OLLAMA_EMBED_MODEL


_session = requests.Session()
_session.trust_env = False


def embedTexts(texts):
    resp = _session.post(OLLAMA_EMBED_URL, json={"model": OLLAMA_EMBED_MODEL, "input": texts})
    if resp.status_code != 200:
        sample = [t[:80] for t in texts[:3]]
        raise RuntimeError(f"ollama embed {resp.status_code}: {resp.text[:300]} | batch={len(texts)} maxlen={max(len(t) for t in texts)} sample={sample}")
    return resp.json()["embeddings"]


nanRescued = 0  # running count of chunks that triggered a NaN and had to be rescued


def embedNanSafe(text):
    # bge-m3 on Ollama deterministically emits NaN for certain (non-empty) inputs — a model/quant
    # bug, not bad data. Escapes that work vary by input; try content-preserving ones, then shrink.
    try:
        return embedTexts([text])[0]
    except RuntimeError as e:
        if 'NaN' not in str(e):
            raise
    global nanRescued
    nanRescued += 1
    try:
        return embedTexts([text.lower()])[0]
    except RuntimeError as e:
        if 'NaN' not in str(e):
            raise
    t = text
    while len(t) > 8:
        t = t[:len(t) * 3 // 4]
        try:
            return embedTexts([t])[0]
        except RuntimeError as e:
            if 'NaN' not in str(e):
                raise
    return embedTexts(['.'])[0]


def embedQuery(query):
    return embedNanSafe(query)


def embedBatch(texts):
    # One bad input would fail the whole batch; on NaN, fall back to per-item NaN-safe embedding.
    try:
        return embedTexts(texts)
    except RuntimeError as e:
        if 'NaN' not in str(e):
            raise
        print(f"  [warn] bge-m3 NaN in batch of {len(texts)}; retrying per-item", flush=True)
        return [embedNanSafe(t) for t in texts]


def loadChunks(docName):
    return json.loads(Path(f'chunks/{docName}.json').read_text(encoding='utf-8'))


def setupVectorIndex(tx):
    tx.run(f"""
        CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {EMBED_DIM},
            `vector.similarity_function`: 'cosine'
        }}}}
    """)


def setupFulltextIndex(tx):
    tx.run("""
        CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS
        FOR (c:Chunk) ON EACH [c.text]
    """)


def writeEmbedding(tx, chunkId, embedding):
    tx.run(
        "MATCH (c:Chunk {chunkId: $chunkId}) SET c.embedding = $embedding",
        chunkId=chunkId,
        embedding=embedding,
    )


def embedDoc(docName):
    chunks = loadChunks(docName)
    before = nanRescued
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupVectorIndex)
            session.execute_write(setupFulltextIndex)
            for i in range(0, len(chunks), CHUNK_EMBED_BATCH):
                batch = chunks[i:i + CHUNK_EMBED_BATCH]
                texts = [c['text'] for c in batch]
                embs = embedBatch(texts)
                for chunk, emb in zip(batch, embs):
                    session.execute_write(writeEmbedding, chunk['chunkId'], emb)
                print(f"Embedded {min(i + CHUNK_EMBED_BATCH, len(chunks))}/{len(chunks)}", flush=True)
    bad = nanRescued - before
    print(f"[embed] {docName}: {len(chunks)} chunks, {bad} needed NaN rescue", flush=True)
