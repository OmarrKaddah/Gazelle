import _bootstrap  # noqa: F401
import asyncio
import os
import uuid
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    role VARCHAR(100) NOT NULL,
    clearance VARCHAR(32) NOT NULL,
    "passwordHash" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    "userId" UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "tokenHash" VARCHAR(128) NOT NULL UNIQUE,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY,
    "userId" UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    "chatId" UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    "tokenCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_memory (
    id UUID PRIMARY KEY,
    "chatId" UUID NOT NULL UNIQUE REFERENCES chats(id) ON DELETE CASCADE,
    summary TEXT NOT NULL DEFAULT '',
    "extractedEntities" JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_memory (
    id UUID PRIMARY KEY,
    "userId" UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "memoryKey" VARCHAR(255) NOT NULL,
    "memoryValue" TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_memory_user_key UNIQUE ("userId", "memoryKey")
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY,
    "userId" UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(120) NOT NULL,
    "entityType" VARCHAR(64) NOT NULL,
    "entityId" VARCHAR(128) NOT NULL,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chats_user_updated ON chats ("userId", "updatedAt");
CREATE INDEX IF NOT EXISTS ix_messages_chat_created ON messages ("chatId", "createdAt");
CREATE INDEX IF NOT EXISTS ix_user_memory_user_updated ON user_memory ("userId", "updatedAt");
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_created ON audit_logs ("userId", "createdAt");
"""

SEED = [
    ("omar", "Admin", "restricted", "admin123"),
    ("sara", "Senior Compliance", "confidential", "compliance123"),
    ("ahmed", "Compliance Analyst", "internal", "staff123"),
    ("guest", "External", "public", "guest"),
]


async def main():
    url = os.environ['DATABASE_URL']
    engine = create_async_engine(
        url,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    async with engine.begin() as conn:
        for stmt in DDL.strip().split(";\n"):
            s = stmt.strip()
            if s:
                await conn.execute(text(s))
        for username, role, clearance, password in SEED:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            await conn.execute(
                text("""
                    INSERT INTO users (id, username, role, clearance, "passwordHash")
                    VALUES (:id, :u, :r, :c, :h)
                    ON CONFLICT (username) DO NOTHING
                """),
                {"id": uuid.uuid4(), "u": username, "r": role, "c": clearance, "h": pw_hash},
            )
    await engine.dispose()
    print("DB initialized. Logins:")
    for u, _, _, p in SEED:
        print(f"  {u} / {p}")


asyncio.run(main())
