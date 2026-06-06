import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import OLLAMA_URL, OLLAMA_CHAT_MODEL
from db.models import ChatMemory, Message
from db.session import asyncSessionFactory
from memory.assembler import countTokens


SUMMARIZER_PROMPT = (
    "You maintain a running summary of an Arabic banking compliance chat. "
    "Update the PREVIOUS SUMMARY using the NEW EXCHANGES. Keep: facts the user asked about, "
    "decisions made, constraints stated, document or article references. "
    "Drop: pleasantries, restatements, model self-references. "
    "REDACT: any sequence of 10+ digits (account numbers, NIDs), bank card numbers, secret tokens. "
    "Output plain prose under 300 tokens. No markdown, no JSON."
)

DEBOUNCE_TURNS = 6
DEBOUNCE_TOKENS = 1000


async def loadMem(session: AsyncSession, chatId: uuid.UUID):
    res = await session.execute(select(ChatMemory).where(ChatMemory.chatId == chatId))
    return res.scalar_one_or_none()


async def loadMessagesSince(session: AsyncSession, chatId: uuid.UUID, sinceId):
    q = select(Message).where(Message.chatId == chatId).order_by(Message.createdAt.asc())
    res = await session.execute(q)
    rows = res.scalars().all()
    if sinceId is None:
        return rows
    out, seen = [], False
    for r in rows:
        if seen:
            out.append(r)
        if r.id == sinceId:
            seen = True
    return out


def buildSummarizerMessages(previous, newMessages):
    body = ["PREVIOUS SUMMARY:", previous or "(none)", "", "NEW EXCHANGES:"]
    for m in newMessages:
        role = "USER" if m.role == "user" else "ASSISTANT"
        body.append(f"{role}: {m.content}")
    body.append("\nProduce the updated summary now.")
    return [
        {"role": "system", "content": SUMMARIZER_PROMPT},
        {"role": "user", "content": "\n".join(body)},
    ]


async def callLlmSummarizer(previous, newMessages):
    payload = {
        "model": OLLAMA_CHAT_MODEL,
        "messages": buildSummarizerMessages(previous, newMessages),
        "temperature": 0,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


async def updateChatMemory(chatId: uuid.UUID, latestMessageId: uuid.UUID):
    async with asyncSessionFactory() as session:
        mem = await loadMem(session, chatId)
        previous = mem.summary if mem else ""
        sinceId = mem.lastSummarizedMessageId if mem else None
        newMessages = await loadMessagesSince(session, chatId, sinceId)
        if not newMessages:
            return
        total = sum(countTokens(m.content) for m in newMessages)
        if len(newMessages) < DEBOUNCE_TURNS and total < DEBOUNCE_TOKENS:
            return
        newSummary = await callLlmSummarizer(previous, newMessages)
        if mem is None:
            mem = ChatMemory(chatId=chatId, summary=newSummary)
            session.add(mem)
        else:
            mem.summary = newSummary
        mem.summaryTokens = countTokens(newSummary)
        mem.lastSummarizedMessageId = latestMessageId
        await session.commit()
