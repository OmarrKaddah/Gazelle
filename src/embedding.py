import json
import requests
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DB, EMBED_DIM, CHUNK_EMBED_BATCH, OLLAMA_EMBED_URL, OLLAMA_EMBED_MODEL


def embedTexts(texts):
    resp = requests.post(OLLAMA_EMBED_URL, json={"model": OLLAMA_EMBED_MODEL, "input": texts})
    return resp.json()["embeddings"]


def embedQuery(query):
    return embedTexts([query])[0]


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
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session(database=NEO4J_DB) as session:
            session.execute_write(setupVectorIndex)
            session.execute_write(setupFulltextIndex)
            for i in range(0, len(chunks), CHUNK_EMBED_BATCH):
                batch = chunks[i:i + CHUNK_EMBED_BATCH]
                texts = [c['text'] for c in batch]
                embs = embedTexts(texts)
                for chunk, emb in zip(batch, embs):
                    session.execute_write(writeEmbedding, chunk['chunkId'], emb)
                print(f"Embedded {min(i + CHUNK_EMBED_BATCH, len(chunks))}/{len(chunks)}", flush=True)
