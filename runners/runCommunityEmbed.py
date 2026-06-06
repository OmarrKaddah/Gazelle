import _bootstrap  # noqa: F401
import sys
import numpy as np
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from embedding import embedNanSafe

CORPUS = sys.argv[1] if len(sys.argv) > 1 else None
LEVEL  = int(sys.argv[2]) if len(sys.argv) > 2 else None
DIM    = 1024
BATCH  = 50


def ensureIndex(session):
    session.run("""
        CREATE VECTOR INDEX community_embedding IF NOT EXISTS
        FOR (c:Community) ON (c.embedding)
        OPTIONS {indexConfig: {`vector.dimensions`: $dim, `vector.similarity_function`: 'cosine'}}
    """, dim=DIM)


def loadPending(session, corpus, level):
    where = []
    params = {}
    if corpus:
        where.append("c.corpus = $corpus")
        params["corpus"] = corpus
    if level is not None:
        where.append("c.level = $level")
        params["level"] = level
    where.append("c.report IS NOT NULL")
    where.append("c.embedding IS NULL")
    clause = "WHERE " + " AND ".join(where)
    return session.run(
        f"MATCH (c:Community) {clause} RETURN c.id AS id, c.report AS report",
        **params,
    ).data()


def writeEmbeddings(session, batch):
    session.run(
        """
        UNWIND $rows AS row
        MATCH (c:Community {id: row.id})
        CALL db.create.setNodeVectorProperty(c, 'embedding', row.emb)
        """,
        rows=batch,
    )


def run():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        ensureIndex(session)
        rows = loadPending(session, CORPUS, LEVEL)

    total = len(rows)
    if total == 0:
        print("Nothing to embed — all community nodes already have embeddings.")
        return

    scope = f"corpus={CORPUS or 'all'} level={LEVEL if LEVEL is not None else 'all'}"
    print(f"Embedding {total} community reports ({scope})")

    done = 0
    pending = []

    for i, row in enumerate(rows):
        vec = np.asarray(embedNanSafe(row["report"]), dtype=np.float32).tolist()
        pending.append({"id": row["id"], "emb": vec})
        done += 1

        if len(pending) >= BATCH:
            with driver.session() as session:
                writeEmbeddings(session, pending)
            pending = []

        pct = done / total * 100
        bar = "#" * int(pct / 2)
        sys.stdout.write(f"\r  [{bar:<50}] {done}/{total} ({pct:.0f}%)")
        sys.stdout.flush()

    if pending:
        with driver.session() as session:
            writeEmbeddings(session, pending)

    print(f"\nDone. {done} embeddings written.")
    driver.close()


run()
