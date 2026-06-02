from __future__ import annotations

import uuid

from config import MOCK_RUNTIME

if MOCK_RUNTIME:
    from mockRuntime import getMockChatMemory, listMockUserMemory, upsertMockChatMemory, upsertMockUserMemory
else:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import ChatMemory, UserMemory


async def upsertChatMemory(session: AsyncSession, chatId: uuid.UUID, summary: str, extractedEntities: dict, metadata: dict):
    if MOCK_RUNTIME:
        return upsertMockChatMemory(chatId, summary, extractedEntities, metadata)
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
    if MOCK_RUNTIME:
        return getMockChatMemory(chatId)
    result = await session.execute(select(ChatMemory).where(ChatMemory.chatId == chatId))
    return result.scalar_one_or_none()


async def listUserMemory(session: AsyncSession, userId: uuid.UUID):
    if MOCK_RUNTIME:
        return listMockUserMemory(userId)
    result = await session.execute(
        select(UserMemory)
        .where(UserMemory.userId == userId)
        .order_by(UserMemory.updatedAt.desc())
    )
    return result.scalars().all()


async def upsertUserMemory(session: AsyncSession, userId: uuid.UUID, memoryKey: str, memoryValue: str, confidence: float, metadata: dict):
    if MOCK_RUNTIME:
        return upsertMockUserMemory(userId, memoryKey, memoryValue, confidence, metadata)
    result = await session.execute(
        select(UserMemory).where(UserMemory.userId == userId, UserMemory.memoryKey == memoryKey)
    )
    row = result.scalar_one_or_none()
    if row:
        row.memoryValue = memoryValue
        row.confidence = confidence
        row.metadataJson = metadata
        await session.flush()
        return row
    row = UserMemory(
        userId=userId,
        memoryKey=memoryKey,
        memoryValue=memoryValue,
        confidence=confidence,
        metadataJson=metadata,
    )
    session.add(row)
    await session.flush()
    return row
