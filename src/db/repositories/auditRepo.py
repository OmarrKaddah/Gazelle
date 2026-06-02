from __future__ import annotations

from config import MOCK_RUNTIME

if MOCK_RUNTIME:
    from mockRuntime import logMockAudit
else:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import AuditLog


async def logAudit(session: AsyncSession, userId, action: str, entityType: str, entityId: str):
    if MOCK_RUNTIME:
        return logMockAudit(userId, action, entityType, entityId)
    row = AuditLog(userId=userId, action=action, entityType=entityType, entityId=entityId)
    session.add(row)
    await session.flush()
    return row
