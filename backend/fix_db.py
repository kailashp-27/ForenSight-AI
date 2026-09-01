import asyncio
import aiomysql

async def fix():
    conn = await aiomysql.connect(host='localhost', port=3306, user='root', password='Priya2711!', db='forensight')
    cur = await conn.cursor()
    # Disable foreign key checks to drop tables
    await cur.execute('SET FOREIGN_KEY_CHECKS = 0;')
    await cur.execute('DROP TABLE IF EXISTS audit_logs;')
    await cur.execute('DROP TABLE IF EXISTS text_chunks;')
    await cur.execute('DROP TABLE IF EXISTS detections;')
    await cur.execute('DROP TABLE IF EXISTS evidence;')
    await cur.execute('DROP TABLE IF EXISTS cases;')
    await cur.execute('DROP TABLE IF EXISTS users;')
    await cur.execute('SET FOREIGN_KEY_CHECKS = 1;')
    await conn.commit()
    await cur.close()
    conn.close()

asyncio.run(fix())
