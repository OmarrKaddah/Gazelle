import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from neo4j import GraphDatabase
from llmTriples import callLLM
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD



MAX_CONTEXT_CHARS = 8000  


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




def parseJson(raw):

    raw = raw.strip()
    start, end = raw.find('{'), raw.rfind('}')
    return json.loads(raw[start:end + 1] if start != -1 and end > start else raw)


def toFloat(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def summarize(context, backend):
 
    for _ in range(3):
        raw = callLLM(SUMMARY_PROMPT.format(context=context), backend=backend)
        try:
            report = parseJson(raw)
        except json.JSONDecodeError:
            continue
        report['rating'] = toFloat(report.get('rating'))
        return report
    return None


def summarizeLeaf(members, edges, backend):
    return summarize(formatElements(members, edges), backend)


def summarizeParent(childReports, members, edges, backend):

    childContext = '\n\n'.join(reportText(r) for r in childReports)

    elements = formatElements(members, edges)

    budget = MAX_CONTEXT_CHARS - len(childContext)

    context = 'Sub-community reports:\n' + childContext
    if budget > 500 :
        context += '\n\nAdditional elements:\n' + elements[:budget]
    return summarize(context, backend)




def storedReport(row):
    #store one b one
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


def summarizeOne(cid, members, edges, childReports, backend):

    if childReports is not None:

        return cid, summarizeParent(childReports, members, edges, backend)
    return cid, summarizeLeaf(members, edges, backend)


def summarizeHierarchy(corpus, backend='openrouter', workers=8):
    # Walk levels finest->root so a parent children are summarised first.
   
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            nodes, childrenOf = loadHierarchy(session, corpus)
            reports = {cid: n['report'] for cid, n in nodes.items()}   # prior runs already filled
            byLevel = defaultdict(list)

            for cid, n in nodes.items():

                byLevel[n['level']].append(cid)
            done = 0
            for level in sorted(byLevel, reverse=True):    # highest level = finest = leaves
                todo = [cid for cid in byLevel[level] if not reports[cid]]

                elems = {cid: communityElements(session, cid) for cid in todo}  

                jobs = []
                for cid in todo:
                    children = childrenOf.get(cid, [])

                    childReports = [reports[c] for c in children if reports.get(c)] if children else None

                    jobs.append((cid, *elems[cid], childReports, backend))

                total = len(byLevel[level])

                with ThreadPoolExecutor(max_workers=workers) as pool:

                    futures = [pool.submit(summarizeOne, *job) for job in jobs]

                    for fut in as_completed(futures):       # write 
                        cid, report = fut.result()

                        if report is None:
                            print(f'  [warn] {cid}: summary unparseable, skipping (retried on resume)', flush=True)

                            continue
                        reports[cid] = report
                        writeReport(session, cid, report)

                        done += 1

                        if done % 20 == 0:
                            print(f'[communitySummary] {corpus}: {done} summarised', flush=True)

                print(f'[communitySummary] {corpus}: level {level} complete ({len(todo)}/{total} communities, {done} total)', flush=True)

    print(f'[communitySummary] {corpus}: {done} communities summarised ({len(nodes)} total)')
