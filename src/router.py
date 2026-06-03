import json
from llmTriples import callLLM

# Stage 1 — route a query to the global arm (community summaries) or the local arm
# (PPR over the entity graph). v1 is a single LLM judgment. The router is Gazelle's
# own design: GraphRAG ships local/global as separate methods the caller picks, so
# there is no published classifier to copy.

ROUTER_PROMPT = '''Classify the question by the scope of evidence it needs.

- "global": needs an understanding of the corpus as a whole — themes, trends,
  patterns, comparisons, or a summary ("main", "overall", "across the documents").
- "local": answerable from a specific fact, entity, number, date, or passage.

Return JSON only: {{"scope": "global"}} or {{"scope": "local"}}.

Question: "{query}"'''


def routeQuery(query, backend='ollama'):
    raw = callLLM(ROUTER_PROMPT.format(query=query), backend=backend)
    return json.loads(raw)['scope']
