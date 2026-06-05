import json
from collections import Counter, defaultdict
from neo4j import GraphDatabase
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Stage 3 of the global arm — turn each (:Community) skeleton (Stage 4) into a
# structured report grounded in its entities and relationships, following GraphRAG
# (Edge et al., 2024, Appendix). Leaf communities are summarised from their elements;
# parent communities roll up their children's reports. Reports are written back onto
# the Community node so the map-reduce global search (Stage 2) can read them.
#
# Provenance: elements are handed to the LLM with short record ids (E0, R3, ...) and
# the prompt requires every finding to cite them as [Data: Entities (...); Relationships (...)],
# so answers trace back to graph evidence — the project's hallucination-resistance rule.

MAX_CONTEXT_CHARS = 8000   # ~2k tokens of element/child-report context per community


SUMMARY_PROMPT = '''You are writing an analyst report about a community of related entities from a corpus.

Using ONLY the data below, write a report with: a short title naming the community's main subject;
a summary paragraph; an importance rating from 0-10 (how significant this community is to the corpus);
and 3-7 findings, each a key insight. Every finding's explanation MUST cite the supporting records
inline as [Data: Entities (id, id); Relationships (id, id)] using the E# / R# ids given.

Return JSON only:
{{"title": "...", "summary": "...", "rating": 0.0, "rating_explanation": "...",
  "findings": [{{"summary": "...", "explanation": "... [Data: Entities (E0); Relationships (R2)]"}}]}}

Data:
{context}'''


# ── element selection (one community's evidence) ─────────────────

def communityMembers(session, communityId):
    rows = session.run(
        '''
        MATCH (e:Entity)-[:IN_COMMUNITY]->(:Community {id: $id})
        RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type,
               e.description AS description
        ''',
        id=communityId,
    )
    return [dict(r) for r in rows]


def communityEdges(session, communityId):
    rows = session.run(
        '''
        MATCH (a:Entity)-[r:RELATED]->(b:Entity)
        WHERE (a)-[:IN_COMMUNITY]->(:Community {id: $id})
          AND (b)-[:IN_COMMUNITY]->(:Community {id: $id})
        RETURN a.canonicalId AS src, b.canonicalId AS dst, r.predicate AS predicate,
               r.description AS description, r.weight AS weight
        ''',
        id=communityId,
    )
    return [dict(r) for r in rows]


def communityElements(session, communityId):
    members = communityMembers(session, communityId)
    edges = communityEdges(session, communityId)
    degree = Counter()
    for e in edges:
        degree[e['src']] += 1
        degree[e['dst']] += 1
    members.sort(key=lambda m: -degree[m['id']])
    edges.sort(key=lambda e: -(e['weight'] or 0))
    return members, edges


# ── prompt formatting (assigns the E#/R# record ids) ─────────────

def formatElements(members, edges):
    nameById = {m['id']: m['name'] for m in members}
    lines = ['Entities:']
    for i, m in enumerate(members):
        lines.append(f'E{i}: {m["name"]} ({m["type"]}) — {m["description"] or ""}')
    lines.append('')
    lines.append('Relationships:')
    for i, e in enumerate(edges):
        src, dst = nameById.get(e['src'], e['src']), nameById.get(e['dst'], e['dst'])
        pred = f' [{e["predicate"]}]' if e['predicate'] else ''
        lines.append(f'R{i}: {src} -> {dst}{pred} — {e["description"] or ""}')
    return '\n'.join(lines)[:MAX_CONTEXT_CHARS]


def reportText(report):
    findings = '\n'.join(f'- {f["summary"]}: {f["explanation"]}' for f in report.get('findings', []))
    return f'# {report["title"]}\n\n{report["summary"]}\n\n{findings}'


# ── summarisation (leaf + roll-up) ───────────────────────────────

def summarize(context, backend):
    report = json.loads(callLLM(SUMMARY_PROMPT.format(context=context), backend=backend))
    report['rating'] = float(report.get('rating', 0.0))
    return report


def summarizeLeaf(members, edges, backend):
    return summarize(formatElements(members, edges), backend)


def summarizeParent(childReports, members, edges, backend):
    childContext = '\n\n'.join(reportText(r) for r in childReports)
    elements = formatElements(members, edges)
    budget = MAX_CONTEXT_CHARS - len(childContext)
    context = 'Sub-community reports:\n' + childContext
    if budget > 500:
        context += '\n\nAdditional elements:\n' + elements[:budget]
    return summarize(context, backend)


# ── hierarchy walk + persistence ─────────────────────────────────

def storedReport(row):
    # Rebuild the report dict from the fields Stage 3 persists, for resume runs.
    if row['summary'] is None:
        return None
    return {'title': row['title'], 'summary': row['summary'],
            'findings': json.loads(row['findings']) if row['findings'] else []}


def loadHierarchy(session, corpus):
    rows = session.run(
        '''MATCH (c:Community {corpus: $corpus})
           RETURN c.id AS id, c.level AS level, c.title AS title, c.summary AS summary,
                  c.findings AS findings''',
        corpus=corpus,
    )
    nodes = {r['id']: {'level': r['level'], 'report': storedReport(r)} for r in rows}
    childrenOf = defaultdict(list)
    links = session.run(
        'MATCH (child:Community {corpus: $corpus})-[:PARENT]->(parent:Community) RETURN child.id AS child, parent.id AS parent',
        corpus=corpus,
    )
    for r in links:
        childrenOf[r['parent']].append(r['child'])
    return nodes, childrenOf


def writeReport(session, communityId, report):
    session.run(
        '''
        MATCH (c:Community {id: $id})
        SET c.title = $title, c.summary = $summary, c.rating = $rating,
            c.findings = $findings, c.report = $report
        ''',
        id=communityId, title=report['title'], summary=report['summary'],
        rating=report['rating'], findings=json.dumps(report.get('findings', [])),
        report=reportText(report),
    )


def summarizeHierarchy(corpus, backend='openrouter'):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            nodes, childrenOf = loadHierarchy(session, corpus)
            reports = {cid: n['report'] for cid, n in nodes.items()}   # prior runs already filled
            # finest (highest level) first, so a parent's children are ready before it.
            order = sorted(nodes, key=lambda cid: -nodes[cid]['level'])
            done = 0
            for cid in order:
                if reports[cid]:                              # resume-safe: already summarised
                    continue
                members, edges = communityElements(session, cid)
                children = childrenOf.get(cid, [])
                if children:
                    childReports = [reports[ch] for ch in children if reports.get(ch)]
                    report = summarizeParent(childReports, members, edges, backend)
                else:
                    report = summarizeLeaf(members, edges, backend)
                reports[cid] = report
                writeReport(session, cid, report)
                done += 1
                if done % 10 == 0:
                    print(f'[communitySummary] {corpus}: {done} summarised', flush=True)
    print(f'[communitySummary] {corpus}: {done} communities summarised ({len(nodes)} total)')
