import os
import hashlib
import logging
from datetime import datetime, timedelta

EMAIL_LOCK_DURATION_MINUTES = 10

def create_email_lock(plcs_list_for_report, lock_dir):
    """Cria um arquivo de trava para evitar o envio de e-mails repetidos."""
    report_identifier = ";".join(
        sorted([f"{p.plc_name}:{p.main_value}:{p.size}" for p in plcs_list_for_report]))
    
    hasher = hashlib.sha256(report_identifier.encode())
    hex_identifier = hasher.hexdigest()
    binary_digest = hasher.digest()

    lock_filename = f"lock_{hex_identifier}.tmp"
    lock_file_path = os.path.join(lock_dir, lock_filename)
    
    try:
        with open(lock_file_path, 'wb') as f:
            f.write(binary_digest)
        logging.info(f"Lock file created/updated: {lock_file_path}")
    except Exception as e:
        logging.error(f"Failed to create lock file: {e}")

def should_send_email(plcs_list_for_report, lock_dir):
    """Verifica se um e-mail idêntico foi enviado recentemente."""
    current_report_identifier = ";".join(
        sorted([f"{p.plc_name}:{p.main_value}:{p.size}" for p in plcs_list_for_report]))
    
    current_hasher = hashlib.sha256(current_report_identifier.encode())
    hex_identifier = current_hasher.hexdigest()
    current_binary_digest = current_hasher.digest()

    lock_file_path = os.path.join(lock_dir, f"lock_{hex_identifier}.tmp")

    if not os.path.exists(lock_file_path):
        return True

    file_mod_time = datetime.fromtimestamp(os.path.getmtime(lock_file_path))
    is_lock_active = (datetime.now() - file_mod_time) < timedelta(minutes=EMAIL_LOCK_DURATION_MINUTES)

    if is_lock_active:
        return False
    
    try:
        with open(lock_file_path, 'rb') as f:
            stored_digest = f.read()

        if current_binary_digest == stored_digest:
            create_email_lock(plcs_list_for_report, lock_dir) # Refresh lock
            return False
        return True
    except Exception:
        return True

def get_current_shift():
    """Retorna o turno atual baseado nas regras: Dia (06-18), Noite (18-06)."""
    from timezone_utils import get_current_sao_paulo_time
    now = get_current_sao_paulo_time()
    hour = now.hour
    
    if 6 <= hour < 18:
        return "DIA (06-18)"
    else:
        return "NOITE (18-06)"
