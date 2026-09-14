import pymysql

def update_dates():
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='Priya2711!',
        database='forensight',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            # Get the case
            cursor.execute("SELECT id FROM cases WHERE case_number = 'CASE-2026-001'")
            row = cursor.fetchone()
            if not row:
                print('Case not found')
                return
            case_id = row['id']
            
            # Make case created_at Aug 1 2026
            cursor.execute("UPDATE cases SET created_at = '2026-08-01 10:00:00' WHERE id = %s", (case_id,))
            
            # Get evidence
            cursor.execute("SELECT id FROM evidence WHERE case_id = %s ORDER BY uploaded_at ASC", (case_id,))
            evidence = cursor.fetchall()
            
            # Update evidence dates, spreading them across August/Sept
            dates = ['2026-08-10 14:30:00', '2026-08-25 09:15:00', '2026-09-05 11:20:00', '2026-09-14 16:45:00']
            for i, ev in enumerate(evidence):
                date = dates[i % len(dates)]
                cursor.execute("UPDATE evidence SET uploaded_at = %s WHERE id = %s", (date, ev['id']))
                
            # Get detections
            cursor.execute("SELECT d.id FROM detections d JOIN evidence e ON d.evidence_id = e.id WHERE e.case_id = %s", (case_id,))
            detections = cursor.fetchall()
            for i, det in enumerate(detections):
                date = dates[(i + 2) % len(dates)]
                cursor.execute("UPDATE detections SET created_at = %s WHERE id = %s", (date, det['id']))
                
            conn.commit()
            print('Dates updated successfully in MySQL database!')
    finally:
        conn.close()

if __name__ == "__main__":
    update_dates()
