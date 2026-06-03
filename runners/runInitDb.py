import _bootstrap  # noqa: F401 - adds src to path, chdir repo root
import asyncio

from db.session import SEED_USERS, initDb


asyncio.run(initDb())
print("DB initialized. Logins:")
for username, _, _, password in SEED_USERS:
    print(f"  {username} / {password}")
