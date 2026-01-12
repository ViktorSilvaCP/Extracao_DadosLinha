from dataclasses import dataclass
from datetime import datetime
from threading import Lock

@dataclass
class ProductionData:
    plc_name: str
    feed_value: float
    size: str
    main_value: int
    total_cups: int
    timestamp: datetime
    file_content: bytes = None
    file_name: str = None

class PLCDataManager:
    def __init__(self):
        self.data = {}  # plc_name -> ProductionData
        self.lock = Lock()
        self.changes_pending = False
    
    def update_data(self, production_data: ProductionData):
        with self.lock:
            self.data[production_data.plc_name] = production_data
            self.changes_pending = True
    
    def get_and_clear_pending_data(self):
        with self.lock:
            if not self.changes_pending:
                return None
            result = self.data.copy()
            self.changes_pending = False
            return result
