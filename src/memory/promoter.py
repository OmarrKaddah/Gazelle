import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserMemory
from db.session import asyncSessionFactory


PATTERNS = [
    (re.compile(r"always answer in (\w+)", re.IGNORECASE), "preference", "language"),
    (re.compile(r"answer in (arabic|english|french|spanish)", re.IGNORECASE), "preference", "language"),
    (re.compile(r"prefer (concise|detailed|brief|verbose) answers?", re.IGNORECASE), "preference", "verbosity"),
    (re.compile(r"my (?:role|division|department) is ([^.\n]+)", re.IGNORECASE), "profile", "role"),
    (re.compile(r"always include (page numbers|article numbers|citations|sources)", re.IGNORECASE), "instruction", "always_include"),
    (re.compile(r"never (mention|include|cite) ([^.\n]+)", re.IGNORECASE), "instruction", "never_include"),
]

PII_RX = re.compile(r"\b\d{10,}\b")


def containsPii(text):
    return bool(PII_RX.search(text))


async def upsertMemory(session: AsyncSession, userId, category, key, value, chatId):
    res = await session.execute(
        select(UserMemory).where(
            UserMemory.userId == userId,
            UserMemory.category == category,
            UserMemory.memoryKey == key,
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        if existing.source == "explicit":
            return
        existing.memoryValue = value
        existing.confidence = min(0.95, existing.confidence + 0.05)
        existing.evidenceChatId = chatId
        return
    session.add(UserMemory(
        userId=userId, category=category, memoryKey=key, memoryValue=value,
        source="inferred", confidence=0.7, evidenceChatId=chatId,
    ))


async def maybePromote(userId: uuid.UUID, chatId: uuid.UUID, userText: str):
    if not userText or containsPii(userText):
        return
    matches = []
    for rx, category, key in PATTERNS:
        m = rx.search(userText)
        if m:
            matches.append((category, key, m.group(1).strip()))
    if not matches:
        return
    async with asyncSessionFactory() as session:
        for category, key, value in matches:
            await upsertMemory(session, userId, category, key, value, chatId)
        await session.commit()
