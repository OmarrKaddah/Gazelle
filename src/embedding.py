import json
import os
from pathlib import Path
from FlagEmbedding import BGEM3FlagModel
from neo4j import GraphDatabase
from dotenv import load_dotenv


load_dotenv()
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']

EMBED_DIM = 1024
BATCH_SIZE = 16
BGE_M3_PATH = os.environ.get('BGE_M3_PATH', 'BAAI/bge-m3')
HF_HUB_OFFLINE = os.environ.get('HF_HUB_OFFLINE', '') == '1'

if BGE_M3_PATH == 'BAAI/bge-m3' and HF_HUB_OFFLINE:
    raise RuntimeError('Set BGE_M3_PATH to a local BGE-M3 snapshot when HF_HUB_OFFLINE=1')

model = BGEM3FlagModel(BGE_M3_PATH, use_fp16=True)


def embedTexts(texts):
    out = model.encode(texts, max_length=8192, return_dense=True, return_sparse=False, return_colbert_vecs=False)
    return out['dense_vecs'].tolist()


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
        with driver.session() as session:
            session.execute_write(setupVectorIndex)
            session.execute_write(setupFulltextIndex)
            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i:i + BATCH_SIZE]
                texts = [c['text'] for c in batch]
                embs = embedTexts(texts)
                for chunk, emb in zip(batch, embs):
                    session.execute_write(writeEmbedding, chunk['chunkId'], emb)
                print(f"Embedded {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}", flush=True)
