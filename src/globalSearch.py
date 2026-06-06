import json
from neo4j import GraphDatabase
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD



MAP_BATCH_CHARS = 10000   
REDUCE_TOP_POINTS = 40    # cap the points fed to reduce, highest score first


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
            return [(r['id'], r['report']) for r in session.run(cypher, corpus=corpus, level=level)]




def batchReports(reports, budget=MAP_BATCH_CHARS):
    # greedily pack report texts into batches that fit the char budget.
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
    

    print(f'  batch broke ({len(reports)} reports), ', flush=True)
    return []




def reduceAnswers(query, points, backend):


    ranked = sorted(points, key=lambda p: -p[1])[:REDUCE_TOP_POINTS]


    block = '\n'.join(f'- ({score}) {desc}' for desc, score in ranked)


    raw = parseJson(callLLM(REDUCE_PROMPT.format(query=query, points=block), backend=backend))
    return asText(raw.get('answer', ''))            





def globalSearch(query, corpus, level=0, backend='openrouter'):
    reports = [rep for _, rep in loadCommunityReports(corpus, level)]
    points = []              


    for batch in batchReports(reports):

        points += mapBatch(query, batch, backend)
    points = [(desc, score) for desc, score in points if score > 0]


    if not points:
        return REFUSAL
    return reduceAnswers(query, points, backend)
