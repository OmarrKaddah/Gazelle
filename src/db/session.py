import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL, MOCK_RUNTIME
from mockRuntime import createMockSession

load_dotenv()

if MOCK_RUNTIME:
    engine = None

    def asyncSessionFactory():
        return createMockSession()


    async def getDbSession():
        async with createMockSession() as session:
            yield session
else:
    engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
    )

    asyncSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


    async def getDbSession():
        async with asyncSessionFactory() as session:
            yield session
