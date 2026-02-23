import sqlite3
import os

DB_FILE = 'c:/programs/Extracao_DadosLinha/production_data.db'

def check():
    if not os.path.exists(DB_FILE):
        print("DB not found")
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print("Last 20 production_records:")
    cursor.execute("SELECT * FROM production_records ORDER BY id DESC LIMIT 20")
    for row in cursor.fetchall():
        print(row)
    conn.close()

if __name__ == "__main__":
    check()
