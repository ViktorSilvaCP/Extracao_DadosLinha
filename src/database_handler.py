import sqlite3
import logging
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

DB_FILE = "production_data.db"

class DatabaseHandler:
    @staticmethod
    def init_db():
        """Inicializa o banco de dados e cria a tabela se ela não existir. 
        Também garante que as migrações necessárias sejam aplicadas."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS production_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    machine_name TEXT NOT NULL,
                    coil_number TEXT NOT NULL,
                    cups_produced INTEGER NOT NULL,
                    consumption_type TEXT,
                    shift TEXT NOT NULL
                )
                """)
                
                # Migração: Garante que a coluna 'shift' exista caso a tabela tenha sido criada em versão anterior
                cursor.execute("PRAGMA table_info(production_records)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'shift' not in columns:
                    logging.info("Migrando banco de dados: Adicionando coluna 'shift'")
                    cursor.execute("ALTER TABLE production_records ADD COLUMN shift TEXT DEFAULT 'Unknown'")
                
                conn.commit()
            logging.info(f"Banco de dados '{DB_FILE}' inicializado e verificado com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao inicializar o banco de dados: {e}")

    @staticmethod
    def insert_production_record(machine_name, coil_number, cups_produced, consumption_type, shift):
        """Insere um novo registro de produção no banco de dados."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO production_records (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift))
                conn.commit()
            logging.info(f"Registro de produção inserido: {machine_name} - Bobina {coil_number}")
        except Exception as e:
            logging.error(f"Erro ao inserir registro de produção: {e}")

    @staticmethod
    def get_production_by_shift(machine_name=None):
        """Calcula a produção total por turno."""
        try:
            query = """
                SELECT machine_name, shift, coil_number, SUM(cups_produced) as total, MAX(timestamp) as last_update
                FROM production_records
            """
            params = []
            if machine_name:
                query += " WHERE machine_name = ?"
                params.append(machine_name)
            
            query += " GROUP BY machine_name, shift, coil_number ORDER BY last_update DESC"
            
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção por turno: {e}")
            return []

    @staticmethod
    def get_production_by_lot(machine_name=None):
        """Calcula a produção total por lote (coil_number)."""
        try:
            query = """
                SELECT machine_name, coil_number, shift, SUM(cups_produced) as total, MIN(timestamp) as start_time, MAX(timestamp) as end_time
                FROM production_records
            """
            params = []
            if machine_name:
                query += " WHERE machine_name = ?"
                params.append(machine_name)
            
            query += " GROUP BY machine_name, coil_number ORDER BY end_time DESC LIMIT 50"
            
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção por lote: {e}")
            return []

    @staticmethod
    def get_recent_production(limit=100, since_id=None):
        """Retorna os registros mais recentes para integração com ERP."""
        try:
            query = "SELECT * FROM production_records"
            params = []
            if since_id:
                query += " WHERE id > ?"
                params.append(since_id)
            
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar registros recentes: {e}")
            return []
