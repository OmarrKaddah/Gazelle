import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

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
