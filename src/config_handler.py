import json
import logging
import os
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

def load_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config from {config_path}: {e}")
        return None

def save_config(config_path, config):
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Error saving config to {config_path}: {e}")
        return False

def save_lote_to_config(plc_name, lote_value):
    """Salva o número do lote no arquivo de configuração do PLC"""
    config_path = f"{plc_name}/config.json"
    config = load_config(config_path)
    if not config:
        return False
    
    if 'lote_config' not in config:
        config['lote_config'] = {}
    
    lote_anterior = config['lote_config'].get('current_lote')
    if lote_anterior and lote_anterior != lote_value:
        config['lote_config']['bobina_saida'] = lote_anterior
        config['lote_config']['data_saida'] = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    
    config['lote_config']['current_lote'] = lote_value
    config['lote_config']['last_updated'] = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    
    return save_config(config_path, config)

def save_bobina_type_to_config(plc_name, tipo_bobina):
    """Salva o tipo da bobina no arquivo de configuração do PLC."""
    config_path = f"{plc_name}/config.json"
    config = load_config(config_path)
    if not config:
        return False
    
    if 'lote_config' not in config:
        config['lote_config'] = {}
    
    config['lote_config']['tipo_bobina'] = tipo_bobina
    return save_config(config_path, config)

def get_lote_from_config(plc_name):
    config_path = f"{plc_name}/config.json"
    config = load_config(config_path)
    if config:
        return config.get('lote_config', {}).get('current_lote', 'Nenhum lote definido')
    return 'Erro ao carregar lote'

def get_bobina_type_from_config(plc_name):
    config_path = f"{plc_name}/config.json"
    config = load_config(config_path)
    if config:
        return config.get('lote_config', {}).get('tipo_bobina')
    return None

def get_bobina_saida_from_config(plc_name):
    config_path = f"{plc_name}/config.json"
    config = load_config(config_path)
    if config:
        bobina_saida = config.get('lote_config', {}).get('bobina_saida', 'Nenhuma bobina saída')
        data_saida = config.get('lote_config', {}).get('data_saida', '')
        return {'lote': bobina_saida, 'data_saida': data_saida}
    return {'lote': 'Erro ao carregar', 'data_saida': ''}
