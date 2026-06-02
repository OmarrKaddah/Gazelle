import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MessageCitation


async def insertCitations(session: AsyncSession, messageId: uuid.UUID, chunks):
    for i, c in enumerate(chunks):
        session.add(MessageCitation(
            messageId=messageId,
            chunkId=c.get("chunkId", ""),
            docName=c.get("docName", ""),
            score=c.get("score"),
            rank=i + 1,
        ))
    await session.flush()


async def listForMessage(session: AsyncSession, messageId: uuid.UUID):
    result = await session.execute(
        select(MessageCitation)
        .where(MessageCitation.messageId == messageId)
        .order_by(MessageCitation.rank.asc())
    )
    return result.scalars().all()
