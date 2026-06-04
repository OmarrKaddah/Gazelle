import _bootstrap  # noqa: F401
import asyncio

from sqlalchemy import select

from db.session import DATABASE_URL, engine, asyncSessionFactory
from db.models import User


async def main():
    async with engine.connect() as conn:
        await conn.exec_driver_sql("SELECT 1")
    async with asyncSessionFactory() as session:
        users = (await session.execute(select(User.username))).scalars().all()
    print(f"DB OK: {DATABASE_URL}")
    print(f"users: {users}")


asyncio.run(main())
