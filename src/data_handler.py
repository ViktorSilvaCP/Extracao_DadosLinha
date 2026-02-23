import logging
from src.database_handler import DatabaseHandler

class ProductionDataHandler:
    def __init__(self, config, plc_name):
        self.config = config
        self.plc_name = plc_name
        self.last_main_value = None

    def log_production(self, main_value, feed_value, cup_size):
        """Logs production data to SQLite instead of files."""
        try:
            # Check if main value changed to avoid redundant entries
            if main_value != self.last_main_value:
                DatabaseHandler.insert_production_detail(
                    machine_name=self.plc_name,
                    cups_produced=main_value,
                    feed_value=feed_value,
                    can_size=cup_size
                )
                self.last_main_value = main_value
                return True
            
            return False
        except Exception as e:
            logging.error(f"[{self.plc_name}] Erro ao registrar produção detalhada no DB: {e}")
            return False

    def close(self):
        """No files to close anymore."""
        pass
