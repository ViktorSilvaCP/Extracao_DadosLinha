from pylogix import PLC
import time
import logging
import os
import subprocess
import platform
import tempfile
import hashlib
from datetime import datetime, timedelta

from timezone_utils import get_current_sao_paulo_time
from email_utils import send_email_direct
from email_templates import format_plc_error_message, format_production_report
from src.database_handler import DatabaseHandler
from src.config_handler import get_lote_from_config, get_bobina_saida_from_config, load_config
from src.models import PLCReportData
from src.data_handler import ProductionDataHandler
from src.monitor_utils import get_current_shift, should_send_email, create_email_lock

class PLCHandler:
    def __init__(self, config, plc_name, shared_data_manager, email_notifier, email_lock_dir):
        self.config = config
        self.plc_name = plc_name
        self.PLC_CONFIG = config['plc_config']
        self.TAG_CONFIG = config['tag_config']
        self.CONNECTION_CONFIG = config['connection_config']
        self.last_main_value = None
        self.last_feed_value = None
        self.last_cup_size = None
        self.last_bobina_value = None
        self.total_cups = 0
        self.current_size_file = None
        self.connected = False
        self.plc = None
        self.reconnect_attempt = 0  
        self.base_delay = 60  
        self.current_date = None
        self.existing_files = {}  
        self.data_dir = self.config.get('production_config', {}).get('size_data_dir')
        self.previous_values = {
            'feed': None,
            'size': None,
            'main': None,
            'total': None
        }
        self.feed_value = None
        self.size = None
        self.main_value = None
        self.bobina_saida = None
        self._values_changed = False
        self.last_values = None
        self._feed_alert_sent = False
        self.last_reset_date = None
        self.last_count_discharge = None
        self.count_discharge_total = 0
        self.coil_change_active = False
        self.shared_data_manager = shared_data_manager
        self.email_notifier = email_notifier
        self.email_lock_dir = email_lock_dir
        self.last_trigger_value = None
        self.data_handler = ProductionDataHandler(config, plc_name)
        self.last_db_sync_value = 0
        self.last_db_sync_time = time.time()
        self.current_shift_tracker = get_current_shift()

    def ping_host(self, ip_address):
        try:
            ping_cmd = ["ping", "-n", "1", ip_address] if platform.system().lower() == "windows" else ["ping", "-c", "1", ip_address]
            result = subprocess.run(ping_cmd, capture_output=True, text=True, check=True)
            logging.info(f"[{self.plc_name}] Ping to {ip_address} successful.")
            return True
        except subprocess.CalledProcessError:
            logging.warning(f"[{self.plc_name}] Ping to {ip_address} failed.")
            return False
        except Exception as e:
            logging.error(f"[{self.plc_name}] Ping error: {e}")
            return False

    def get_reconnect_delay(self):
        """Calculate delay based on number of failed reconnection attempts"""
        if self.reconnect_attempt == 0:
            return 0
        
        delay = min(self.base_delay * self.reconnect_attempt, 1800)
        logging.info(f"[{self.plc_name}] Next reconnection attempt in {delay/60:.0f} minutes")
        return delay

    def attempt_plc_connection(self):
        """Attempts to connect to the PLC, with retries."""
        max_attempts = self.CONNECTION_CONFIG['max_attempts']
        retry_delay = self.CONNECTION_CONFIG['retry_delay']
        
        for attempt in range(1, max_attempts + 1):
            try:
                logging.info(f"[{self.plc_name}] Tentativa {attempt}/{max_attempts} de conexão")
                self.plc = PLC()
                self.plc.IPAddress = self.PLC_CONFIG['ip_address']
                self.plc.ProcessorSlot = self.PLC_CONFIG['processor_slot']
                
                test_read = self.plc.Read('Count_discharge')
                
                if test_read.Status == "Success":
                    logging.info(f"[{self.plc_name}] Conexão bem sucedida - Valor: {test_read.Value}")
                    self.connected = True
                    return True
                else:
                    logging.error(f"[{self.plc_name}] Falha na leitura: {test_read.Status}")
                    self.plc.Close()
                    return False
                    
            except Exception as e:
                logging.error(f"[{self.plc_name}] Falha na tentativa {attempt}/{max_attempts}: {e}")
                if attempt < max_attempts:
                    logging.info(f"[{self.plc_name}] Aguardando {retry_delay}s para próxima tentativa")
                    time.sleep(retry_delay)
                    
        return False

    def determine_cup_size(self, feed_value):
        """Determines cup size based on Feed_Progression_INCH value."""
        try:
            
            feed_str = str(feed_value)
            decimal_pos = feed_str.find('.')
            if decimal_pos != -1:
                feed_value = float(feed_str[:decimal_pos] + feed_str[decimal_pos:decimal_pos+5])
            else:
                feed_value = float(feed_str[:5])
            
            logging.debug(f"[{self.plc_name}] Processed feed value: {feed_value}")
            
            tolerance = self.config['cup_size_config']['tolerance']
            sizes = self.config['cup_size_config']['sizes']

            for size, target_value in sizes.items():
                if abs(feed_value - target_value) <= tolerance:
                    logging.debug(f"[{self.plc_name}] Matched size {size} for value {feed_value}")
                    return size
            
            logging.warning(f"[{self.plc_name}] Feed value {feed_value} outside tolerance ranges")
            return "desconhecido"
            
        except Exception as e:
            logging.error(f"[{self.plc_name}] Error in determine_cup_size: {str(e)}")
            return "erro"

    def get_filename(self, cup_size, feed_value, data_dir):
        """Get appropriate filename based on cup size and feed value"""
        base_format = self.config['file_config']['base_format']
        date_format = self.config['file_config']['date_format']
        
        base_filename = base_format.format(size=cup_size)
        base_filepath = os.path.join(data_dir, base_filename)
        
        
        if os.path.exists(base_filepath) and cup_size in self.existing_files:
            if self.existing_files[cup_size] != feed_value:
                date_str = get_current_sao_paulo_time().strftime('%Y%m%d')
                return os.path.join(data_dir, date_format.format(size=cup_size, date=date_str))
        
        self.existing_files[cup_size] = feed_value
        return base_filepath

    def calculate_total_from_file(self, filepath):
        """Calculate total by summing all Main values from file"""
        try:
            total = 0
            with open(filepath, 'r') as f:
                for line in f:
                    if 'Main:' in line:
                        
                        main_str = line.split('Main:')[1].split(',')[0].strip()
                        total += int(main_str)  
            return total
        except Exception as e:
            logging.error(f"[{self.plc_name}] Error calculating total: {e}")
            return 0

    @property
    def values_changed(self):
        """Check if values changed and reset flag"""
        changed = self._values_changed
        self._values_changed = False
        return changed

    

    def create_temp_production_file(self, lote_atual=None):
        """Creates a temporary file with current production data"""
        try:
            temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8')
            current_time = get_current_sao_paulo_time().strftime('%Y-%m-%d %H:%M:%S')
            
            content = f"""RELATÓRIO DE PRODUÇÃO - {self.plc_name}
Data/Hora: {current_time}
==============================================
Lote Atual: {lote_atual if lote_atual else 'N/A'}
Status Bobina: {self.bobina_saida if self.bobina_saida else 'N/A'}
Formato: {self.size}
Feed Rate: {self.feed_value:.4f} inch
Contador: {self.main_value}
Total Acumulado: {"{:,}".format(self.total_cups).replace(",", ".")} copos
=============================================="""
            
            temp_file.write(content)
            temp_file.close()
            return temp_file.name, content.encode('utf-8') 
        except Exception as e:
            logging.error(f"Erro criando arquivo temporário: {e}")
            return None

    def get_production_files(self):
        """Returns current production file paths"""
        """Returns current production file paths.
        The first file in the list, if present, is a temporary file for the email.
        The second, if present, is the persistent log file.
        """
        files = []
        temp_file_path, _ = self.create_temp_production_file(None) 
        if os.path.exists(temp_file_path):
                files.append(temp_file_path)
        else:
                logging.warning(f"[{self.plc_name}] Arquivo temporário {temp_file_path} não foi encontrado após a criação.")
            
        
        if self.current_size_file and hasattr(self.current_size_file, 'name'):
            try:
                current_file_log_path = self.current_size_file.name
                if os.path.exists(current_file_log_path):
                    
                    if not files or (files and current_file_log_path != files[0]):
                         files.append(current_file_log_path)
            except Exception as e:
                logging.warning(f"[{self.plc_name}] Erro ao tentar adicionar arquivo de log persistente {self.current_size_file.name if hasattr(self.current_size_file, 'name') else 'N/A'} à lista de anexos: {e}")
                
        return files 

    def process_plc_data(self, email_notifier=None, lock_dir=None):
        """Process data from a single PLC."""
        try:
            main_tag = self.TAG_CONFIG['main_tag']
            feed_tag = self.TAG_CONFIG['feed_tag']
            bobina_tag = self.TAG_CONFIG['bobina_tag']
            count_discharge_tag = 'Count_discharge'
            trigger_coil_tag = self.TAG_CONFIG.get('trigger_coil_tag', 'Coil_change')
            read_interval = self.CONNECTION_CONFIG['read_interval']
            
            # Check for 6 AM reset
            now_sp = get_current_sao_paulo_time()
            if self.last_reset_date is None or now_sp.date() > self.last_reset_date:
                if now_sp.hour >= 6:
                    self.count_discharge_total = 0
                    self.last_reset_date = now_sp.date()
                    logging.info(f"[{self.plc_name}] Reset count_discharge_total at 6 AM")

            if not self.data_dir or 'file_config' not in self.config:
                logging.error(f"[{self.plc_name}] Configuration error: missing 'size_data_dir' or 'file_config'")
                return 

            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except Exception as e:
                logging.warning(f"[{self.plc_name}] Falha ao acessar diretório de rede '{self.data_dir}': {e}. Usando fallback local.")
                script_dir = os.path.dirname(os.path.abspath(__file__))
                local_data_dir = os.path.join(script_dir, 'production_data', self.plc_name.replace(" ", "_"))
                self.data_dir = local_data_dir  
                os.makedirs(self.data_dir, exist_ok=True)
                logging.info(f"[{self.plc_name}] Production data will be saved to local directory: {self.data_dir}")

            
            if not self.connected or not self.plc:
                if not self.attempt_plc_connection(): 
                    logging.warning(f"[{self.plc_name}] Falha ao conectar ao PLC. Tentando novamente no próximo ciclo.")
                    return 

            # Read each tag individually and log specific errors
            count_discharge_data = self.plc.Read(count_discharge_tag)
            if count_discharge_data.Status != 'Success':
                logging.error(f"[{self.plc_name}] Failed to read Count_discharge: {count_discharge_data.Status}")
                self.connected = False
                return

            feed_data = self.plc.Read(feed_tag)
            if feed_data.Status != 'Success':
                logging.error(f"[{self.plc_name}] Failed to read Feed_Progression_INCH: {feed_data.Status}")
                self.connected = False
                return

            bobina_data = self.plc.Read(bobina_tag)
            if bobina_data.Status != 'Success':
                logging.error(f"[{self.plc_name}] Failed to read Bobina_Consumida: {bobina_data.Status}")
                self.connected = False
                return

            trigger_coil_data = self.plc.Read(trigger_coil_tag) #Ler tag Coil_change
            if trigger_coil_data.Status != 'Success':
                logging.error(f"[{self.plc_name}] Failed to read Coil_change: {trigger_coil_data.Status}")
                self.connected = False
                return

            current_main_value = count_discharge_data.Value
            current_bobina_value = bobina_data.Value
            
            # --- LÓGICA DE GRAVAÇÃO POR TURNO E LOTE (TOTVS) ---
            if current_main_value is not None:
                # Inicializa referência na primeira leitura para evitar pico no reinício
                if self.last_db_sync_value == 0 and current_main_value > 0:
                    self.last_db_sync_value = current_main_value

                # Se houve reset no PLC (valor atual menor que o último salvo), reseta nossa referência
                if current_main_value < self.last_db_sync_value:
                    self.last_db_sync_value = 0

                # Verifica mudança de turno para fechar o lote atual no turno correto
                real_current_shift = get_current_shift()
                if self.current_shift_tracker != real_current_shift:
                    delta_producao = current_main_value - self.last_db_sync_value
                    
                    if delta_producao > 0:
                        try:
                            bobina_info = get_bobina_saida_from_config(self.plc_name)
                            coil_num = bobina_info.get('lote', 'N/A')
                            
                            DatabaseHandler.insert_production_record(
                                machine_name=self.plc_name,
                                coil_number=coil_num,
                                cups_produced=delta_producao,
                                consumption_type="Fechamento Turno",
                                shift=self.current_shift_tracker # Grava no turno que encerrou
                            )
                            self.last_db_sync_value = current_main_value
                        except Exception as e:
                            logging.error(f"[{self.plc_name}] Erro ao gravar fechamento de turno: {e}")
                    
                    self.current_shift_tracker = real_current_shift


            logging.debug(f"[{self.plc_name}] Raw feed_data.Value: {feed_data.Value} (type: {type(feed_data.Value)})")
            if isinstance(feed_data.Value, float):
                
                
                current_feed_value = round(feed_data.Value, 4)
            else:
                
                feed_str = str(feed_data.Value)
                decimal_pos = feed_str.find('.')
                if decimal_pos != -1:
                    current_feed_value = float(feed_str[:decimal_pos + 5])  
                else:
                    current_feed_value = float(feed_str[:5]) 
            logging.debug(f"[{self.plc_name}] Processed current_feed_value: {current_feed_value}")
            
            if current_main_value is None or current_feed_value is None or current_bobina_value is None:
                logging.warning(f"[{self.plc_name}] Received null values: Main={current_main_value}, Feed={current_feed_value}, Bobina={current_bobina_value}")
                return 

            
            if current_bobina_value == 1:
                bobina_status = "Baixa Parcial"
            elif current_bobina_value == 2:
                bobina_status = "Baixa Completa"
            elif current_bobina_value == 0:
                bobina_status = "Nenhuma Bobina Consumida"
            else:
                bobina_status = f"Valor Desconhecido ({current_bobina_value})"
                logging.warning(f"[{self.plc_name}] Valor desconhecido para Bobina_Consumida: {current_bobina_value}")

            now_sao_paulo = get_current_sao_paulo_time()
            current_timestamp = now_sao_paulo.strftime('%Y-%m-%d %H:%M:%S %Z%z')
            date_str = now_sao_paulo.strftime('%Y%m%d')
            current_cup_size = self.determine_cup_size(current_feed_value)

            
            if current_cup_size == "desconhecido":
                if not hasattr(self, '_feed_alert_sent') or not self._feed_alert_sent:
                    subject = f"[ALERTA] Valor desconhecido do Feed em {self.plc_name}"
                    error_details = f"Valor do Feed_Progression_INCH fora do esperado: {current_feed_value} (PLC: {self.plc_name})"
                    msg = format_plc_error_message(self.plc_name, error_details)
                    send_email_direct(
                        to=["victor.nascimento@canpack.com", "felipe.rossetti@canpack.com"],
                        subject=subject,
                        message={"text": msg, "html": msg}
                    )
                    self._feed_alert_sent = True
            else:
                self._feed_alert_sent = False

            logging.debug(f"[{self.plc_name}] Checking values - Feed: {current_feed_value}, Size: {current_cup_size}, Main: {current_main_value}")

            
            feed_changed = current_feed_value != self.last_feed_value
            main_changed = current_main_value != self.last_main_value
            size_changed = current_cup_size != self.last_cup_size
            bobina_changed = current_bobina_value != getattr(self, 'last_bobina_value', None)
            
            if (feed_changed or main_changed or size_changed or bobina_changed):
                
                logging.debug(f"[{self.plc_name}] Values changed - Feed: {current_feed_value}, Size: {current_cup_size}, Main: {current_main_value}")
                
                
                if bobina_changed:
                    last_bobina = getattr(self, 'last_bobina_value', None)
                    if last_bobina == 0 and current_bobina_value in [1, 2]:
                        logging.info(f"[{self.plc_name}] 🎯 BOBINA CONSUMIDA DETECTADA! De {last_bobina} para {current_bobina_value} ({bobina_status})")
                    elif last_bobina in [1, 2] and current_bobina_value == 0:
                        logging.info(f"[{self.plc_name}] Bobina resetada para 0 (pronto para próxima bobina)")
                    elif last_bobina in [1, 2] and current_bobina_value in [1, 2]:
                        logging.info(f"[{self.plc_name}] Mudança de status da bobina: {last_bobina} -> {current_bobina_value}")
                
                self.feed_value = current_feed_value
                self.size = current_cup_size
                self.main_value = current_main_value
                self.bobina_saida = bobina_status
                self._values_changed = True
                
                self.previous_values = {
                    'feed': current_feed_value,
                    'size': current_cup_size,
                    'main': current_main_value,
                    'total': self.total_cups 
                }

                self.last_feed_value = current_feed_value
                self.last_cup_size = current_cup_size
                self.last_bobina_value = current_bobina_value
                

            if (current_cup_size != self.last_cup_size or 
                date_str != self.current_date or 
                self.current_size_file is None):
                
                filepath = self.get_filename(current_cup_size, current_feed_value, self.data_dir)
                logging.info(f"[{self.plc_name}] File check - Path: {filepath}")
                file_exists = os.path.exists(filepath)

                if self.current_size_file:
                    self.current_size_file.close()

                self.current_size_file = open(filepath, 'a')
                
                if not file_exists:
                    logging.info(f"[{self.plc_name}] Creating new file with header")
                    header = (f"Início da produção: {current_timestamp}\n"
                            f"Tamanho do copo: {current_cup_size}\n"
                            f"Feed value: {current_feed_value}\n"
                            f"===============================================\n"
                            f"Registros de produção:\n")
                    self.current_size_file.write(header)
                    self.total_cups = 0  
                    logging.info(f"[{self.plc_name}] Reset total cups counter to 0")
                else:
                    logging.info(f"[{self.plc_name}] Appending to existing file")

                
                self.current_date = date_str

            # Process Count_discharge
            current_count_discharge = count_discharge_data.Value
            current_trigger_coil = trigger_coil_data.Value

            # Only process Count_discharge if trigger_coil is not active
            if not self.coil_change_active:
                if current_count_discharge != self.last_count_discharge and current_count_discharge is not None:
                    # Protect against zero values
                    if current_count_discharge > 0 or (current_count_discharge == 0 and self.last_count_discharge is not None):
                        self.count_discharge_total += current_count_discharge
                        logging.debug(f"[{self.plc_name}] Count_discharge updated: +{current_count_discharge}, Total: {self.count_discharge_total}")
                    self.last_count_discharge = current_count_discharge

            # Monitor trigger_coil
            if current_trigger_coil == 1 and not self.coil_change_active:
                self.coil_change_active = True
                logging.info(f"[{self.plc_name}]  TRIGGER DE TROCA DE BOBINA ATIVADO (Bobina_Trocada = 1)")

                # --- INÍCIO DA LÓGICA DE ENVIO DE E-MAIL E REGISTRO DE PRODUÇÃO ---

                lote_atual = get_lote_from_config(self.plc_name)
                bobina_saida_info = get_bobina_saida_from_config(self.plc_name)
                current_shift = get_current_shift()

                # Insere registro no DB
                try:
                    # Se houve reset no PLC antes da troca
                    if self.main_value < self.last_db_sync_value:
                        self.last_db_sync_value = 0
                        
                    # Calcula o delta final (o que foi produzido desde a última parcial até agora)
                    delta_final = self.main_value - self.last_db_sync_value
                    
                    DatabaseHandler.insert_production_record(
                        machine_name=self.plc_name,
                        coil_number=bobina_saida_info['lote'],
                        cups_produced=delta_final,
                        consumption_type=self.bobina_saida,
                        shift=self.current_shift_tracker
                    )
                    self.last_db_sync_value = self.main_value # Sincroniza a referência
                except Exception as db_error:
                    logging.error(f"[{self.plc_name}] Falha ao inserir registro no banco de dados: {db_error}")

                # Prepara dados para o relatório
                report_data = PLCReportData(
                    plc_name=self.plc_name.replace("Cupper_", ""),
                    feed_value=self.feed_value,
                    size=self.size,
                    main_value=self.main_value,
                    total_cups=self.total_cups,
                    update_time=get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S"),
                    status=self.config.get('status', 'ATIVO'),
                    bobina_saida=bobina_saida_info['lote'],
                    bobina_consumida=self.bobina_saida,
                    current_shift=current_shift,
                    count_discharge_total=self.count_discharge_total
                )
                temp_file_info = self.create_temp_production_file(lote_atual)
                if temp_file_info:
                    report_data.temp_attachment_path, content_bytes = temp_file_info
                    report_data.attachment_filename = os.path.basename(report_data.temp_attachment_path)
                    report_data.attachment_content = content_bytes
                plcs_list_for_report = [report_data]
                if should_send_email(plcs_list_for_report, self.email_lock_dir):
                    logging.info(f"[{self.plc_name}] Trava de e-mail liberada. Preparando para enviar relatório.")

                    lote_values = {self.plc_name: lote_atual}
                    formatted_report = format_production_report(plcs_list_for_report, lote_values)
                    
                    email_attachments = []
                    if report_data.attachment_filename and report_data.attachment_content:
                        email_attachments.append({
                            'filename': report_data.attachment_filename,
                            'content': report_data.attachment_content
                        })

                    # Envia o e-mail de produção
                    self.email_notifier.send_notification(
                        "Relatório de Produção - Cuppers",
                        formatted_report,
                        is_error=False,
                        attachments=email_attachments
                    )
                    logging.info(f"[{self.plc_name}] E-mail de produção enviado.")

                    # Cria a trava para evitar e-mails repetidos
                    create_email_lock(plcs_list_for_report, self.email_lock_dir)

                else:
                    logging.info(f"[{self.plc_name}] Envio de e-mail suprimido pela trava (relatório idêntico recente).")

                # Limpa o arquivo temporário
                if report_data.temp_attachment_path and os.path.exists(report_data.temp_attachment_path):
                    try:
                        os.unlink(report_data.temp_attachment_path)
                        logging.info(f"[{self.plc_name}] Arquivo temporário {report_data.temp_attachment_path} removido.")
                    except Exception as e_unlink:
                        logging.error(f"[{self.plc_name}] Falha ao remover arquivo temporário: {e_unlink}")

                # Zera o contador para o próximo ciclo
                self.last_count_discharge = 0
                # --- FIM DA LÓGICA DE ENVIO DE E-MAIL ---

            elif current_trigger_coil == 0 and self.coil_change_active:
                self.coil_change_active = False
                logging.info(f"[{self.plc_name}] TRIGGER DE TROCA DE BOBINA DESATIVADO (Bobina_Trocada = 0). Aguardando próximo ciclo.")

            if current_main_value != self.last_main_value:
                self.data_handler.log_production(current_main_value, current_feed_value, current_cup_size)
                self.total_cups = self.calculate_total_from_file(self.current_size_file.name)
                self.last_main_value = current_main_value
                logging.debug(f"[{self.plc_name}] Updated total cups to {self.total_cups}")
                self._values_changed = True

            
            if self._values_changed:
                 self.previous_values['total'] = self.total_cups

            
            

        except Exception as e:
            logging.error(f"[{self.plc_name}] Processing error: {e}")
            self.connected = False
            raise  

        
        

    def write_lote(self, lote_value):
        """(Desativado) Futuramente irá escrever o valor do lote no PLC."""
        
        
        
        
        
        
        
        
        
        
        
        
        
        return True  

    def get_current_file_path(self):
        """Retorna o caminho do arquivo atual de produção"""
        if self.current_size_file:
            return self.current_size_file.name
        return None
