import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Chat, Message


async def createChat(session: AsyncSession, userId: uuid.UUID, title: str):
    row = Chat(userId=userId, title=title)
    session.add(row)
    await session.flush()
    return row


async def listChats(session: AsyncSession, userId: uuid.UUID, limit: int, offset: int):
    result = await session.execute(
        select(Chat)
        .where(Chat.userId == userId)
        .order_by(Chat.updatedAt.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def getChatById(session: AsyncSession, userId: uuid.UUID, chatId: uuid.UUID):
    result = await session.execute(
        select(Chat).where(Chat.id == chatId, Chat.userId == userId)
    )
    return result.scalar_one_or_none()


async def deleteChat(session: AsyncSession, userId: uuid.UUID, chatId: uuid.UUID):
    await session.execute(delete(Chat).where(Chat.id == chatId, Chat.userId == userId))


async def createMessage(session: AsyncSession, chatId: uuid.UUID, role: str, content: str, tokenCount: int):
    row = Message(chatId=chatId, role=role, content=content, tokenCount=tokenCount)
    session.add(row)
    chat = await session.get(Chat, chatId)
    if chat:
        chat.updatedAt = datetime.now(timezone.utc)
    await session.flush()
    return row


async def listMessages(session: AsyncSession, chatId: uuid.UUID, limit: int, offset: int):
    result = await session.execute(
        select(Message)
        .where(Message.chatId == chatId)
        .order_by(Message.createdAt.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
