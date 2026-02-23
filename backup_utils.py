import shutil
import os
import logging
from datetime import datetime
import time

def backup_database():
    """Realiza o backup do banco de dados SQLite."""
    source_db = os.getenv("DB_FILE", "production_data.db")
    backup_dir = os.getenv("BACKUP_DIR", "backups")
    
    if not os.path.exists(source_db):
        logging.error(f"Banco de dados {source_db} não encontrado para backup.")
        return

    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"production_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_file)
    
    try:
        shutil.copy2(source_db, backup_path)
        logging.info(f"Backup realizado com sucesso: {backup_path}")
        
        # Limpeza: Mantém apenas os últimos 10 backups
        backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("production_backup_")])
        while len(backups) > 10:
            oldest_backup = backups.pop(0)
            os.remove(oldest_backup)
            logging.info(f"Backup antigo removido: {oldest_backup}")
            
    except Exception as e:
        logging.error(f"Falha ao realizar backup: {e}")

if __name__ == "__main__":
    # Configuração básica de log para rodar independente se necessário
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    backup_database()
