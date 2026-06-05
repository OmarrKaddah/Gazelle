import _bootstrap  # noqa: F401
import json
from neo4j import GraphDatabase
from embedding import embedQuery
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Naive vector RAG — the baseline the global arm is judged against (the paper's
# vector-RAG comparator). Top-k chunk retrieval over the chunk_embedding index,
# then a single-shot synthesis. Self-contained (passes the corpus scope directly)
# so it doesn't drag in the production retriever's clearance machinery.

ANSWER_PROMPT = '''Answer the question using ONLY the numbered context passages below. Cite the
passages you use by their number, e.g. [1]. If the context is insufficient, say so.

Return JSON only: {{"answer": "..."}}

Question: {query}

Context:
{context}'''


def vectorChunks(query, corpus, topK):
    cypher = '''
    CALL db.index.vector.queryNodes('chunk_embedding', $pool, $emb) YIELD node, score
    WITH node, score WHERE node.docName = $corpus
    RETURN node.text AS text ORDER BY score DESC LIMIT $k
    '''
    emb = embedQuery(query)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            rows = session.run(cypher, emb=emb, pool=topK * 4, corpus=corpus, k=topK)
            return [r['text'] for r in rows]


def vectorAnswer(query, corpus='apnews', topK=10, backend='openrouter'):
    chunks = vectorChunks(query, corpus, topK)
    context = '\n\n'.join(f'[{i + 1}] {t}' for i, t in enumerate(chunks))
    raw = json.loads(callLLM(ANSWER_PROMPT.format(query=query, context=context), backend=backend))
    return raw.get('answer', '')
