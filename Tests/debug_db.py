import sqlite3
import json

def check():
    conn = sqlite3.connect('production_data.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("--- coil_consumption_lot (Last 10) ---")
    c.execute('SELECT * FROM coil_consumption_lot ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    for row in rows:
        print(dict(row))
    
    print("\n--- production_records (Last 10) ---")
    c.execute('SELECT * FROM production_records ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    for row in rows:
        print(dict(row))
        
    conn.close()

if __name__ == "__main__":
    check()
