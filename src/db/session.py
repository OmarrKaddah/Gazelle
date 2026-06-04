import os

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 - registers all models on Base.metadata
from db.base import Base
from db.models import User

load_dotenv()

# Airgapped build: SQLite only — no Postgres, no asyncpg (nothing that can't be carried on a USB).
# Any non-sqlite DATABASE_URL left over in .env is ignored so we never try to reach a Postgres server.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./gazelle.db")
if not DATABASE_URL.startswith("sqlite"):
    print(f"[db] ignoring non-sqlite DATABASE_URL ({DATABASE_URL.split('://', 1)[0]}://…); this build is SQLite-only", flush=True)
    DATABASE_URL = "sqlite+aiosqlite:///./gazelle.db"

engine = create_async_engine(DATABASE_URL)
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
