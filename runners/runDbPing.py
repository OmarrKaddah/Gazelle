import _bootstrap  # noqa: F401
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ['PG_HOST']
PORT = int(os.environ.get('PG_PORT', '5432'))
USER = os.environ['PG_USER']
PASSWORD = os.environ['PG_PASSWORD']
DB = os.environ['PG_DB']


async def tryConnect(label, **kwargs):
    print(f"\n--- {label} ---")
    try:
        conn = await asyncpg.connect(
            host=HOST, port=PORT, user=USER, password=PASSWORD, database=DB,
            timeout=15, **kwargs,
        )
        version = await conn.fetchval("SELECT version()")
        print(f"OK: {version}")
        await conn.close()
    except Exception as e:
        print(f"FAIL ({type(e).__name__}): {e}")


async def main():
    await tryConnect("ssl=disable", ssl=False)
    await tryConnect("ssl=prefer", ssl='prefer')
    await tryConnect("ssl=require", ssl='require')


asyncio.run(main())
