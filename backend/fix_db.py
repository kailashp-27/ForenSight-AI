import asyncio
from backend.database.db import get_db

async def update_dates():
    db = await get_db()
    try:
        # Get the case
        await db.execute('SELECT id, created_at FROM cases WHERE case_number = \'CASE-2026-001\'')
        row = await db.cursor.fetchone()
        if not row:
            print('Case not found')
            return
        case_id = row['id']
        
        # Make case created_at Aug 1 2026
        await db.execute('UPDATE cases SET created_at = \'2026-08-01 10:00:00\' WHERE id = %s', (case_id,))
        
        # Get evidence
        await db.execute('SELECT id, file_name FROM evidence WHERE case_id = %s', (case_id,))
        evidence = await db.cursor.fetchall()
        
        # Update evidence dates, spreading them across August/Sept
        dates = ['2026-08-10 14:30:00', '2026-08-25 09:15:00', '2026-09-05 11:20:00', '2026-09-14 16:45:00']
        for i, ev in enumerate(evidence):
            date = dates[i % len(dates)]
            await db.execute('UPDATE evidence SET uploaded_at = %s WHERE id = %s', (date, ev['id']))
            
        # Get detections
        await db.execute('SELECT d.id FROM detections d JOIN evidence e ON d.evidence_id = e.id WHERE e.case_id = %s', (case_id,))
        detections = await db.cursor.fetchall()
        for i, det in enumerate(detections):
            date = dates[(i + 2) % len(dates)]
            await db.execute('UPDATE detections SET created_at = %s WHERE id = %s', (date, det['id']))
            
        await db.commit()
        print('Dates updated successfully in database!')
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(update_dates())
