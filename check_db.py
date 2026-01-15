import sqlite3
from src.database_handler import DatabaseHandler

# Test update
DatabaseHandler.update_current_production(
    machine_name='Test_Cupper',
    current_cups=12345,
    shift='DIA',
    coil_number='TEST123',
    feed_value=1.234,
    size='269ml',
    status='ATIVO'
)

# Check
conn = sqlite3.connect('production_data.db')
c = conn.cursor()
c.execute('SELECT * FROM current_production WHERE machine_name="Test_Cupper"')
row = c.fetchone()
print("Row:", row)
conn.close()