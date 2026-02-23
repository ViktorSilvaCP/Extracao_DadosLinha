import sqlite3

def check():
    conn = sqlite3.connect('production_data.db')
    c = conn.cursor()
    
    print("Distinct production_date in coil_consumption_lot:")
    c.execute('SELECT DISTINCT production_date FROM coil_consumption_lot')
    print(c.fetchall())
    
    print("\nDistinct dates in production_records:")
    c.execute('SELECT DISTINCT date(timestamp) FROM production_records')
    print(c.fetchall())

    conn.close()

if __name__ == "__main__": 
    check()
