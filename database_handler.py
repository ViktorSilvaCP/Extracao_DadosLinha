from src.database_handler import DatabaseHandler

# Proxy functions for backward compatibility if needed, 
# although the system has been refactored to use DatabaseHandler directly.

def init_db():
    return DatabaseHandler.init_db()

def insert_production_record(machine_name, coil_number, cups_produced, consumption_type, shift):
    return DatabaseHandler.insert_production_record(machine_name, coil_number, cups_produced, consumption_type, shift)