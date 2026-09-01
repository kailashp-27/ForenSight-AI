import asyncio
from backend.database.db import init_db
from backend.seed_mock import seed

async def run():
    await init_db()
    await seed()

asyncio.run(run())
