import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from dotenv import load_dotenv

load_dotenv()


# Derive an admin connection (to the default 'postgres' database) and the
# target database name from the app's DATABASE_URL, so this needs no psql and
# no separate config.
def parseTarget():
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    parts = urlsplit(url)
    dbName = parts.path.lstrip("/")
    adminUrl = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    return adminUrl, dbName


async def createDatabase():
    adminUrl, dbName = parseTarget()
    conn = await asyncpg.connect(adminUrl)
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbName)
    if exists:
        print(f"database '{dbName}' already exists")
    else:
        await conn.execute(f'CREATE DATABASE "{dbName}"')
        print(f"created database '{dbName}'")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(createDatabase())
