import json
import os
import requests
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neo4j import GraphDatabase
from dotenv import load_dotenv
from retriever import retrieve
from auth import login, logout, userFromToken, getCurrentUser, USERS
from docAccess import LEVELS, DOC_ACCESS


load_dotenv()
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OLLAMA_TEXT_MODEL = os.environ.get('OLLAMA_TEXT_MODEL', 'qwen3-vl:8b-instruct-q4_K_M')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

PROVIDERS = {
    'ollama': {'url': OLLAMA_URL, 'model': OLLAMA_TEXT_MODEL, 'apiKey': None},
    'groq': {'url': GROQ_URL, 'model': GROQ_MODEL, 'apiKey': GROQ_API_KEY},
}


app = FastAPI(title="Gazelle API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    mode: str = "vector"
    k: int = 5
    hops: int = 1
    provider: str = "ollama"


def buildContext(chunks):
    return "\n\n---\n\n".join(
        f"[{c['chunkId']} | section: {' > '.join(c.get('sectionPath') or [])} | pages: {c.get('pages')}]\n{c['text']}"
        for c in chunks
    )


SYSTEM_PROMPT = """You are Gazelle, a compliance assistant for Abu Dhabi Islamic Bank (ADIB).

STRICT GROUNDING RULES — these override every other instinct:
1. Answer using ONLY the provided CONTEXT chunks. Do NOT use general knowledge, training data, common-sense inferences, or any external information.
2. Every factual claim in your answer MUST be tied to a specific source by including the chunkId in square brackets, e.g. [chapter_3-c0017]. A claim without a citation is forbidden.
3. If the CONTEXT does not contain enough information to answer the question, respond with exactly:
   - In Arabic: "لا توجد معلومات كافية في السياق المتاح للإجابة على هذا السؤال."
   - In English: "The provided context does not contain enough information to answer this question."
   Match the language of the question. Do NOT guess. Do NOT fall back on what you think the answer might be.
4. Do NOT add background, examples, definitions, or related facts that are not explicitly stated in the CONTEXT.
5. Prefer short direct quotes from the CONTEXT over paraphrase. Be concise: 2–4 sentences unless the question genuinely requires a structured list.
6. If a question is partially covered, answer only the part the context supports and explicitly note what is missing.

When in doubt, refuse to answer rather than fabricate."""


def buildPrompt(query, chunks):
    return (
        f"CONTEXT:\n{buildContext(chunks)}\n\n"
        "---\n\n"
        "Reminder: answer ONLY using the CONTEXT above. Cite [chunkId] for every claim. "
        "If the context is insufficient, refuse using the exact refusal sentence per the system rules.\n\n"
        f"QUESTION: {query}"
    )


def streamTokens(query, chunks, provider='ollama'):
    if not chunks:
        yield "data: " + json.dumps({"type": "token", "text": "No relevant context was retrieved for this query."}) + "\n\n"
        return
    cfg = PROVIDERS.get(provider) or PROVIDERS['ollama']
    headers = {"Authorization": f"Bearer {cfg['apiKey']}"} if cfg['apiKey'] else {}
    response = requests.post(
        cfg['url'],
        headers=headers,
        json={
            "model": cfg['model'],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": buildPrompt(query, chunks)},
            ],
            "temperature": 0,
            "stream": True,
        },
        stream=True,
        timeout=300,
    )
    response.raise_for_status()
    response.encoding = 'utf-8'
    for raw in response.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data: "):
            continue
        payload = raw[6:]
        if payload == "[DONE]":
            break
        chunk = json.loads(payload)
        delta = chunk["choices"][0].get("delta", {}).get("content", "")
        if delta:
            yield "data: " + json.dumps({"type": "token", "text": delta}) + "\n\n"


@app.get("/api/info")
def infoEndpoint():
    return {
        "providers": {
            "ollama": {"model": OLLAMA_TEXT_MODEL, "available": True},
            "groq": {"model": GROQ_MODEL, "available": bool(GROQ_API_KEY)},
        },
        "levels": LEVELS,
    }


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def loginEndpoint(req: LoginRequest):
    token = login(req.username, req.password)
    if not token:
        return {"ok": False, "error": "Invalid credentials"}
    user = userFromToken(token)
    return {"ok": True, "token": token, "user": user}


@app.post("/api/logout")
def logoutEndpoint(user=Depends(getCurrentUser)):
    return {"ok": True}


@app.get("/api/me")
def meEndpoint(user=Depends(getCurrentUser)):
    return {"user": user}


@app.post("/api/retrieve")
def retrieveEndpoint(req: ChatRequest, user=Depends(getCurrentUser)):
    return {"chunks": retrieve(req.query, mode=req.mode, k=req.k, hops=req.hops, clearance=user['clearance'])}


def queryGraph(tx, search, entityType, limit):
    where = []
    params = {"limit": limit}
    if entityType:
        where.append("e.type = $entityType")
        params["entityType"] = entityType
    if search:
        where.append("(toLower(e.canonicalName) CONTAINS toLower($search) OR toLower(e.canonicalId) CONTAINS toLower($search))")
        params["search"] = search
    whereClause = ("WHERE " + " AND ".join(where)) if where else ""
    nodesRes = tx.run(
        f"""
        MATCH (e:Entity)
        {whereClause}
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(c:Chunk)
        WITH e, count(DISTINCT c) AS chunkCount
        RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type, chunkCount
        ORDER BY chunkCount DESC
        LIMIT $limit
        """,
        **params,
    )
    nodes = [dict(r) for r in nodesRes]
    nodeIds = [n["id"] for n in nodes]
    edgesRes = tx.run(
        """
        MATCH (s:Entity)-[r]->(o:Entity)
        WHERE s.canonicalId IN $ids AND o.canonicalId IN $ids AND type(r) <> 'MENTIONED_IN'
        RETURN s.canonicalId AS source, o.canonicalId AS target, type(r) AS predicate
        """,
        ids=nodeIds,
    )
    edges = [dict(r) for r in edgesRes]
    return nodes, edges


def querySeedGraph(tx, seed, hops, limit):
    nodesRes = tx.run(
        f"""
        MATCH (seed:Entity {{canonicalId: $seed}})
        OPTIONAL MATCH path = (seed)-[*1..{hops}]-(other:Entity)
        WHERE NONE(rel IN relationships(path) WHERE type(rel) = 'MENTIONED_IN')
        WITH collect(DISTINCT seed) + collect(DISTINCT other) AS allNodes
        UNWIND allNodes AS e
        WITH DISTINCT e WHERE e IS NOT NULL
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(c:Chunk)
        WITH e, count(DISTINCT c) AS chunkCount
        RETURN e.canonicalId AS id, e.canonicalName AS name, e.type AS type, chunkCount
        LIMIT $limit
        """,
        seed=seed,
        limit=limit,
    )
    nodes = [dict(r) for r in nodesRes]
    nodeIds = [n["id"] for n in nodes]
    edgesRes = tx.run(
        """
        MATCH (s:Entity)-[r]->(o:Entity)
        WHERE s.canonicalId IN $ids AND o.canonicalId IN $ids AND type(r) <> 'MENTIONED_IN'
        RETURN s.canonicalId AS source, o.canonicalId AS target, type(r) AS predicate
        """,
        ids=nodeIds,
    )
    edges = [dict(r) for r in edgesRes]
    return nodes, edges


@app.get("/api/graph")
def graphEndpoint(
    search: str = "",
    type: str = "",
    seed: str = "",
    hops: int = 1,
    limit: int = 200,
    user=Depends(getCurrentUser),
):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            if seed:
                nodes, edges = session.execute_read(querySeedGraph, seed, hops, limit)
            else:
                nodes, edges = session.execute_read(queryGraph, search, type, limit)
    return {
        "nodes": [
            {
                "data": {
                    "id": n["id"],
                    "label": (n["name"] or n["id"])[:40],
                    "name": n["name"],
                    "type": n["type"],
                    "chunkCount": n["chunkCount"],
                }
            }
            for n in nodes
        ],
        "edges": [
            {
                "data": {
                    "id": f"{e['source']}__{e['predicate']}__{e['target']}",
                    "source": e["source"],
                    "target": e["target"],
                    "label": e["predicate"],
                }
            }
            for e in edges
        ],
    }


@app.post("/api/chat")
def chatStream(req: ChatRequest, user=Depends(getCurrentUser)):
    chunks = retrieve(req.query, mode=req.mode, k=req.k, hops=req.hops, clearance=user['clearance'])

    def eventGen():
        yield "data: " + json.dumps({"type": "citations", "citations": chunks}) + "\n\n"
        yield from streamTokens(req.query, chunks, req.provider)
        yield "data: " + json.dumps({"type": "done"}) + "\n\n"

    return StreamingResponse(eventGen(), media_type="text/event-stream; charset=utf-8")


if os.path.isdir("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
