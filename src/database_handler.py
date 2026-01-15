import sqlite3
import logging
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

DB_FILE = "production_data.db"
DB_TIMEOUT = 20.0  # Timeout de 20 segundos para operações concorrentes no BD

class DatabaseHandler:
    @staticmethod
    def init_db():
        """Inicializa o banco de dados e cria a tabela se ela não existir. 
        Também garante que as migrações necessárias sejam aplicadas."""
        try:
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                cursor = conn.cursor()
                # Ativa o modo WAL (Write-Ahead Logging) para melhor concorrência.
                # Uma vez ativado, é persistente no arquivo do banco de dados.
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS production_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    machine_name TEXT NOT NULL,
                    coil_number TEXT NOT NULL,
                    cups_produced INTEGER NOT NULL,
                    consumption_type TEXT,
                    shift TEXT NOT NULL,
                    absolute_counter INTEGER DEFAULT 0
                )
                """)
                
                # Nova tabela para registros de consumo de bobina
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS coil_consumption_lot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_name TEXT NOT NULL,
                    coil_id TEXT NOT NULL,
                    lot_number TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    consumed_quantity INTEGER NOT NULL,
                    unit TEXT NOT NULL,
                    production_date TEXT NOT NULL,
                    shift TEXT NOT NULL,
                    consumption_type TEXT NOT NULL
                )
                """)
                
                # Tabela para status atual de produção
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS current_production (
                    machine_name TEXT PRIMARY KEY,
                    current_cups INTEGER NOT NULL DEFAULT 0,
                    last_update TEXT NOT NULL,
                    shift TEXT NOT NULL,
                    coil_number TEXT NOT NULL,
                    feed_value REAL,
                    size TEXT,
                    status TEXT DEFAULT 'ATIVO',
                    daily_total INTEGER DEFAULT 0
                )
                """)
                
                # Migração: Garante que a coluna 'shift' exista caso a tabela tenha sido criada em versão anterior
                cursor.execute("PRAGMA table_info(production_records)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'shift' not in columns:
                    logging.info("Migrando banco de dados: Adicionando coluna 'shift'")
                    cursor.execute("ALTER TABLE production_records ADD COLUMN shift TEXT DEFAULT 'Unknown'")
                
                # Migração: Adicionar daily_total na tabela current_production para persistência
                cursor.execute("PRAGMA table_info(current_production)")
                columns_curr = [col[1] for col in cursor.fetchall()]
                if 'daily_total' not in columns_curr:
                    logging.info("Migrando banco de dados: Adicionando coluna 'daily_total' em current_production")
                    cursor.execute("ALTER TABLE current_production ADD COLUMN daily_total INTEGER DEFAULT 0")

                # Migração: Adicionar absolute_counter na tabela production_records
                if 'absolute_counter' not in columns:
                    logging.info("Migrando banco de dados: Adicionando coluna 'absolute_counter' em production_records")
                    cursor.execute("ALTER TABLE production_records ADD COLUMN absolute_counter INTEGER DEFAULT 0")
                
                conn.commit()
            logging.info(f"Banco de dados '{DB_FILE}' inicializado e verificado com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao inicializar o banco de dados: {e}")

    @staticmethod
    def insert_production_record(machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter):
        """Insere um novo registro de produção no banco de dados."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO production_records (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter))
                conn.commit()
            logging.info(f"Registro de produção inserido: {machine_name} - Bobina {coil_number}")
        except Exception as e:
            logging.error(f"Erro ao inserir registro de produção: {e}")

    @staticmethod
    def get_production_by_shift(machine_name=None):
        """Calcula a produção total por turno."""
        try:
            query = """
                SELECT machine_name, shift, coil_number, SUM(cups_produced) as total, MAX(timestamp) as last_update, MAX(consumption_type) as consumption_type
                FROM production_records
            """
            params = []
            if machine_name:
                query += " WHERE machine_name = ?"
                params.append(machine_name)
            
            query += " GROUP BY machine_name, shift, coil_number ORDER BY last_update DESC"
            
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção por turno: {e}")
            return []

    @staticmethod
    def get_production_by_lot(machine_name=None, date=None):
        """Calcula a produção total por lote (coil_number)."""
        try:
            query = """
                SELECT machine_name, coil_number, shift, SUM(cups_produced) as total, MIN(timestamp) as start_time, MAX(timestamp) as end_time, MAX(consumption_type) as consumption_type
                FROM production_records
            """
            params = []
            conditions = []
            if machine_name:
                conditions.append("machine_name = ?")
                params.append(machine_name)
            if date:
                conditions.append("date(timestamp) = ?")
                params.append(date)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " GROUP BY machine_name, coil_number ORDER BY end_time DESC LIMIT 50"
            
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção por lote: {e}")
            return []

    @staticmethod
    def update_current_production(machine_name, current_cups, shift, coil_number, feed_value=None, size=None, status='ATIVO', daily_total=0):
        """Atualiza ou insere o status atual de produção."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO current_production 
                (machine_name, current_cups, last_update, shift, coil_number, feed_value, size, status, daily_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (machine_name, current_cups, timestamp, shift, coil_number, feed_value, size, status, daily_total))
                conn.commit()
            logging.debug(f"Status atual de produção atualizado: {machine_name} - {current_cups} copos")
        except sqlite3.OperationalError as e:
            if "no column named daily_total" in str(e):
                logging.warning("Coluna 'daily_total' ausente. Tentando corrigir esquema...")
                DatabaseHandler.init_db()
                try:
                    with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                        INSERT OR REPLACE INTO current_production 
                        (machine_name, current_cups, last_update, shift, coil_number, feed_value, size, status, daily_total)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (machine_name, current_cups, timestamp, shift, coil_number, feed_value, size, status, daily_total))
                        conn.commit()
                except Exception as retry_e:
                    logging.error(f"Erro ao atualizar status após correção de esquema: {retry_e}")
            else:
                logging.error(f"Erro operacional no banco de dados: {e}")
        except Exception as e:
            logging.error(f"Erro ao atualizar status atual de produção: {e}")

    @staticmethod
    def get_current_production(machine_name=None):
        """Retorna o status atual de produção."""
        try:
            query = "SELECT * FROM current_production"
            params = []
            if machine_name:
                query += " WHERE machine_name = ?"
                params.append(machine_name)
            
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar status atual de produção: {e}")
            return []

    @staticmethod
    def get_last_absolute_counter(machine_name):
        """Busca o último contador absoluto registrado para uma máquina."""
        try:
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT absolute_counter FROM production_records
                    WHERE machine_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (machine_name,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logging.error(f"Erro ao buscar último contador absoluto para {machine_name}: {e}")
            return 0

    @staticmethod
    def get_recent_production(limit=100, since_id=None, machine_name=None):
        """
        Busca os registros de produção mais recentes.
        Suporta filtros por ID (para sincronização incremental) e por máquina.
        """
        try:
            query = "SELECT id, timestamp, machine_name, coil_number, cups_produced, consumption_type, shift FROM production_records"
            params = []
            conditions = []

            if since_id is not None:
                conditions.append("id > ?")
                params.append(since_id)

            if machine_name:
                conditions.append("machine_name = ?")
                params.append(machine_name)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção recente: {e}")
            return []

    @staticmethod
    def insert_coil_consumption_record(machine_name, coil_id, lot_number, start_time, end_time, consumed_quantity, unit, production_date, shift, consumption_type):
        """Insere um novo registro de consumo de bobina no banco de dados."""
        try:
            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO coil_consumption_lot (machine_name, coil_id, lot_number, start_time, end_time, consumed_quantity, unit, production_date, shift, consumption_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (machine_name, coil_id, lot_number, start_time.isoformat(), end_time.isoformat(), consumed_quantity, unit, production_date, shift, consumption_type))
                conn.commit()
            logging.info(f"Registro de consumo de bobina inserido: Máquina {machine_name}, Bobina {coil_id}")
        except Exception as e:
            logging.error(f"Erro ao inserir registro de consumo de bobina: {e}")

    @staticmethod
    def get_coil_consumption_records(machine_name=None, start_date=None, end_date=None, lot_number=None):
        """Busca registros de consumo de bobina com filtros."""
        try:
            query = "SELECT * FROM coil_consumption_lot"
            params = []
            conditions = []

            if machine_name:
                conditions.append("machine_name = ?")
                params.append(machine_name)
            if start_date:
                conditions.append("production_date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("production_date <= ?")
                params.append(end_date)
            if lot_number:
                conditions.append("lot_number = ?")
                params.append(lot_number)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY end_time DESC"

            with sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar registros de consumo de bobina: {e}")
            return []
