import asyncio
from backend.database.db import get_db, init_db

async def run():
    await init_db()
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM cases LIMIT 1")
        case = await row.fetchone()
        print("case:", case)
        if case:
            ev_cursor = await db.execute("SELECT * FROM evidence WHERE case_id = %s", (case['id'],))
            evidence = await ev_cursor.fetchall()
            print("evidence:", evidence)
    except Exception as e:
        print("Error:", e)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(run())
