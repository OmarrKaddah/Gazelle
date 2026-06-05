import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatMemory, Message, UserMemory


PROMPT_CATEGORIES = ("preference", "instruction")


async def upsertChatMemory(session: AsyncSession, chatId: uuid.UUID, summary: str, extractedEntities: dict, metadata: dict):
    result = await session.execute(select(ChatMemory).where(ChatMemory.chatId == chatId))
    row = result.scalar_one_or_none()
    if row:
        row.summary = summary
        row.extractedEntities = extractedEntities
        row.metadataJson = metadata
        await session.flush()
        return row
    row = ChatMemory(
        chatId=chatId,
        summary=summary,
        extractedEntities=extractedEntities,
        metadataJson=metadata,
    )
    session.add(row)
    await session.flush()
    return row


async def getChatMemory(session: AsyncSession, chatId: uuid.UUID):
    result = await session.execute(select(ChatMemory).where(ChatMemory.chatId == chatId))
    return result.scalar_one_or_none()


async def listUserMemory(session: AsyncSession, userId: uuid.UUID):
    result = await session.execute(
        select(UserMemory)
        .where(UserMemory.userId == userId)
        .order_by(UserMemory.updatedAt.desc())
    )
    return result.scalars().all()


async def loadUserMemoryForPrompt(session: AsyncSession, userId: uuid.UUID, limit: int = 5):
    result = await session.execute(
        select(UserMemory)
        .where(UserMemory.userId == userId, UserMemory.category.in_(PROMPT_CATEGORIES))
        .order_by(UserMemory.confidence.desc(), UserMemory.updatedAt.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def loadRecentMessages(session: AsyncSession, chatId: uuid.UUID, n: int = 4):
    result = await session.execute(
        select(Message)
        .where(Message.chatId == chatId)
        .order_by(desc(Message.createdAt))
        .limit(n)
    )
    rows = result.scalars().all()
    return list(reversed(rows))


async def upsertUserMemory(session: AsyncSession, userId: uuid.UUID, memoryKey: str, memoryValue: str, confidence: float, metadata: dict, category: str = "preference", source: str = "explicit"):
    result = await session.execute(
        select(UserMemory).where(
            UserMemory.userId == userId,
            UserMemory.category == category,
            UserMemory.memoryKey == memoryKey,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.memoryValue = memoryValue
        row.confidence = confidence
        row.metadataJson = metadata
        row.source = source
        await session.flush()
        return row
    row = UserMemory(
        userId=userId,
        category=category,
        memoryKey=memoryKey,
        memoryValue=memoryValue,
        source=source,
        confidence=confidence,
        metadataJson=metadata,
    )
    session.add(row)
    await session.flush()
    return row
