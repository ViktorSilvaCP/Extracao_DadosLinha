import sqlite3
import os

db_file = "production_data.db"
if os.path.exists(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Update Cupper_23 with correct IP and Tag
    cursor.execute("""
    UPDATE plc_machines 
    SET ip = '10.81.72.11', lote_tag = 'Cupper22_Bobina_Consumida_Serial'
    WHERE name = 'Cupper_23'
    """)
    
    if cursor.rowcount > 0:
        print(f"Successfully updated Cupper_23 in the database.")
    else:
        print("Cupper_23 not found in the database.")
        
    conn.commit()
    conn.close()
else:
    print(f"Database {db_file} not found.")
