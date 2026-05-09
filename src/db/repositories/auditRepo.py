from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog


async def logAudit(session: AsyncSession, userId, action: str, entityType: str, entityId: str):
    row = AuditLog(userId=userId, action=action, entityType=entityType, entityId=entityId)
    session.add(row)
    await session.flush()
    return row
