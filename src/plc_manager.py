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
        self.email_cooldown_seconds = int(os.getenv("EMAIL_COOLDOWN_SECONDS", 60))

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
        self.threads = {} # Alterado para dicionário {name: thread}
        self.handlers = {} # Armazena os handlers ativos por nome
        self.stop_events = {} # Eventos para parar threads individuais
        self.running = False
        self.email_notifier = None
        self.lock_dir = None

    def start_monitoring(self, plcs_config: List[dict], email_notifier, lock_dir):
        self.running = True
        self.email_notifier = email_notifier
        self.lock_dir = lock_dir
        
        for config in plcs_config:
            self.add_machine(config['name'], config['config'])

    def add_machine(self, plc_name: str, config: dict):
        """Inicia o monitoramento de uma nova máquina."""
        if plc_name in self.threads and self.threads[plc_name].is_alive():
            logging.warning(f"Monitoramento já ativo para {plc_name}. Reiniciando...")
            self.remove_machine(plc_name)

        stop_event = threading.Event()
        self.stop_events[plc_name] = stop_event

        t = threading.Thread(
            target=self._monitor_loop,
            args=(config, plc_name, self.email_notifier, self.lock_dir, stop_event),
            daemon=True,
            name=f"Monitor-{plc_name}"
        )
        self.threads[plc_name] = t
        t.start()
        logging.info(f"Monitoramento iniciado dinamicamente para {plc_name}")

    def remove_machine(self, plc_name: str):
        """Para o monitoramento de uma máquina específica."""
        if plc_name in self.stop_events:
            self.stop_events[plc_name].set()
            # Aguarda a thread encerrar (timeout curto para não travar API)
            if plc_name in self.threads:
                self.threads[plc_name].join(timeout=2)
            
            self.stop_events.pop(plc_name, None)
            self.threads.pop(plc_name, None)
            self.handlers.pop(plc_name, None)
            logging.info(f"Monitoramento parado para {plc_name}")

    def _monitor_loop(self, config, plc_name, email_notifier, lock_dir, stop_event):
        from plc_handler import PLCHandler
        handler = None
        retry_wait = config.get('connection_config', {}).get('retry_delay', 5)
        
        while not stop_event.is_set():
            try:
                if not handler:
                    handler = PLCHandler(config, plc_name, self.shared_data, email_notifier, lock_dir)
                    if not handler.attempt_plc_connection():
                        # Espera respeitando o evento de parada
                        stop_event.wait(retry_wait)
                        handler = None
                        continue
                    
                    # Registra o handler para acesso externo
                    self.handlers[plc_name] = handler

                handler.process_plc_data()
                
                # Update shared data for API access (Melhorado para refletir o status real)
                from src.models import PLCReportData
                report_data = PLCReportData(
                    plc_name=plc_name.replace("Cupper_", ""),
                    feed_value=handler.feed_value,
                    size=handler.size,
                    main_value=handler.main_value,
                    total_cups=handler.count_discharge_total,
                    status=handler.status_maquina if hasattr(handler, 'status_maquina') else 'ATIVO',
                    bobina_saida=getattr(handler, 'bobina_saida_name', 'N/A'),
                    bobina_consumida=handler.bobina_saida,
                    count_discharge_total=handler.count_discharge_total,
                    update_time=get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
                )
                self.shared_data.update_plc_data(plc_name, report_data)

                # Espera respeitando o intervalo e o sinal de parada
                interval = config.get('connection_config', {}).get('read_interval', 5)
                stop_event.wait(interval)

            except Exception as e:
                logging.error(f"[{plc_name}] Erro no loop de monitoramento: {e}")
                self.handlers.pop(plc_name, None)
                handler = None
                stop_event.wait(retry_wait)

        logging.info(f"Loop de monitoramento encerrado para {plc_name}")
