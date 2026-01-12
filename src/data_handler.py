import os
import logging
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

class ProductionDataHandler:
    def __init__(self, config, plc_name):
        self.config = config
        self.plc_name = plc_name
        self.last_main_value = None
        self.last_feed_value = None
        self.current_date = None
        self.current_file = None
        
        # Determine base directory
        self.base_dir = self.config.get('production_config', {}).get('size_data_dir')
        if not self.base_dir:
            self.base_dir = os.path.join('production_data', self.plc_name.replace(" ", "_"))
        
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except Exception as e:
            logging.warning(f"[{self.plc_name}] Falha ao acessar diretório de rede '{self.base_dir}': {e}. Usando fallback local.")
            self.base_dir = os.path.join('production_data', self.plc_name.replace(" ", "_"))
            os.makedirs(self.base_dir, exist_ok=True)

    def get_cup_size(self, feed_value):
        """Determines cup size based on feed value and config tolerance."""
        try:
            sizes = self.config['cup_size_config']['sizes']
            tolerance = self.config['cup_size_config']['tolerance']
            
            # Normalize feed value for comparison
            fv = round(float(feed_value), 4)
            
            for size, target in sizes.items():
                if abs(fv - target) <= tolerance:
                    return size
            return 'desconhecido'
        except Exception:
            return 'erro'

    def log_production(self, main_value, feed_value, cup_size):
        """Logs production data to a file."""
        try:
            now = get_current_sao_paulo_time()
            date_str = now.strftime('%Y%m%d')
            timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if we need to rotate file (new day or first run)
            if date_str != self.current_date:
                if self.current_file:
                    self.current_file.close()
                
                filename = self.config['file_config']['date_format'].format(
                    size=cup_size, 
                    date=date_str
                )
                filepath = os.path.join(self.base_dir, filename)
                
                file_exists = os.path.exists(filepath)
                try:
                    self.current_file = open(filepath, 'a', encoding='utf-8')
                except Exception as open_err:
                    logging.error(f"[{self.plc_name}] Falha ao abrir arquivo {filepath}: {open_err}")
                    # Try to fallback to local if not already there
                    if "production_data" not in self.base_dir:
                        self.base_dir = os.path.join('production_data', self.plc_name.replace(" ", "_"))
                        os.makedirs(self.base_dir, exist_ok=True)
                        filepath = os.path.join(self.base_dir, filename)
                        self.current_file = open(filepath, 'a', encoding='utf-8')
                    else:
                        raise open_err
                
                if not file_exists:
                    self.current_file.write(f"Início da produção: {timestamp}\n")
                    self.current_file.write(f"Tamanho: {cup_size} | Feed: {feed_value}\n")
                    self.current_file.write("="*50 + "\n")
                
                self.current_date = date_str

            # Log the data point if main value changed
            if main_value != self.last_main_value:
                self.current_file.write(f"{timestamp}: Main: {main_value}, Feed: {feed_value}\n")
                self.current_file.flush()
                self.last_main_value = main_value
                self.last_feed_value = feed_value
                return True
            
            return False
        except Exception as e:
            logging.error(f"[{self.plc_name}] Erro ao registrar produção: {e}")
            return False

    def close(self):
        if self.current_file:
            self.current_file.close()
