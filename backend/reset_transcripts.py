"""
backend/reset_transcripts.py
──────────────────────────────
Deletes all existing mock text_chunks so that real Whisper output can replace them.
Also resets transcription_status back to 'PENDING' on all audio/video evidence.
"""
import asyncio
import aiomysql

async def run():
    conn = await aiomysql.connect(
        host='localhost', port=3306,
        user='root', password='Priya2711!', db='forensight'
    )
    cur = await conn.cursor()

    # Delete all existing text chunks (mock data)
    await cur.execute("DELETE FROM text_chunks WHERE source_type = 'whisper'")
    deleted = cur.rowcount
    print(f"Deleted {deleted} mock text chunks.")

    # Reset transcription status on audio/video evidence back to PENDING
    await cur.execute(
        "UPDATE evidence SET transcription_status = 'PENDING', transcript = NULL WHERE file_type IN ('AUDIO', 'VIDEO')"
    )
    reset = cur.rowcount
    print(f"Reset transcription_status on {reset} audio/video evidence records.")

    await conn.commit()
    await cur.close()
    conn.close()
    print("Done. Re-upload your audio files to trigger real Whisper transcription.")

asyncio.run(run())
