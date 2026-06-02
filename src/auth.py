from __future__ import annotations

import hashlib
import secrets

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from config import MOCK_RUNTIME
from db.session import getDbSession

if MOCK_RUNTIME:
    from mockRuntime import getMockUser, issueMockToken, revokeMockToken
else:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.repositories.authRepo import createSession, deleteSessionByTokenHash, getUserByTokenHash, getUserByUsername


bearer = HTTPBearer(auto_error=False)


def hashToken(token: str):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verifyPassword(password: str, passwordHash: str):
    return bcrypt.checkpw(password.encode("utf-8"), passwordHash.encode("utf-8"))


async def login(username: str, password: str, session: AsyncSession):
    if MOCK_RUNTIME:
        return issueMockToken()
    user = await getUserByUsername(session, username)
    if not user:
        return None
    if not verifyPassword(password, user.passwordHash):
        return None
    token = secrets.token_urlsafe(32)
    await createSession(session, user.id, hashToken(token))
    await session.commit()
    return token


async def logout(token: str, session: AsyncSession):
    if MOCK_RUNTIME:
        revokeMockToken(token)
        return
    await deleteSessionByTokenHash(session, hashToken(token))
    await session.commit()


async def userFromToken(token: str, session: AsyncSession):
    if MOCK_RUNTIME:
        return getMockUser()
    user = await getUserByTokenHash(session, hashToken(token))
    if not user:
        return None
    return {
        "id": str(user.id),
        "username": user.username,
        "name": user.username,
        "role": user.role,
        "clearance": user.clearance,
    }


async def getCurrentUser(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    session: AsyncSession = Depends(getDbSession),
):
    if MOCK_RUNTIME:
        return getMockUser()
    if not creds:
        raise HTTPException(status_code=401, detail="Missing credentials")
    user = await userFromToken(creds.credentials, session)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
