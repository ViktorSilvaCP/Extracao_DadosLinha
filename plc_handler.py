from pylogix import PLC
import time
import threading
import logging
import os
import subprocess
import platform
import tempfile
from datetime import datetime, timedelta

from timezone_utils import get_current_sao_paulo_time
from email_utils import send_email_direct
from email_templates import format_plc_error_message, format_late_lot_alert
from src.database_handler import DatabaseHandler
from src.models import PLCReportData
from src.data_handler import ProductionDataHandler
from src.monitor_utils import get_current_shift

class PLCHandler:
    def __init__(self, config, plc_name, shared_data_manager, email_notifier, email_lock_dir):
        self.config = config
        self.plc_name = plc_name
        self.PLC_CONFIG = config['plc_config']
        self.TAG_CONFIG = config['tag_config']
        self.CONNECTION_CONFIG = config['connection_config']
        
        # Estado atual para Dashboard
        self.feed_value = None
        self.size = None
        self.main_value = None
        self.bobina_saida = None
        self.count_discharge_total = 0
        self._values_changed = False
        
        # Referências de Strokes para cálculos baseados em Triggers (Subtração e Multiplicação)
        self.day_start_stroke = None          # Referência para produção diária (06:00)
        self.initial_stroke_counter = None    # Referência para a bobina atual (Troca de Bobina)
        self.last_shift_sync_stroke = None    # Referência para o turno atual (Virada de Turno)
        
        self.last_reset_date = None
        self.connected = False
        self.plc = None
        self.reconnect_attempt = 0
        self.coil_change_active = False
        self.last_coil_start_time = None
        self.current_shift_tracker = get_current_shift()
        self.shared_data_manager = shared_data_manager
        self.email_notifier = email_notifier
        self.data_handler = ProductionDataHandler(config, plc_name)
        self.last_main_value = None
        self.last_feed_value = None
        self.last_cup_size = None
        self.last_bobina_value = None
        self.pending_lot_checks = [] # Lista de alertas pendentes [{time, lot}]
        self._load_persisted_state()

    def _load_persisted_state(self):
        """Recupera o estado anterior do banco de dados para continuidade."""
        try:
            data = DatabaseHandler.get_current_production(self.plc_name)
            if data:
                record = data[0]
                last_update_str = record.get('last_update')
                if last_update_str:
                    now = get_current_sao_paulo_time()
                    # Regra industrial: Dia começa as 06:00 (com buffer de 30s)
                    def get_prod_date(dt):
                        return (dt - timedelta(hours=6, seconds=30)).date()
                    
                    last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
                    if get_prod_date(last_update) == get_prod_date(now):
                        self.count_discharge_total = record.get('daily_total', 0)
                        self.last_reset_date = get_prod_date(now)
                        logging.info(f"[{self.plc_name}] ♻️ Estado recuperado: Total Diário = {self.count_discharge_total}")
        except Exception as e:
            logging.error(f"[{self.plc_name}] Falha ao carregar estado: {e}")

    def attempt_plc_connection(self):
        """Tenta estabelecer conexão com o PLC."""
        try:
            self.plc = PLC()
            self.plc.IPAddress = self.PLC_CONFIG['ip_address']
            self.plc.ProcessorSlot = self.PLC_CONFIG['processor_slot']
            
            test_tag = self.TAG_CONFIG.get('stroke_tag', 'IGN_Total_Stroke_Counter')
            test_read = self.plc.Read(test_tag)
            
            if test_read.Status == "Success":
                self.connected = True
                self.reconnect_attempt = 0
                return True
            else:
                logging.warning(f"[{self.plc_name}] Falha de leitura na conexão: {test_read.Status}")
                self.plc.Close()
                return False
        except Exception as e:
            logging.error(f"[{self.plc_name}] Erro ao conectar: {e}")
            return False

    def determine_cup_size(self, feed_value):
        """Determina o tamanho do copo baseado no valor do feed e configuração."""
        try:
            tolerance = self.config['cup_size_config']['tolerance']
            sizes = self.config['cup_size_config']['sizes']
            for size, target in sizes.items():
                if abs(feed_value - target) <= tolerance:
                    return size
            return "desconhecido"
        except Exception:
            return "erro"

    def process_plc_data(self, email_notifier=None, lock_dir=None):
        """Ciclo principal de processamento: Otimizado para triggers (Subtração e Multiplicação)."""
        try:
            now_sp = get_current_sao_paulo_time()
            
            # --- 1. SETUP DE TAGS ---
            stroke_tag = self.TAG_CONFIG.get('stroke_tag', 'IGN_Total_Stroke_Counter')
            tool_size_tag = self.TAG_CONFIG.get('tool_size_tag', 'IGN_Tool_Size')
            feed_tag = self.TAG_CONFIG['feed_tag']
            bobina_tag = self.TAG_CONFIG['bobina_tag']
            trigger_coil_tag = self.TAG_CONFIG.get('trigger_coil_tag', 'Coil_change')
            
            # Atualiza email_notifier se foi passado como parâmetro
            if email_notifier:
                self.email_notifier = email_notifier
            
            if not self.connected or not self.plc:
                if not self.attempt_plc_connection(): return

            # --- 2. LEITURA EM LOTE (PERFORMANCE) ---
            tags = [stroke_tag, tool_size_tag, feed_tag, bobina_tag, trigger_coil_tag]
            results = self.plc.Read(tags)
            if any(r.Status != 'Success' for r in results):
                self.connected = False
                return

            # Mapeamento
            data = {r.TagName: r.Value for r in results}
            current_stroke = data[stroke_tag]
            current_tool_size = data[tool_size_tag]
            current_feed_val = round(float(data[feed_tag]), 4)
            current_bobina_val = data[bobina_tag]
            current_trigger_coil = data[trigger_coil_tag]
            current_cup_size = self.determine_cup_size(current_feed_val)

            # --- 3. GESTÃO DE REFERÊNCIAS (RESET DIÁRIO) ---
            def get_prod_date(dt):
                return (dt - timedelta(hours=6, seconds=30)).date()
            
            current_prod_date = get_prod_date(now_sp)
            if self.last_reset_date is None or self.last_reset_date < current_prod_date:
                self.day_start_stroke = current_stroke
                self.last_reset_date = current_prod_date
                logging.info(f"[{self.plc_name}] 🌅 Novo dia industrial: {current_prod_date} | Stroke referência {current_stroke}")

            # Inicialização de emergência
            if self.day_start_stroke is None: self.day_start_stroke = current_stroke
            if self.initial_stroke_counter is None: self.initial_stroke_counter = current_stroke
            if self.last_shift_sync_stroke is None: self.last_shift_sync_stroke = current_stroke
            if self.last_coil_start_time is None: self.last_coil_start_time = now_sp

            # --- 4. CÁLCULOS TIPO "TRIGGER" (SUBTRAÇÃO E MULTIPLICAÇÃO) ---
            # Total Diário: (Atual - Início do Dia) * Ferramenta
            self.count_discharge_total = int((current_stroke - self.day_start_stroke) * current_tool_size)
            
            # Produção Bobina Atual: (Atual - Início da Bobina) * Ferramenta
            current_main_value = int((current_stroke - self.initial_stroke_counter) * current_tool_size)
            
            # --- 5. ATUALIZAÇÃO STATUS (DASHBOARD) ---
            lote_atual = DatabaseHandler.get_lote_from_db(self.plc_name)
            current_shift = get_current_shift()
            
            DatabaseHandler.update_current_production(
                machine_name=self.plc_name,
                current_cups=current_main_value,
                shift=current_shift,
                coil_number=lote_atual,
                feed_value=current_feed_val,
                size=current_cup_size,
                status='ATIVO',
                daily_total=self.count_discharge_total
            )

            # --- 6. TRIGGER: MUDANÇA DE TURNO ---
            if self.current_shift_tracker != current_shift:
                strokes_turno = current_stroke - self.last_shift_sync_stroke
                if strokes_turno > 0:
                    prod = int(strokes_turno * current_tool_size)
                    try:
                        DatabaseHandler.insert_production_record(
                            machine_name=self.plc_name,
                            coil_number=lote_atual,
                            cups_produced=prod,
                            consumption_type="Fechamento Turno",
                            shift=self.current_shift_tracker,
                            absolute_counter=current_main_value,
                            coil_type=get_bobina_type_from_config(self.plc_name),
                            can_size=current_cup_size
                        )
                        logging.info(f"[{self.plc_name}] 🌓 Turno finalizado. Produção: {prod}")
                    except Exception as e: logging.error(f"Erro turno: {e}")
                self.last_shift_sync_stroke = current_stroke
                self.current_shift_tracker = current_shift

            # --- 7. TRIGGER: TROCA DE BOBINA ---
            if current_trigger_coil == 1 and not self.coil_change_active:
                self.coil_change_active = True
                strokes_bobina = current_stroke - self.initial_stroke_counter
                total_bobina = int(max(0, strokes_bobina) * current_tool_size)
                tipo = "Completa" if current_bobina_val == 2 else "Parcial"
                
                try:
                    c_type = DatabaseHandler.get_bobina_type_from_db(self.plc_name)
                    # Registro para Consumo
                    DatabaseHandler.insert_coil_consumption_record(
                        machine_name=self.plc_name,
                        coil_id=f"{lote_atual}-{now_sp.strftime('%H%M%S')}",
                        lot_number=lote_atual,
                        start_time=self.last_coil_start_time,
                        end_time=now_sp,
                        consumed_quantity=total_bobina,
                        unit="cups",
                        production_date=self.last_reset_date.strftime('%Y-%m-%d'),
                        shift=current_shift,
                        consumption_type=tipo,
                        coil_type=c_type
                    )
                    # Registro para Reporte ERP
                    DatabaseHandler.insert_production_record(
                        machine_name=self.plc_name,
                        coil_number=lote_atual,
                        cups_produced=total_bobina,
                        consumption_type=f"REPORTE TOTAL - {tipo}",
                        shift=current_shift,
                        absolute_counter=current_main_value,
                        coil_type=c_type,
                        can_size=current_cup_size
                    )
                    logging.info(f"[{self.plc_name}] 🏁 Bobina finalizada. Total: {total_bobina}")
                except Exception as e: logging.error(f"Erro trigger bobina: {e}")

                # Agenda verificação de Lote para daqui a 3 horas
                check_time = now_sp + timedelta(hours=3)
                self.pending_lot_checks.append({
                    'check_time': check_time,
                    'lot': lote_atual,
                    'start_time': now_sp
                })
                logging.info(f"[{self.plc_name}] 🔔 TRIGGER BOBINA ACIONADO: Lote '{lote_atual}' - Email será enviado em {check_time.strftime('%d/%m/%Y %H:%M:%S')} (São Paulo)")

                # Reinicia referências para a nova bobina
                self.initial_stroke_counter = current_stroke
                self.last_shift_sync_stroke = current_stroke
                self.last_coil_start_time = now_sp

            if current_trigger_coil == 0:
                self.coil_change_active = False

            # --- VERIFICAÇÃO DE ALERTA DE LOTE (3 HORAS) ---
            # Verifica alertas agendados e envia email se tempo de 3 horas foi atingido
            completed_checks = []
            for check in self.pending_lot_checks:
                if now_sp >= check['check_time']:
                    # Revalida o lote atual no momento do disparo
                    current_lote_check = DatabaseHandler.get_lote_from_db(self.plc_name)
                    if current_lote_check == check['lot']:
                        # Envia o alerta com informações de timing
                        self._send_late_lot_alert(check['lot'], check.get('start_time'), now_sp)
                        logging.warning(f"[{self.plc_name}] ⏱️ ALERTA 3H DISPARADO: Lote '{check['lot']}' não foi alterado após 3 horas de produção")
                    else:
                        logging.info(f"[{self.plc_name}] ✓ Lote foi alterado antes do disparo do alerta (de '{check['lot']}' para '{current_lote_check}')")
                    completed_checks.append(check)
            # Limpa checks concluídos
            for check in completed_checks:
                self.pending_lot_checks.remove(check)

            # --- 8. LOGS LOCAIS E CACHE ---
            if current_main_value != self.last_main_value:
                self.data_handler.log_production(current_main_value, current_feed_val, current_cup_size)
                self.last_main_value = current_main_value
                self.main_value = current_main_value
                self.feed_value = current_feed_val
                self.size = current_cup_size
                self._values_changed = True

        except Exception as e:
            logging.error(f"[{self.plc_name}] Erro no ciclo: {e}")
            self.connected = False

    def _send_late_lot_alert(self, old_lot, start_time=None, alert_time=None):
        """Envia email de alerta se o lote não foi trocado após 3 horas.
        
        Args:
            old_lot: Número do lote que não foi alterado
            start_time: Hora que o trigger foi acionado (datetime)
            alert_time: Hora que o alerta está sendo disparado (datetime)
        """
        recipients = os.getenv("NOTIFICATION_RECIPIENTS", "").split(",")
        subject = f"⚠️ ALERTA 3H: Lote não trocado na {self.plc_name}"
        
        # Formata a mensagem com informações de tempo se disponível
        message = format_late_lot_alert(self.plc_name, old_lot)
        
        # Tenta usar email_notifier se disponível, senão usa método direto
        try:
            if self.email_notifier:
                self.email_notifier.send_notification(subject, message, is_error=False)
                logging.info(f"[{self.plc_name}] 📧 Email de alerta do lote '{old_lot}' agendado no pool (3h).")
            else:
                # Fallback para envio direto
                send_email_direct(recipients, subject, message)
                logging.info(f"[{self.plc_name}] 📧 Email de alerta do lote '{old_lot}' enviado diretamente (3h).")
        except Exception as e:
            logging.error(f"[{self.plc_name}] ❌ Erro ao enviar alerta de lote {old_lot}: {e}")

    def write_lote(self, lote_value):
        """Grava o lote no PLC."""
        if not self.connected or not self.plc: return False
        lote_tag = self.TAG_CONFIG.get('lote_tag')
        if not lote_tag: return False
        try:
            res = self.plc.Write(lote_tag, str(lote_value))
            return res.Status == 'Success'
        except Exception: return False
