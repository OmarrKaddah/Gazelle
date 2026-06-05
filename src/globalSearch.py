import json
from neo4j import GraphDatabase
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Stage 2 of the global arm — GraphRAG map-reduce over community reports. Each
# community report independently produces a partial answer + a helpfulness score
# (map); the top-scored partials are combined into the final answer (reduce). This
# is what makes the answer *global*: the whole corpus is considered through its
# community summaries, nothing is retrieved away. Default level 0 = root (C0), the
# level the paper shows is ~as good as deeper ones at a fraction of the tokens.

MAP_PROMPT = '''Answer the question using ONLY the community report below. If the report is not
relevant to the question, say so and score 0.

Give a partial answer and a helpfulness score from 0-100 (how useful this report is for answering
the question). Preserve any [Data: ...] references from the report in your partial answer.

Return JSON only: {{"answer": "...", "score": 0}}

Question: {query}

Community report:
{report}'''

REDUCE_PROMPT = '''Combine the partial answers below into a single comprehensive answer to the question.
The partials come from independent analyses of different parts of the corpus; merge them, remove
redundancy, and preserve their [Data: ...] references. Do not add information not present in the partials.

Return JSON only: {{"answer": "..."}}

Question: {query}

Partial answers (each from one community, most helpful first):
{partials}'''


def loadCommunityReports(corpus, level=0):
    cypher = '''
    MATCH (c:Community {corpus: $corpus, level: $level})
    WHERE c.report IS NOT NULL
    RETURN c.id AS id, c.report AS report
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return [(r['id'], r['report']) for r in session.run(cypher, corpus=corpus, level=level)]


def mapCommunity(query, report, backend):
    raw = json.loads(callLLM(MAP_PROMPT.format(query=query, report=report), backend=backend))
    return raw.get('answer', ''), int(raw.get('score', 0))


def reduceAnswers(query, partials, backend):
    ranked = sorted(partials, key=lambda p: -p[1])
    block = '\n\n'.join(f'[helpfulness {score}] {answer}' for answer, score in ranked)
    raw = json.loads(callLLM(REDUCE_PROMPT.format(query=query, partials=block), backend=backend))
    return raw.get('answer', '')


def globalSearch(query, corpus, level=0, backend='openrouter'):
    reports = loadCommunityReports(corpus, level)
    partials = [mapCommunity(query, report, backend) for _, report in reports]
    partials = [(answer, score) for answer, score in partials if score > 0]
    if not partials:
        return 'The corpus does not contain information relevant to this question.'
    return reduceAnswers(query, partials, backend)
