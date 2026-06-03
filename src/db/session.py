import os

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 - registers all models on Base.metadata
from db.base import Base
from db.models import User

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./gazelle.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(DATABASE_URL)
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


SEED_USERS = [
    ("omar", "Admin", "restricted", "admin123"),
    ("sara", "Senior Compliance", "confidential", "compliance123"),
    ("ahmed", "Compliance Analyst", "internal", "staff123"),
    ("guest", "External", "public", "guest"),
]


async def initDb():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with asyncSessionFactory() as session:
        existing = await session.execute(select(User.id).limit(1))
        if existing.first():
            return
        for username, role, clearance, password in SEED_USERS:
            passwordHash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            session.add(User(username=username, role=role, clearance=clearance, passwordHash=passwordHash))
        await session.commit()
