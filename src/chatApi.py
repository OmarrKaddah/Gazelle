import asyncio
import json
import os
import subprocess
import sys
import uuid

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from neo4j import GraphDatabase
from retriever import retrieve, graphRetrieve
from localRetrieve import reloadLocalIndex
from auth import bearer, getCurrentUser, login, logout, userFromToken
from docAccess import LEVELS
from db.session import asyncSessionFactory, getDbSession, initDb
from db.repositories.chatRepo import (
    createChat, listChats, getChatById, deleteChat, createMessage, listMessages,
)
from db.repositories.memoryRepo import (
    upsertChatMemory, getChatMemory, listUserMemory, upsertUserMemory,
    loadUserMemoryForPrompt, loadRecentMessages,
)
from db.repositories.citationRepo import insertCitations
from db.repositories.auditRepo import logAudit
from memory.assembler import assembleMessages
from memory.summarizer import updateChatMemory
from memory.promoter import maybePromote
from config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    OLLAMA_URL, GROQ_URL, OLLAMA_CHAT_MODEL, GROQ_MODEL, GROQ_API_KEY,
    CHAT_DOMAIN,
)

PROVIDERS = {
    'ollama': {'url': OLLAMA_URL, 'model': OLLAMA_CHAT_MODEL, 'apiKey': None},
    'groq': {'url': GROQ_URL, 'model': GROQ_MODEL, 'apiKey': GROQ_API_KEY},
}


app = FastAPI(title="Gazelle API")


@app.on_event("startup")
async def onStartup():
    await initDb()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    chatId: str | None = None
    mode: str = "vector"
    k: int = 5
    hops: int = 1
    provider: str = "ollama"


class CreateChatRequest(BaseModel):
    title: str | None = None


class UpdateChatRequest(BaseModel):
    title: str


class UpsertChatMemoryRequest(BaseModel):
    summary: str
    extractedEntities: dict
    metadata: dict | None = None


class UpsertUserMemoryRequest(BaseModel):
    memoryValue: str
    confidence: float = 1.0
    metadata: dict | None = None


def buildContext(chunks):
    return "\n\n---\n\n".join(
        f"[{c['chunkId']} | section: {' > '.join(c.get('sectionPath') or [])} | pages: {c.get('pages')}]\n{c['text']}"
        for c in chunks
    )


COMPLIANCE_PROMPT = """You are Gazelle, a compliance assistant for Abu Dhabi Islamic Bank (ADIB).

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


# Open-domain framing for benchmark corpora (MuSiQue / 2Wiki Wikipedia passages). Same grounding
# discipline, no banking identity — so the UI vibe-check reflects the data actually loaded.
GENERAL_PROMPT = """You are a question-answering assistant grounded in a retrieved set of passages.

STRICT GROUNDING RULES — these override every other instinct:
1. Answer using ONLY the provided CONTEXT chunks. Do NOT use general knowledge, training data, common-sense inferences, or any external information.
2. Every factual claim in your answer MUST be tied to a specific source by including the chunkId in square brackets, e.g. [musique-0017]. A claim without a citation is forbidden.
3. If the CONTEXT does not contain enough information to answer the question, respond with exactly:
   "The provided context does not contain enough information to answer this question."
   Do NOT guess. Do NOT fall back on what you think the answer might be.
4. Do NOT add background, examples, definitions, or related facts that are not explicitly stated in the CONTEXT.
5. Prefer short direct quotes from the CONTEXT over paraphrase. Be concise.
6. If a question is partially covered, answer only the part the context supports and explicitly note what is missing.

When in doubt, refuse to answer rather than fabricate."""


SYSTEM_PROMPT = GENERAL_PROMPT if CHAT_DOMAIN == 'general' else COMPLIANCE_PROMPT


def buildPrompt(query, chunks):
    return (
        f"CONTEXT:\n{buildContext(chunks)}\n\n"
        "---\n\n"
        "Reminder: answer ONLY using the CONTEXT above. Cite [chunkId] for every claim. "
        "If the context is insufficient, refuse using the exact refusal sentence per the system rules.\n\n"
        f"QUESTION: {query}"
    )


async def streamTokens(query, chunks, userMemRows, chatSummary, recentTurns, provider='ollama'):
    if not chunks:
        print(
            f"[chatApi] No chunks to stream for query={query!r} provider={provider}",
            flush=True,
        )
        yield "data: " + json.dumps({"type": "token", "text": "No relevant context was retrieved for this query."}) + "\n\n"
        return
    cfg = PROVIDERS.get(provider) or PROVIDERS['ollama']
    headers = {"Authorization": f"Bearer {cfg['apiKey']}"} if cfg['apiKey'] else {}
    messages = assembleMessages(
        systemPrompt=SYSTEM_PROMPT,
        userMemRows=userMemRows,
        chatSummary=chatSummary,
        recentTurns=recentTurns,
        contextBlock=buildContext(chunks),
        question=query,
    )
    print(
        f"[chatApi] Streaming provider={provider} model={cfg['model']} chunks={len(chunks)} "
        f"userMem={len(userMemRows or [])} hasSummary={bool(chatSummary)} recent={len(recentTurns or [])}",
        flush=True,
    )
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            cfg['url'],
            headers=headers,
            json={
                "model": cfg['model'],
                "messages": messages,
                "temperature": 0,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for raw in response.aiter_lines():
                if not raw or not raw.startswith("data: "):
                    continue
                payload = raw[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {}).get("content", "")
                if delta:
                    yield "data: " + json.dumps({"type": "token", "text": delta}) + "\n\n"


def serializeChat(chat):
    return {
        "id": str(chat.id),
        "userId": str(chat.userId),
        "title": chat.title,
        "createdAt": chat.createdAt.isoformat(),
        "updatedAt": chat.updatedAt.isoformat(),
    }


def serializeMessage(message):
    return {
        "id": str(message.id),
        "chatId": str(message.chatId),
        "role": message.role,
        "text": message.content,
        "tokenCount": message.tokenCount,
        "createdAt": message.createdAt.isoformat(),
    }


def serializeUserMemory(row):
    return {
        "id": str(row.id),
        "memoryKey": row.memoryKey,
        "memoryValue": row.memoryValue,
        "confidence": row.confidence,
        "metadata": row.metadataJson,
        "updatedAt": row.updatedAt.isoformat(),
    }


def serializeChatMemory(row):
    if not row:
        return None
    return {
        "id": str(row.id),
        "chatId": str(row.chatId),
        "summary": row.summary,
        "extractedEntities": row.extractedEntities,
        "metadata": row.metadataJson,
        "updatedAt": row.updatedAt.isoformat(),
    }


def countTokens(text: str):
    return len(text.split())


def buildChatSummary(userQuery: str, assistantAnswer: str):
    userPart = userQuery.strip()[:500]
    assistantPart = assistantAnswer.strip()[:1200]
    return f"User: {userPart}\nAssistant: {assistantPart}"


@app.get("/api/info")
def infoEndpoint():
    return {
        "providers": {
            "ollama": {"model": OLLAMA_CHAT_MODEL, "available": True},
            "groq": {"model": GROQ_MODEL, "available": bool(GROQ_API_KEY)},
        },
        "levels": LEVELS,
    }


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def loginEndpoint(req: LoginRequest, session: AsyncSession = Depends(getDbSession)):
    token = await login(req.username, req.password, session)
    if not token:
        return {"ok": False, "error": "Invalid credentials"}
    user = await userFromToken(token, session)
    return {"ok": True, "token": token, "user": user}


@app.post("/api/logout")
async def logoutEndpoint(
    creds=Depends(bearer),
    session: AsyncSession = Depends(getDbSession),
):
    if creds:
        await logout(creds.credentials, session)
    return {"ok": True}


@app.get("/api/me")
async def meEndpoint(user=Depends(getCurrentUser)):
    return {"user": user}


@app.post("/api/retrieve")
def retrieveEndpoint(req: ChatRequest, user=Depends(getCurrentUser)):
    return {"chunks": retrieve(req.query, mode=req.mode, k=req.k, clearance=user['clearance'])}


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
async def graphEndpoint(
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


async def chatEventGen(query, chunks, userMemRows, chatSummary, recentTurns, chatId, userId, req, provenance=None):
    yield "data: " + json.dumps({"type": "citations", "citations": chunks}) + "\n\n"
    if provenance:
        yield "data: " + json.dumps({"type": "graph", **provenance}) + "\n\n"
    parts = []
    async for event in streamTokens(query, chunks, userMemRows, chatSummary, recentTurns, req.provider):
        payload = json.loads(event[6:].strip())
        if payload.get("type") == "token":
            parts.append(payload.get("text", ""))
        yield event
    assistantText = "".join(parts)
    chatMetadata = {"mode": req.mode, "provider": req.provider, "k": req.k, "hops": req.hops}
    async with asyncSessionFactory() as session:
        msg = await createMessage(session, chatId, "assistant", assistantText, countTokens(assistantText))
        await insertCitations(session, msg.id, chunks)
        existing = await getChatMemory(session, chatId)
        if not existing:
            await upsertChatMemory(session, chatId, "", {}, chatMetadata)
        else:
            existing.metadataJson = chatMetadata
            await session.flush()
        await logAudit(session, userId, "message.create", "chat", str(chatId))
        await session.commit()
        latestMessageId = msg.id
    asyncio.create_task(updateChatMemory(chatId, latestMessageId))
    asyncio.create_task(maybePromote(userId, chatId, query))
    yield "data: " + json.dumps({"type": "done", "chatId": str(chatId)}) + "\n\n"


@app.post("/api/chat")
async def chatStream(req: ChatRequest, user=Depends(getCurrentUser)):
    if req.mode == 'graph':
        result = await asyncio.to_thread(graphRetrieve, req.query, req.k, user['clearance'])
        chunks = result['chunks']
        provenance = {'seeds': result['seeds'], 'pathEdges': result['pathEdges']}
    else:
        chunks = await asyncio.to_thread(retrieve, req.query, mode=req.mode, k=req.k, clearance=user['clearance'])
        provenance = None
    userId = uuid.UUID(user["id"])
    async with asyncSessionFactory() as session:
        if req.chatId:
            chatId = uuid.UUID(req.chatId)
        else:
            chat = await createChat(session, userId, req.query[:60])
            await session.commit()
            chatId = chat.id
        await createMessage(session, chatId, "user", req.query, countTokens(req.query))
        await logAudit(session, userId, "message.create", "chat", str(chatId))
        await session.commit()
        userMemRows = await loadUserMemoryForPrompt(session, userId)
        chatMem = await getChatMemory(session, chatId)
        chatSummary = chatMem.summary if chatMem else ""
        recentTurns = await loadRecentMessages(session, chatId, n=4)
    return StreamingResponse(
        chatEventGen(req.query, chunks, userMemRows, chatSummary, recentTurns, chatId, userId, req, provenance),
        media_type="text/event-stream; charset=utf-8",
    )


@app.get("/api/chats")
async def listChatsEndpoint(
    limit: int = 30,
    offset: int = 0,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    rows = await listChats(session, uuid.UUID(user["id"]), limit, offset)
    return {"chats": [serializeChat(row) for row in rows]}


@app.post("/api/chats")
async def createChatEndpoint(
    req: CreateChatRequest,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await createChat(session, uuid.UUID(user["id"]), req.title or "New conversation")
    await logAudit(session, uuid.UUID(user["id"]), "chat.create", "chat", str(row.id))
    await session.commit()
    await session.refresh(row)
    messages = await listMessages(session, row.id, 200, 0)
    return {"chat": {**serializeChat(row), "messages": [serializeMessage(msg) for msg in messages]}}


@app.get("/api/chats/{chatId}")
async def getChatEndpoint(
    chatId: str,
    limit: int = 200,
    offset: int = 0,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await getChatById(session, uuid.UUID(user["id"]), uuid.UUID(chatId))
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = await listMessages(session, row.id, limit, offset)
    return {"chat": {**serializeChat(row), "messages": [serializeMessage(msg) for msg in messages]}}


@app.patch("/api/chats/{chatId}")
async def updateChatEndpoint(
    chatId: str,
    req: UpdateChatRequest,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await getChatById(session, uuid.UUID(user["id"]), uuid.UUID(chatId))
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    row.title = req.title
    await logAudit(session, uuid.UUID(user["id"]), "chat.update", "chat", str(row.id))
    await session.commit()
    await session.refresh(row)
    return {"chat": serializeChat(row)}


@app.delete("/api/chats/{chatId}")
async def deleteChatEndpoint(
    chatId: str,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    await deleteChat(session, uuid.UUID(user["id"]), uuid.UUID(chatId))
    await logAudit(session, uuid.UUID(user["id"]), "chat.delete", "chat", chatId)
    await session.commit()
    return {"ok": True}


@app.get("/api/chats/{chatId}/memory")
async def getChatMemoryEndpoint(
    chatId: str,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await getChatById(session, uuid.UUID(user["id"]), uuid.UUID(chatId))
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    memory = await getChatMemory(session, row.id)
    return {"memory": serializeChatMemory(memory)}


@app.put("/api/chats/{chatId}/memory")
async def putChatMemoryEndpoint(
    chatId: str,
    req: UpsertChatMemoryRequest,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await getChatById(session, uuid.UUID(user["id"]), uuid.UUID(chatId))
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    memory = await upsertChatMemory(session, row.id, req.summary, req.extractedEntities, req.metadata)
    await logAudit(session, uuid.UUID(user["id"]), "chat.memory.upsert", "chat", chatId)
    await session.commit()
    await session.refresh(memory)
    return {"memory": serializeChatMemory(memory)}


@app.get("/api/memory/user")
async def getUserMemoryEndpoint(
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    rows = await listUserMemory(session, uuid.UUID(user["id"]))
    return {"memory": [serializeUserMemory(row) for row in rows]}


@app.put("/api/memory/user/{memoryKey}")
async def putUserMemoryEndpoint(
    memoryKey: str,
    req: UpsertUserMemoryRequest,
    user=Depends(getCurrentUser),
    session: AsyncSession = Depends(getDbSession),
):
    row = await upsertUserMemory(
        session,
        uuid.UUID(user["id"]),
        memoryKey,
        req.memoryValue,
        req.confidence,
        req.metadata,
    )
    await logAudit(session, uuid.UUID(user["id"]), "user.memory.upsert", "user", user["id"])
    await session.commit()
    await session.refresh(row)
    return {"memory": serializeUserMemory(row)}


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# stage id -> runner script. 'all' is the end-to-end orchestrator (branches on GRAPH_ROUTE).
PIPELINE_STAGES = {
    "ocr": "runners/runOcr.py",
    "parser": "runners/runParser.py",
    "chunker": "runners/runChunker.py",
    "embed": "runners/runEmbed.py",
    "gliner": "runners/runGliner.py",
    "kgBuild": "runners/runKgBuild.py",
    "graphExtract": "runners/runGraphExtract.py",
    "graphBuild": "runners/runGraphBuild.py",
    "entityEmbed": "runners/runEntityEmbed.py",
    "all": "runners/runPipeline.py",
}

# stage id -> (directory, glob) used to count how many docs have reached that stage.
PIPELINE_OUTPUTS = {
    "ocr": ("Doc_Out", "*.md"),
    "parser": ("parsed", "*.json"),
    "chunker": ("chunks", "*.json"),
    "gliner": ("extractions", "*_entities.json"),
    "graphExtract": ("extractions", "*_graph.json"),
}


class PipelineRunRequest(BaseModel):
    stage: str
    route: str = "2"
    ner: str = "gliner"
    chunker: str = "semantic"
    backend: str = "openrouter"
    workers: int = 12


def pipelineEnv(req: PipelineRunRequest):
    env = dict(os.environ)
    env.update({
        "GRAPH_ROUTE": req.route,
        "NER_STRATEGY": req.ner,
        "CHUNKER_TYPE": req.chunker,
        "GRAPH_EXTRACT_BACKEND": req.backend,
        "GRAPH_EXTRACT_WORKERS": str(req.workers),
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
    })
    return env


@app.get("/api/pipeline/status")
async def pipelineStatus(user=Depends(getCurrentUser)):
    counts = {}
    for stage, (folder, pattern) in PIPELINE_OUTPUTS.items():
        d = os.path.join(REPO_ROOT, folder)
        counts[stage] = len([f for f in os.listdir(d) if f.endswith(pattern.lstrip("*"))]) if os.path.isdir(d) else 0
    return {
        "counts": counts,
        "config": {
            "route": os.environ.get("GRAPH_ROUTE", "2"),
            "ner": os.environ.get("NER_STRATEGY", "gliner"),
            "chunker": os.environ.get("CHUNKER_TYPE", "semantic"),
            "backend": os.environ.get("GRAPH_EXTRACT_BACKEND", "openrouter"),
            "workers": int(os.environ.get("GRAPH_EXTRACT_WORKERS", "12")),
        },
    }


@app.post("/api/pipeline/run")
def pipelineRun(req: PipelineRunRequest, user=Depends(getCurrentUser)):
    if req.stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {req.stage}")
    script = PIPELINE_STAGES[req.stage]

    def gen():
        yield "data: " + json.dumps({"line": f"$ python {script}  (route={req.route} ner={req.ner} chunker={req.chunker})"}) + "\n\n"
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=REPO_ROOT,
            env=pipelineEnv(req),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        for line in proc.stdout:
            yield "data: " + json.dumps({"line": line.rstrip("\n")}) + "\n\n"
        proc.wait()
        yield "data: " + json.dumps({"done": True, "code": proc.returncode}) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8")


@app.post("/api/pipeline/reloadIndex")
def pipelineReloadIndex(user=Depends(getCurrentUser)):
    idx = reloadLocalIndex()
    return {"entities": len(idx.idxToId), "chunks": len(idx.chunkDoc)}


if os.path.isdir("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
