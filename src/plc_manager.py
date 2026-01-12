import threading
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from timezone_utils import get_current_sao_paulo_time
from src.models import PLCReportData

class SharedPLCData:
    def __init__(self):
        self._plcs_data: Dict[str, PLCReportData] = {}
        self.lock = threading.Lock()
        self.last_email_time = None
        self.email_cooldown_seconds = 60

    def update_plc_data(self, plc_name: str, data: PLCReportData):
        with self.lock:
            self._plcs_data[plc_name] = data

    def get_all_data(self) -> List[PLCReportData]:
        with self.lock:
            # Sort by machine name (Cupper 22, 23, etc)
            return sorted(self._plcs_data.values(), key=lambda x: x.plc_name)

    def get_plc_data(self, plc_name: str) -> Optional[PLCReportData]:
        with self.lock:
            return self._plcs_data.get(plc_name)

class PLCMonitorManager:
    """Manages the lifecycle of PLC monitoring threads."""
    def __init__(self, shared_data: SharedPLCData):
        self.shared_data = shared_data
        self.threads = []
        self.running = False

    def start_monitoring(self, plcs_config: List[dict], email_notifier, lock_dir):
        self.running = True
        from plc_handler import PLCHandler # Local import to avoid circular dependencies
        
        for config in plcs_config:
            plc_name = config['name']
            t = threading.Thread(
                target=self._monitor_loop,
                args=(config['config'], plc_name, email_notifier, lock_dir),
                daemon=True,
                name=f"Monitor-{plc_name}"
            )
            self.threads.append(t)
            t.start()
            logging.info(f"Thread de monitoramento iniciada para {plc_name}")

    def _monitor_loop(self, config, plc_name, email_notifier, lock_dir):
        from plc_handler import PLCHandler
        handler = None
        retry_wait = config.get('connection_config', {}).get('retry_delay', 5)
        
        while self.running:
            try:
                if not handler:
                    handler = PLCHandler(config, plc_name, self.shared_data, email_notifier, lock_dir)
                    if not handler.attempt_plc_connection():
                        time.sleep(retry_wait)
                        handler = None
                        continue

                handler.process_plc_data()
                
                # Update shared data for API access
                report_data = PLCReportData(
                    plc_name=plc_name.replace("Cupper ", ""),
                    feed_value=handler.feed_value,
                    size=handler.size,
                    main_value=handler.main_value,
                    total_cups=handler.total_cups,
                    status=config.get('status', 'ATIVO'),
                    bobina_saida=getattr(handler, 'bobina_saida_name', 'N/A'),
                    bobina_consumida=handler.bobina_saida,
                    count_discharge_total=handler.count_discharge_total
                )
                self.shared_data.update_plc_data(plc_name, report_data)

                time.sleep(config['connection_config'].get('read_interval', 5))

            except Exception as e:
                logging.error(f"[{plc_name}] Erro no loop de monitoramento: {e}")
                handler = None # Force reconnection
                time.sleep(retry_wait)
