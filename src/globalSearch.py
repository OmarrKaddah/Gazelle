import json
import numpy as np
from neo4j import GraphDatabase
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


MAP_BATCH_CHARS = 10000
REDUCE_TOP_POINTS = 100
DEFAULT_TOP_REPORTS = 20
MAX_REPORT_CHARS = 2500

REFUSAL = 'The provided context does not contain enough information to answer this question.'

MAP_PROMPT = '''You are answering a question using several community reports drawn from a corpus.

From the reports below, extract the key points relevant to answering the question. Each point is a
single self-contained claim with a helpfulness score 0-100 (how useful it is for the question).
Preserve any [Data: ...] references. Ignore reports that are not relevant.

Return JSON only: {{"points": [{{"description": "...", "score": 0}}]}}

Question: {query}

Community reports:
{reports}'''

REDUCE_PROMPT = '''Synthesise the key points below into a single comprehensive answer to the question.
The points were extracted independently from different parts of the corpus.

Write flowing PROSE, not a bare list: group related points into a few short paragraphs, briefly explain
each, merge duplicates, and preserve the [Data: ...] references. Do not add information not present in the
points. The "answer" value must be a single prose string.

Return JSON only: {{"answer": "..."}}

Question: {query}

Key points (most helpful first):
{points}'''


def _vectorRank(queryEmb, corpus, level, topK):
    cypher = """
    CALL db.index.vector.queryNodes('community_embedding', $topK, $emb)
    YIELD node, score
    WHERE node.corpus = $corpus AND node.level = $level AND node.report IS NOT NULL
    RETURN node.id AS id, node.report AS report, score
    """
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return [(r['id'], r['report'], r['score'])
                    for r in session.run(cypher, emb=queryEmb.tolist(), topK=topK * 4,
                                         corpus=corpus, level=level)][:topK]


def _fallbackRank(queryEmb, rows, topK):
    # used when community embeddings haven't been written yet
    from embedding import embedNanSafe
    scored = []
    for cid, rep in rows:
        vec = np.asarray(embedNanSafe(rep), dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        scored.append((float(np.dot(queryEmb, vec)), cid, rep))
    scored.sort(key=lambda x: -x[0])
    return [(cid, rep, score) for score, cid, rep in scored[:topK]]


def rankReports(queryEmb, corpus, level, rows, topK):
    try:
        ranked = _vectorRank(queryEmb, corpus, level, topK)
        if ranked:
            return ranked
    except Exception as e:
        print(f"[globalSearch] vector index unavailable ({e}), falling back to on-the-fly embed", flush=True)
    return _fallbackRank(queryEmb, rows, topK)


def asText(x):
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return ' '.join(asText(i) for i in x)
    return json.dumps(x, ensure_ascii=False)


def toScore(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def parseJson(raw):
    raw = raw.strip()
    start, end = raw.find('{'), raw.rfind('}')
    return json.loads(raw[start:end + 1] if start != -1 and end > start else raw)


def loadCommunityReports(corpus, level=0):
    cypher = '''
    MATCH (c:Community {corpus: $corpus, level: $level})
    WHERE c.report IS NOT NULL
    RETURN c.id AS id, c.report AS report
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return [(r['id'], r['report'][:MAX_REPORT_CHARS]) for r in session.run(cypher, corpus=corpus, level=level)]


def batchReports(reports, budget=MAP_BATCH_CHARS):
    batches, current, size = [], [], 0
    for rep in reports:
        if current and size + len(rep) > budget:
            batches.append(current)
            current, size = [], 0
        current.append(rep)
        size += len(rep)
    if current:
        batches.append(current)
    return batches


def mapBatch(query, reports, backend):
    block = '\n\n---\n\n'.join(reports)
    for _ in range(3):
        raw = callLLM(MAP_PROMPT.format(query=query, reports=block), backend=backend)
        try:
            data = parseJson(raw)
        except json.JSONDecodeError:
            continue
        return [(asText(p.get('description', '')), toScore(p.get('score'))) for p in data.get('points', [])]
    print(f'  batch broke ({len(reports)} reports)', flush=True)
    return []


def reduceAnswers(query, points, backend):
    ranked = sorted(points, key=lambda p: -p[1])[:REDUCE_TOP_POINTS]
    block = '\n'.join(f'- ({score}) {desc}' for desc, score in ranked)
    raw = parseJson(callLLM(REDUCE_PROMPT.format(query=query, points=block), backend=backend))
    return asText(raw.get('answer', ''))


def globalSearch(query, corpus, level=0, backend='openrouter', useLlmMap=True, topReports=DEFAULT_TOP_REPORTS):
    rows = loadCommunityReports(corpus, level)
    if not rows:
        return {"answer": REFUSAL, "chunks": []}

    from embedding import embedQuery
    queryEmb = np.asarray(embedQuery(query), dtype=np.float32)
    norm = np.linalg.norm(queryEmb)
    if norm > 0:
        queryEmb = queryEmb / norm

    ranked = rankReports(queryEmb, corpus, level, rows, topK=topReports)
    print(f'[globalSearch] {len(rows)} reports → top {len(ranked)} by cosine', flush=True)

    if not useLlmMap:
        chunks = [
            {"chunkId": f"community-{cid}", "text": rep, "sectionPath": ["Community", str(cid)],
             "pages": [], "docName": corpus, "score": round(score, 4), "source": "global"}
            for cid, rep, score in ranked
        ]
        return {"answer": None, "chunks": chunks}

    reports = [rep for _, rep, _ in ranked]
    points = []
    for batch in batchReports(reports):
        points += mapBatch(query, batch, backend)
    points = [(desc, score) for desc, score in points if score > 0]

    if not points:
        return {"answer": REFUSAL, "chunks": []}
    return {"answer": reduceAnswers(query, points, backend), "chunks": []}
