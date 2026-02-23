import sqlite3
import os
import logging
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

DB_FILE = os.getenv("DB_FILE", "production_data.db")
DB_TIMEOUT = 10.0  # Timeout de 20 segundos para operações concorrentes no BD

class DatabaseHandler:
    @staticmethod
    def _get_connection():
        """Centraliza a criação da conexão e configuração do Row Factory."""
        conn = sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        """Inicializa tabelas, índices e realiza migrações automáticas."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                
                # Tabela de registros de produção
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS production_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    machine_name TEXT NOT NULL,
                    coil_number TEXT NOT NULL,
                    cups_produced INTEGER NOT NULL,
                    consumption_type TEXT,
                    shift TEXT NOT NULL,
                    absolute_counter INTEGER DEFAULT 0,
                    coil_type TEXT,
                    can_size TEXT
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
                    consumption_type TEXT NOT NULL,
                    coil_type TEXT
                )
                """)
                
                # Status Real-time para Dashboard da API
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

                # Configuração de lotes (Migrado de config.json)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS lote_config (
                    machine_name TEXT PRIMARY KEY,
                    current_lote TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    bobina_saida TEXT,
                    data_saida TEXT,
                    tipo_bobina TEXT
                )
                """)

                # Configuração de máquinas PLC (Escalabilidade)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS plc_machines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    ip TEXT NOT NULL,
                    slot INTEGER DEFAULT 0,
                    socket_timeout INTEGER DEFAULT 5,
                    main_tag TEXT,
                    feed_tag TEXT,
                    bobina_tag TEXT,
                    trigger_coil_tag TEXT,
                    lote_tag TEXT,
                    stroke_tag TEXT,
                    tool_size_tag TEXT,
                    is_active INTEGER DEFAULT 1
                )
                """)

                # Configuração de destinatários de e-mail
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
                """)

                # Detalharação de produção (Log frequente para auditoria)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS production_detail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    cups_produced INTEGER NOT NULL,
                    feed_value REAL,
                    can_size TEXT
                )
                """)

                # Índices fundamentais para buscas via API (filtros de data e máquina)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_timestamp ON production_records (timestamp);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_machine ON production_records (machine_name);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_lote_config_machine ON lote_config (machine_name);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_detail_machine_time ON production_detail (machine_name, timestamp);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_coil_consumption_machine ON coil_consumption_lot (machine_name);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_coil_consumption_date ON coil_consumption_lot (production_date);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_current_prod_machine ON current_production (machine_name);")
                
                # Verificação de migrações (Casos legados)
                cursor.execute("PRAGMA table_info(production_records)")
                cols = [col[1] for col in cursor.fetchall()]
                if 'can_size' not in cols:
                    cursor.execute("ALTER TABLE production_records ADD COLUMN can_size TEXT")
                if 'coil_type' not in cols:
                    cursor.execute("ALTER TABLE production_records ADD COLUMN coil_type TEXT")
                if 'shift' not in cols:
                    cursor.execute("ALTER TABLE production_records ADD COLUMN shift TEXT DEFAULT 'Unknown'")
                if 'absolute_counter' not in cols:
                    cursor.execute("ALTER TABLE production_records ADD COLUMN absolute_counter INTEGER DEFAULT 0")

                cursor.execute("PRAGMA table_info(coil_consumption_lot)")
                cols_coil = [col[1] for col in cursor.fetchall()]
                if 'coil_type' not in cols_coil:
                    cursor.execute("ALTER TABLE coil_consumption_lot ADD COLUMN coil_type TEXT")

                cursor.execute("PRAGMA table_info(current_production)")
                cols_curr = [col[1] for col in cursor.fetchall()]
                if 'daily_total' not in cols_curr:
                    cursor.execute("ALTER TABLE current_production ADD COLUMN daily_total INTEGER DEFAULT 0")

                conn.commit()
            logging.info("Banco de dados pronto para consumo via API.")
        except Exception as e:
            logging.error(f"Erro no init_db: {e}")

    @staticmethod
    def insert_production_detail(machine_name, cups_produced, feed_value, can_size):
        """Insere um log detalhado de produção no banco de dados."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                INSERT INTO production_detail (machine_name, timestamp, cups_produced, feed_value, can_size)
                VALUES (?, ?, ?, ?, ?)
                """, (machine_name, timestamp, cups_produced, feed_value, can_size))
                conn.commit()
        except Exception as e:
            logging.error(f"Erro ao inserir detalhe de produção: {e}")

    @staticmethod
    def get_all_plcs(only_active=False):
        """Retorna todas as máquinas PLC configuradas."""
        try:
            query = "SELECT * FROM plc_machines"
            if only_active:
                query += " WHERE is_active = 1"
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar PLCs: {e}")
            return []

    @staticmethod
    def save_plc(plc_data):
        """Salva ou atualiza uma máquina PLC."""
        try:
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                INSERT INTO plc_machines (name, ip, slot, socket_timeout, main_tag, feed_tag, bobina_tag, trigger_coil_tag, lote_tag, stroke_tag, tool_size_tag, is_active)
                VALUES (:name, :ip, :slot, :socket_timeout, :main_tag, :feed_tag, :bobina_tag, :trigger_coil_tag, :lote_tag, :stroke_tag, :tool_size_tag, :is_active)
                ON CONFLICT(name) DO UPDATE SET
                    ip=excluded.ip,
                    slot=excluded.slot,
                    socket_timeout=excluded.socket_timeout,
                    main_tag=excluded.main_tag,
                    feed_tag=excluded.feed_tag,
                    bobina_tag=excluded.bobina_tag,
                    trigger_coil_tag=excluded.trigger_coil_tag,
                    lote_tag=excluded.lote_tag,
                    stroke_tag=excluded.stroke_tag,
                    tool_size_tag=excluded.tool_size_tag,
                    is_active=excluded.is_active
                """, plc_data)
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar PLC {plc_data.get('name')}: {e}")
            return False

    @staticmethod
    def delete_plc(name):
        """Remove uma máquina PLC."""
        try:
            with DatabaseHandler._get_connection() as conn:
                conn.execute("DELETE FROM plc_machines WHERE name = ?", (name,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao deletar PLC {name}: {e}")
            return False

    @staticmethod
    def get_all_recipients(only_active=False):
        """Retorna todos os destinatários de e-mail."""
        try:
            query = "SELECT * FROM email_recipients"
            if only_active:
                query += " WHERE is_active = 1"
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar destinatários: {e}")
            return []

    @staticmethod
    def save_recipient(name, email, is_active=1):
        """Salva ou atualiza um destinatário."""
        try:
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                INSERT INTO email_recipients (name, email, is_active)
                VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name=excluded.name,
                    is_active=excluded.is_active
                """, (name, email, is_active))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar destinatário {email}: {e}")
            return False

    @staticmethod
    def delete_recipient(recipient_id):
        """Remove um destinatário."""
        try:
            with DatabaseHandler._get_connection() as conn:
                conn.execute("DELETE FROM email_recipients WHERE id = ?", (recipient_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao deletar destinatário {recipient_id}: {e}")
            return False

    @staticmethod
    def insert_production_record(machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter, coil_type=None, can_size=None):
        """Insere um novo registro de produção no banco de dados."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                INSERT INTO production_records (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter, coil_type, can_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, machine_name, coil_number, cups_produced, consumption_type, shift, absolute_counter, coil_type, can_size))
                conn.commit()
            logging.info(f"Registro inserido: {machine_name} - Lote {coil_number}")
        except Exception as e:
            logging.error(f"Erro ao inserir registro de produção: {e}")

    @staticmethod
    def update_current_production(machine_name, current_cups, shift, coil_number, feed_value=None, size=None, status='ATIVO', daily_total=0):
        """Atualiza status atual usando UPSERT (ON CONFLICT). Essencial para dashboard live."""
        try:
            timestamp = get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                INSERT INTO current_production 
                (machine_name, current_cups, last_update, shift, coil_number, feed_value, size, status, daily_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(machine_name) DO UPDATE SET
                    current_cups=excluded.current_cups,
                    last_update=excluded.last_update,
                    shift=excluded.shift,
                    coil_number=excluded.coil_number,
                    feed_value=excluded.feed_value,
                    size=excluded.size,
                    status=excluded.status,
                    daily_total=excluded.daily_total
                """, (machine_name, current_cups, timestamp, shift, coil_number, feed_value, size, status, daily_total))
                conn.commit()
        except Exception as e:
            logging.error(f"Erro no Upsert do status atual: {e}")

    @staticmethod
    def get_api_production_report(machine_name=None, date=None):
        """
        Endpoint de Reporte Otimizado: Retorna dados formatados para integração externa.
        Aplica a regra de negócio de virada de turno às 06:00:30.
        """
        try:
            calc_prod_date = "CASE WHEN time(timestamp) < '06:00:30' THEN date(timestamp, '-1 day') ELSE date(timestamp) END"
            calc_report_type = """
                CASE 
                    WHEN consumption_type LIKE '%Completa%' THEN 'TOTAL - COMPLETA'
                    WHEN consumption_type LIKE '%Parcial%' THEN 'TOTAL - PARCIAL'
                    ELSE 'TURNO'
                END
            """
            
            query = f"""
                SELECT 
                    id,
                    {calc_prod_date} as data_turno,
                    timestamp as data_hora_real,
                    shift as turno,
                    machine_name as maquina,
                    coil_number as lote,
                    cups_produced as quantidade,
                    can_size as tamanho,
                    coil_type as tipo_bobina,
                    {calc_report_type} as tipo_saida
                FROM production_records
            """
            params = []
            conditions = []
            
            if machine_name:
                conditions.append("maquina = ?")
                params.append(machine_name)
            
            query_with_filter = f"SELECT * FROM ({query}) AS sub"
            
            if date:
                conditions.append("data_turno = ?")
                params.append(date)
            
            if conditions:
                query_with_filter += " WHERE " + " AND ".join(conditions)
            
            query_with_filter += " ORDER BY data_hora_real ASC"

            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query_with_filter, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro no reporte API: {e}")
            return []

    @staticmethod
    def get_production_by_shift(machine_name=None, start_date=None, end_date=None):
        """Legado: Retorna as passagens de produção individuais formatadas para o Reporte ERP."""
        try:
            calc_prod_date = "CASE WHEN time(timestamp) < '06:00:30' THEN date(timestamp, '-1 day') ELSE date(timestamp) END"
            calc_linha = "REPLACE(machine_name, 'Cupper_', '')"
            calc_report_type = """
                CASE 
                    WHEN consumption_type LIKE '%Completa%' THEN 'TOTAL - COMPLETA'
                    WHEN consumption_type LIKE '%Parcial%' THEN 'TOTAL - PARCIAL'
                    ELSE 'TURNO'
                END
            """
            
            query = f"""
                SELECT 
                    {calc_linha} as Linha,
                    machine_name as Maquina, 
                    shift as Turno, 
                    {calc_prod_date} as Dt_turno,
                    coil_number as Lote, 
                    cups_produced as Quantidade, 
                    can_size as Tamanho,
                    {calc_report_type} as Tipo_Reporte,
                    coil_type as Coil_Type,
                    timestamp as Horário_Evento
                FROM production_records
            """
            params = []
            conditions = []
            
            if machine_name:
                conditions.append("machine_name = ?")
                params.append(machine_name)
            
            sub_query = f"SELECT * FROM ({query}) AS sub"
            
            if start_date:
                conditions.append("Dt_turno >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("Dt_turno <= ?")
                params.append(end_date)
            
            final_query = sub_query
            if conditions:
                final_query += " WHERE " + " AND ".join(conditions)
            
            final_query += " ORDER BY Horário_Evento DESC"
            
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(final_query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar reporte de produção: {e}")
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
            
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção por lote: {e}")
            return []

    @staticmethod
    def get_current_production(machine_name=None):
        """Retorna o status atual de produção de uma ou todas as máquinas."""
        try:
            query = "SELECT * FROM current_production"
            params = []
            if machine_name:
                query += " WHERE machine_name = ?"
                params.append(machine_name)
            
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar status atual: {e}")
            return []

    @staticmethod
    def get_last_absolute_counter(machine_name):
        """Busca o último contador absoluto registrado para uma máquina."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT absolute_counter FROM production_records
                    WHERE machine_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (machine_name,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logging.error(f"Erro ao buscar último contador absoluto: {e}")
            return 0

    @staticmethod
    def get_recent_production(limit=100, since_id=None, machine_name=None):
        """Busca os registros de produção mais recentes com lógica de Data_Turno."""
        try:
            calc_prod_date = "CASE WHEN time(timestamp) < '06:00:30' THEN date(timestamp, '-1 day') ELSE date(timestamp) END"
            query = f"""
                SELECT id, {calc_prod_date} as Data_Turno, timestamp as Horário_Evento,
                       timestamp, machine_name, coil_number, cups_produced, consumption_type, shift 
                FROM production_records
            """
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

            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar produção recente: {e}")
            return []

    @staticmethod
    def get_shift_breakdown(machine_name, coil_number, start_time, end_time):
        """Busca a produção detalhada por turno para uma bobina."""
        try:
            calc_prod_date = "CASE WHEN time(timestamp) < '06:00:30' THEN date(timestamp, '-1 day') ELSE date(timestamp) END"
            query = f"""
                SELECT shift, {calc_prod_date} as production_date, SUM(cups_produced) as total_cups
                FROM production_records
                WHERE machine_name = ? AND (coil_number = ? OR coil_number = '') 
                AND timestamp >= ? AND timestamp <= ?
                GROUP BY shift, production_date
                ORDER BY timestamp ASC
            """
            with DatabaseHandler._get_connection() as conn:
                if 'T' in start_time: start_time = start_time.replace('T', ' ').split('.')[0]
                if 'T' in end_time: end_time = end_time.replace('T', ' ').split('.')[0]
                cursor = conn.execute(query, (machine_name, coil_number, start_time, end_time))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro no detalhamento por turno: {e}")
            return []

    @staticmethod
    def insert_coil_consumption_record(machine_name, coil_id, lot_number, start_time, end_time, consumed_quantity, unit, production_date, shift, consumption_type, coil_type=None):
        """Insere registro de consumo de bobina finalizado."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT lot_number FROM coil_consumption_lot 
                    WHERE machine_name = ? ORDER BY id DESC LIMIT 1
                """, (machine_name,))
                last_record = cursor.fetchone()
                
                lot_to_save = lot_number
                if last_record and last_record['lot_number'] == lot_number:
                    lot_to_save = "" 
                
                conn.execute("""
                INSERT INTO coil_consumption_lot (machine_name, coil_id, lot_number, start_time, end_time, consumed_quantity, unit, production_date, shift, consumption_type, coil_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (machine_name, coil_id, lot_to_save, start_time.isoformat(), end_time.isoformat(), consumed_quantity, unit, production_date, shift, consumption_type, coil_type))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao inserir consumo de bobina: {e}")
            return False

    @staticmethod
    def get_coil_consumption_records(machine_name=None, start_date=None, end_date=None, lot_number=None, limit=None):
        """Consulta histórico de consumo de bobinas."""
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
            if limit:
                query += f" LIMIT {limit}"

            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(query, params)
                records = []
                for row in cursor.fetchall():
                    record = dict(row)
                    for field in ['start_time', 'end_time']:
                        if not record.get(field): record[field] = None
                    records.append(record)
                return records
        except Exception as e:
            logging.error(f"Erro ao buscar registros de consumo: {e}")
            return []

    @staticmethod
    def save_lote_to_db(machine_name, lote_value):
        """Salva o número do lote no banco de dados (substitui config.json)."""
        try:
            with DatabaseHandler._get_connection() as conn:
                current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
                
                # Buscar lote anterior
                cursor = conn.execute("SELECT current_lote FROM lote_config WHERE machine_name = ?", (machine_name,))
                row = cursor.fetchone()
                
                if row:
                    lote_anterior = row[0]
                    # UPDATE
                    conn.execute("""
                    UPDATE lote_config 
                    SET current_lote = ?, last_updated = ?, bobina_saida = ?, data_saida = ?
                    WHERE machine_name = ?
                    """, (lote_value, current_time, lote_anterior, current_time, machine_name))
                else:
                    # INSERT
                    conn.execute("""
                    INSERT INTO lote_config (machine_name, current_lote, last_updated)
                    VALUES (?, ?, ?)
                    """, (machine_name, lote_value, current_time))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar lote no DB: {e}")
            return False

    @staticmethod
    def save_bobina_type_to_db(machine_name, tipo_bobina):
        """Salva o tipo da bobina no banco de dados."""
        try:
            with DatabaseHandler._get_connection() as conn:
                conn.execute("""
                UPDATE lote_config 
                SET tipo_bobina = ?
                WHERE machine_name = ?
                """, (tipo_bobina, machine_name))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar tipo de bobina no DB: {e}")
            return False

    @staticmethod
    def get_lote_from_db(machine_name):
        """Lê o lote atual do banco de dados."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT current_lote FROM lote_config WHERE machine_name = ?",
                    (machine_name,)
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
                # Se não encontrar, tenta criar um registro padrão
                logging.warning(f"Nenhum lote encontrado para {machine_name}, criando padrão...")
                try:
                    DatabaseHandler.save_lote_to_db(machine_name, "N/A")
                    return "N/A"
                except:
                    return "Nenhum lote definido"
        except Exception as e:
            logging.error(f"Erro crítico ao buscar lote do DB ({machine_name}): {e}")
            return "Nenhum lote definido"

    @staticmethod
    def get_bobina_type_from_db(machine_name):
        """Lê o tipo de bobina do banco de dados."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT tipo_bobina FROM lote_config WHERE machine_name = ?",
                    (machine_name,)
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
                return None
        except Exception as e:
            logging.error(f"Erro ao buscar tipo de bobina do DB ({machine_name}): {e}")
            return None

    @staticmethod
    def get_bobina_saida_from_db(machine_name):
        """Lê a bobina de saída do banco de dados."""
        try:
            with DatabaseHandler._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT bobina_saida, data_saida FROM lote_config WHERE machine_name = ?",
                    (machine_name,)
                )
                row = cursor.fetchone()
                if row:
                    return {'lote': row[0] or 'Nenhuma bobina saída', 'data_saida': row[1] or ''}
                return {'lote': 'Nenhuma bobina saída', 'data_saida': ''}
        except Exception as e:
            logging.error(f"Erro ao buscar bobina de saída do DB ({machine_name}): {e}")
            return {'lote': 'Nenhuma bobina saída', 'data_saida': ''}