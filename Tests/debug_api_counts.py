import sqlite3
import json

def check_data():
    conn = sqlite3.connect('production_data.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    calc_date = "CASE WHEN time(timestamp) < '06:00:30' THEN date(timestamp, '-1 day') ELSE date(timestamp) END"
    
    print("--- Contagem por data_turno ---")
    cur.execute(f"SELECT {calc_date} as data_turno, COUNT(*) as total FROM production_records GROUP BY data_turno ORDER BY data_turno DESC")
    rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        print(f"Data: {row['data_turno']} | Total: {row['total']}")
    
    conn.close()

if __name__ == "__main__":
    check_data()
