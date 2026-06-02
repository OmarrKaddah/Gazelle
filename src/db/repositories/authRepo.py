from __future__ import annotations

from config import MOCK_RUNTIME

if MOCK_RUNTIME:
    from mockRuntime import getMockUserByToken, getMockUserByUsername
else:
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import User, UserSession


async def getUserByUsername(session: AsyncSession, username: str):
    if MOCK_RUNTIME:
        return getMockUserByUsername(username)
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def createSession(session: AsyncSession, userId, tokenHash: str):
    if MOCK_RUNTIME:
        return None
    row = UserSession(userId=userId, tokenHash=tokenHash)
    session.add(row)
    await session.flush()
    return row


async def deleteSessionByTokenHash(session: AsyncSession, tokenHash: str):
    if MOCK_RUNTIME:
        return None
    await session.execute(delete(UserSession).where(UserSession.tokenHash == tokenHash))


async def getUserByTokenHash(session: AsyncSession, tokenHash: str):
    if MOCK_RUNTIME:
        return getMockUserByToken(tokenHash)
    result = await session.execute(
        select(User)
        .join(UserSession, UserSession.userId == User.id)
        .where(UserSession.tokenHash == tokenHash)
    )
    return result.scalar_one_or_none()
