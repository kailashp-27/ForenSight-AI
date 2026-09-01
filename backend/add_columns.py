import asyncio
import aiomysql

async def run():
    conn = await aiomysql.connect(host='localhost', port=3306, user='root', password='Priya2711!', db='forensight')
    cur = await conn.cursor()
    
    try:
        await cur.execute('ALTER TABLE evidence ADD COLUMN transcription_status VARCHAR(50) DEFAULT "PENDING";')
    except Exception as e:
        print(e)
        
    try:
        await cur.execute('ALTER TABLE evidence ADD COLUMN transcript TEXT;')
    except Exception as e:
        print(e)
        
    await conn.commit()
    await cur.close()
    conn.close()

asyncio.run(run())
