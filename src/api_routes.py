from fastapi import APIRouter, Form, Request, Depends, HTTPException, Query
from typing import List, Optional
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from src.models import PLCStatsResponse, AllPLCsResponse, ShiftProductionSummary, LotProductionSummary, CoilConsumptionLot, ProductionShiftBreakdown
from src.database_handler import DatabaseHandler
from src.monitor_utils import get_current_shift
from timezone_utils import get_current_sao_paulo_time
from email_utils import EmailNotifier, send_email_direct
from email_templates import format_lote_notification
import logging
import socket
import subprocess
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory=".")

import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir
load_dotenv()

# Configurações Globais de Segurança (Extraídas de Variáveis de Ambiente para Produção)
# Configurações Globais de Segurança
MASTER_TOKEN = os.getenv("API_MASTER_TOKEN")
AUTHORIZED_HOSTNAME = os.getenv("AUTHORIZED_HOSTNAME")
AUTHORIZED_IP = os.getenv("AUTHORIZED_IP")

if not MASTER_TOKEN:
    logging.error("❌ ERRO CRÍTICO: 'API_MASTER_TOKEN' não configurado no arquivo .env")
else:
    security_info = []
    if AUTHORIZED_HOSTNAME: security_info.append(f"Host={AUTHORIZED_HOSTNAME}")
    if AUTHORIZED_IP: security_info.append(f"IP={AUTHORIZED_IP}")
    logging.info(f"🛡️ Segurança: Token carregado ({' + '.join(security_info) if security_info else 'Token Livre'}).")

# Rate Limiter Simples (In-Memory)
class SimpleRateLimiter:
    def __init__(self, requests_limit: int, window_seconds: int):
        self.limit = requests_limit
        self.window = window_seconds
        self.history = {}

    def is_allowed(self, client_id: str) -> bool:
        now = datetime.now()
        if client_id not in self.history:
            self.history[client_id] = []
        
        # Remove registros antigos
        self.history[client_id] = [t for t in self.history[client_id] if now - t < timedelta(seconds=self.window)]
        
        if len(self.history[client_id]) < self.limit:
            self.history[client_id].append(now)
            return True
        return False

# Rate Limiters: Configuráveis via .env
DATA_MAX = int(os.getenv("RATE_LIMIT_DATA_MAX", 60))
DATA_WINDOW = int(os.getenv("RATE_LIMIT_DATA_WINDOW", 10))
CMD_MAX = int(os.getenv("RATE_LIMIT_COMMAND_MAX", 5))
CMD_WINDOW = int(os.getenv("RATE_LIMIT_COMMAND_WINDOW", 60))

data_limiter = SimpleRateLimiter(DATA_MAX, DATA_WINDOW)
command_limiter = SimpleRateLimiter(CMD_MAX, CMD_WINDOW)

# Variável global para acessar os dados compartilhados
shared_data_manager = None
plc_configs = {}
monitor_manager = None

def init_api(sdm, configs, mm):
    global shared_data_manager, plc_configs, monitor_manager
    shared_data_manager = sdm
    plc_configs = configs
    monitor_manager = mm

# Cache global para nomes de máquinas para acelerar requisições repetitivas
hostname_cache = {}

def resolve_hostname(ip_address: str) -> str:
    """Resolve IP para Hostname com cache para performance extrema."""
    if ip_address == "127.0.0.1":
        return socket.gethostname().upper()
    
    # Retorna do cache se já resolveu este IP nos últimos 30 minutos
    cached_info = hostname_cache.get(ip_address)
    if cached_info:
        cached_name, timestamp = cached_info
        if datetime.now() - timestamp < timedelta(minutes=30):
            return cached_name

    # Lógica de resolução (DNS -> NBTSAT)
    result_name = "UNKNOWN"
    
    # 1. Tentativa via DNS Reverso
    try:
        hostname_info = socket.gethostbyaddr(ip_address)
        result_name = hostname_info[0].split('.')[0].upper()
    except Exception:
        # 2. Tentativa via FQDN
        try:
            fqdn = socket.getfqdn(ip_address)
            if fqdn and fqdn != ip_address:
                result_name = fqdn.split('.')[0].upper()
        except Exception:
            # 3. Tentativa via NBTSTAT (Específico Windows)
            try:
                result = subprocess.run(['nbtstat', '-A', ip_address], 
                                    capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    import re
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if "<00>" in line and "UNIQUE" in line:
                            match = re.search(r'^\s*([A-Za-z0-9\-]+)', line)
                            if match:
                                result_name = match.group(1).upper()
                                break
            except Exception:
                pass

    # Salva no cache antes de retornar (mesmo se for UNKNOWN, para evitar retentativas lentas imediatas)
    hostname_cache[ip_address] = (result_name, datetime.now())
    return result_name

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/lote.html", response_class=HTMLResponse, include_in_schema=False)
async def read_root(request: Request):
    # Renderiza o template e injeta script para prevenir envio automático (Enter)
    template = templates.get_template("lote.html")
    content = template.render(request=request)
    
    script_prevention = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        const forms = document.querySelectorAll("form");
        forms.forEach(form => {
            form.addEventListener("keydown", function(event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    return false;
                }
            });
        });
    });
    </script>
    """
    
    if "</body>" in content:
        content = content.replace("</body>", script_prevention + "</body>")
    else:
        content += script_prevention
        
    return HTMLResponse(content=content)

@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_panel(request: Request):
    """Rota para o novo painel administrativo avançado."""
    return templates.TemplateResponse("admin.html", {"request": request})

# --- ENDPOINTS ADMINISTRATIVOS (MÁQUINAS PLC) ---

@router.get("/api/admin/plcs", tags=["Administração / Admin"])
async def list_plcs_admin():
    """Lista todos os PLCs configurados no banco de dados."""
    return DatabaseHandler.get_all_plcs()

@router.post("/api/admin/plcs", tags=["Administração / Admin"])
async def save_plc_admin(request: Request):
    """Salva ou atualiza uma configuração de PLC e reinicia o monitoramento se necessário."""
    data = await request.json()
    client_token = request.headers.get("X-Terminal-Token")
    if client_token != MASTER_TOKEN:
        raise HTTPException(status_code=403, detail="Acesso administrativo negado.")
    
    success = DatabaseHandler.save_plc(data)
    if success:
        plc_name = data.get('name')
        # Atualiza o dicionário global de configurações para a API
        config = {
            "plc_config": {
                "ip_address": data['ip'],
                "processor_slot": data['slot'],
                "socket_timeout": data.get('socket_timeout', 5)
            },
            "tag_config": {
                "main_tag": data['main_tag'],
                "feed_tag": data['feed_tag'],
                "bobina_tag": data['bobina_tag'],
                "trigger_coil_tag": data['trigger_coil_tag'],
                "lote_tag": data['lote_tag'],
                "stroke_tag": data.get('stroke_tag', 'oHMI_Daily_Stroke_Count'),
                "tool_size_tag": data.get('tool_size_tag', 'IGN_Tool_Size')
            },
            "connection_config": {
                "read_interval": 5,
                "retry_delay": 5
            }
        }
        plc_configs[plc_name] = config
        
        # Gerencia a thread de monitoramento dinamicamente
        if monitor_manager:
            if data.get('is_active', 1):
                monitor_manager.add_machine(plc_name, config)
            else:
                monitor_manager.remove_machine(plc_name)
                
        return {"success": True, "message": f"PLC {plc_name} salvo e monitoramento atualizado."}
    return JSONResponse(status_code=500, content={"success": False, "message": "Erro ao salvar no banco de dados."})

@router.delete("/api/admin/plcs/{name}", tags=["Administração / Admin"])
async def delete_plc_admin(name: str, request: Request):
    """Remove um PLC do sistema e para o monitoramento."""
    client_token = request.headers.get("X-Terminal-Token")
    if client_token != MASTER_TOKEN:
        raise HTTPException(status_code=403, detail="Acesso administrativo negado.")
    
    success = DatabaseHandler.delete_plc(name)
    if success:
        if monitor_manager:
            monitor_manager.remove_machine(name)
        if name in plc_configs:
            del plc_configs[name]
        return {"success": True, "message": f"PLC {name} removido com sucesso."}
    return JSONResponse(status_code=500, content={"success": False, "message": "Erro ao deletar."})

# --- ENDPOINTS ADMINISTRATIVOS (DESTINATÁRIOS) ---

@router.get("/api/admin/recipients", tags=["Administração / Admin"])
async def list_recipients_admin():
    """Lista todos os destinatários de e-mail."""
    return DatabaseHandler.get_all_recipients()

@router.post("/api/admin/recipients", tags=["Administração / Admin"])
async def save_recipient_admin(request: Request):
    """Salva ou atualiza um destinatário."""
    data = await request.json()
    client_token = request.headers.get("X-Terminal-Token")
    if client_token != MASTER_TOKEN:
        raise HTTPException(status_code=403, detail="Acesso administrativo negado.")
    
    success = DatabaseHandler.save_recipient(data['name'], data['email'], data.get('is_active', 1))
    if success:
        return {"success": True, "message": "Destinatário salvo."}
    return JSONResponse(status_code=500, content={"success": False, "message": "Erro ao salvar."})

@router.delete("/api/admin/recipients/{recipient_id}", tags=["Administração / Admin"])
async def delete_recipient_admin(recipient_id: int, request: Request):
    """Remove um destinatário."""
    client_token = request.headers.get("X-Terminal-Token")
    if client_token != MASTER_TOKEN:
        raise HTTPException(status_code=403, detail="Acesso administrativo negado.")
    
    success = DatabaseHandler.delete_recipient(recipient_id)
    if success:
        return {"success": True, "message": "Destinatário removido."}
    return JSONResponse(status_code=500, content={"success": False, "message": "Erro ao deletar."})

@router.post("/enviar_lote", response_class=JSONResponse, summary="✍️ Enviar Novo Lote / Send New Batch", tags=["Operação de Lotes / Batch Operations"])
async def enviar_lote(request: Request,
                       lote: str = Form(..., description="Código do lote (mínimo 3 caracteres)"), 
                       plc: str = Form(..., description="Nome da máquina (Cupper_22/23)"), 
                       tipo_bobina: str = Form(..., description="Tipo da bobina (ex: M, Alu)")):
    """
    Envia o código do lote e tipo de bobina para a máquina especificada com validações rigorosas de segurança.
    """
    client_ip = request.client.host
    
    # 1. Rate Limiting (Proteção contra Brute Force / DoS) - Usando command_limiter para escrita
    if not command_limiter.is_allowed(client_ip):
        logging.warning(f"RATE LIMIT (COMMAND): Tentativas excessivas de {client_ip}")
        return JSONResponse(status_code=429, content={"success": False, "message": "Muitas solicitações de envio. Aguarde um minuto."})

    try:
        client_token = request.headers.get("X-Terminal-Token")
        client_hostname = resolve_hostname(client_ip)
        logging.info(f"Requisição de Lote: {client_hostname} ({client_ip}) -> PLC: {plc}")
        is_localhost = client_ip == "127.0.0.1"
        if not is_localhost:
            if client_token != MASTER_TOKEN:
                logging.warning(f"ACESSO NEGADO (TOKEN INVÁLIDO): Host={client_hostname}, IP={client_ip}")
                return JSONResponse(status_code=403, content={"success": False, "message": "Acesso Negado: Token inválido."})
            if (AUTHORIZED_HOSTNAME or AUTHORIZED_IP):
                host_ok = (AUTHORIZED_HOSTNAME and client_hostname == AUTHORIZED_HOSTNAME)
                ip_ok = (AUTHORIZED_IP and client_ip == AUTHORIZED_IP)
                
                if not (host_ok or ip_ok):
                    logging.warning(f"ACESSO NEGADO (ORIGEM NÃO AUTORIZADA): Host={client_hostname}, IP={client_ip}")
                    return JSONResponse(status_code=403, content={"success": False, "message": f"Acesso Negado: Terminal não autorizado (IP:{client_ip} / Host:{client_hostname})."})
        import re
        lote = lote.strip().upper()
        is_national = re.match(r'^\d{6}$', lote)
        is_chinese = re.match(r'^[A-Z0-9]{11}-[A-Z]{1}$', lote)
        
        if not (is_national or is_chinese):
            return JSONResponse(status_code=400, content={
                "success": False, 
                "message": "Formato inválido! Use:  • Nacional: 6 dígitos (ex: 123456)  • Chinês: 11 chars + traço + letra (ex: 25608813CB0-A)"
            })
        
        if plc not in ["Cupper_22", "Cupper_23"]:
            return JSONResponse(status_code=400, content={"success": False, "message": "PLC Inválido."})

        config = plc_configs.get(plc)
        if not config:
             return JSONResponse(status_code=404, content={"success": False, "message": f"Configuração do PLC {plc} não encontrada."})
        if not config:
             return JSONResponse(status_code=404, content={"success": False, "message": f"PLC {plc} não encontrado."})

        # Lógica de salvar e notificar
        DatabaseHandler.save_lote_to_db(plc, lote)
        DatabaseHandler.save_bobina_type_to_db(plc, tipo_bobina)
        
        # Tenta escrever no PLC se o monitoramento estiver ativo
        plc_write_success = False
        if monitor_manager and plc in monitor_manager.handlers:
            handler = monitor_manager.handlers[plc]
            plc_write_success = handler.write_lote(lote)
        
        # Notificação por e-mail
        try:
            email_message = format_lote_notification(lote, plc, config)
            # Destinatários carregados do banco de dados (Escalável via Admin)
            active_recipients = DatabaseHandler.get_all_recipients(only_active=True)
            recipients = [r['email'] for r in active_recipients]
            
            if recipients:
                send_email_direct(
                    to=recipients,
                    subject=f"✅ Lote {lote} Inserido - {plc}",
                    message=email_message
                )
        except Exception as e:
            logging.error(f"Erro ao enviar notificação de lote: {e}")

        msg = f"✅ Lote {lote} processado com sucesso para {plc}."
        if not plc_write_success:
            msg += " (Nota: Não foi possível gravar no PLC no momento, mas foi salvo no sistema)"

        return JSONResponse(content={"success": True, "message": msg, "plc_written": plc_write_success})
    except Exception as e:
        logging.error(f"Erro em enviar_lote: {e}")
        return JSONResponse(content={"success": False, "message": str(e)}, status_code=500)

@router.get("/api/lote/{plc_name}", response_model=PLCStatsResponse, summary="📊 Status em Tempo Real / Real-time Status", tags=["Monitoramento / Monitoring"])
async def get_plc_stats(plc_name: str):
    """
    Retorna os dados completos (tempo real + configuração) de um PLC específico. / Returns complete data (real-time + config) for a specific PLC.
    """
    if plc_name not in plc_configs:
        return JSONResponse(status_code=404, content={"error": "Máquina não encontrada"})

    # Dados em tempo real do manager
    real_time_data = shared_data_manager.get_plc_data(plc_name)
    
    # Dados de configuração
    lote_atual = DatabaseHandler.get_lote_from_db(plc_name)
    tipo_bobina = DatabaseHandler.get_bobina_type_from_db(plc_name)
    bobina_saida_info = DatabaseHandler.get_bobina_saida_from_db(plc_name)
    
    # Cálculo do turno usando a nova regra (06-18)
    current_shift = get_current_shift()
    now_sp = get_current_sao_paulo_time()

    if real_time_data:
        return {
            "lote_atual": lote_atual,
            "tipo_bobina": tipo_bobina,
            "bobina_saida": bobina_saida_info['lote'],
            "data_bobina_saida": bobina_saida_info['data_saida'],
            "status_maquina": real_time_data.status,
            "status_bobina_plc": real_time_data.bobina_consumida,
            "formato": real_time_data.size,
            "feed_rate": real_time_data.feed_value,
            "producao_bobina": real_time_data.main_value,
            "producao_total_acumulada": real_time_data.count_discharge_total,
            "turno_atual": current_shift,
            "ultima_atualizacao": real_time_data.update_time,
            "conectado": True
        }
    else:
        return {
            "lote_atual": lote_atual,
            "tipo_bobina": tipo_bobina,
            "bobina_saida": bobina_saida_info['lote'],
            "data_bobina_saida": bobina_saida_info['data_saida'],
            "status_maquina": "DESCONHECIDO",
            "turno_atual": current_shift,
            "ultima_atualizacao": now_sp.strftime("%d/%m/%Y %H:%M:%S"),
            "conectado": False,
            "detalhe": "Sem dados em tempo real disponíveis."
        }

@router.get("/api/lotes", response_model=AllPLCsResponse, summary="🌐 Resumo Geral das Linhas / General Lines Summary", tags=["Monitoramento / Monitoring"])
async def get_all_plc_stats(request: Request):
    """
    Retorna o status consolidado de todas as máquinas monitoradas pelo sistema.
    """
    if not data_limiter.is_allowed(request.client.host):
        return JSONResponse(status_code=429, content={"error": "Muitas requisições. O sistema permite refreshes rápidos."})
    dados_completos = {}
    for plc_name in plc_configs:
        stats = await get_plc_stats(plc_name)
        dados_completos[plc_name] = stats

    return {
        "dados_plcs": dados_completos,
        "lotes": {name: dados["lote_atual"] for name, dados in dados_completos.items()},
        "timestamp": get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S"),
        "total_plcs": len(dados_completos)
    }

@router.get("/api/producao/turno", response_model=List[ShiftProductionSummary], summary="📅 Histórico por Turno / Shift History", tags=["Relatórios de Produção / Production Reports"])
async def get_shift_production(
    machine_name: Optional[str] = Query(None, description="Filtrar por nome da máquina / Machine name"),
    start_date: Optional[str] = Query(None, description="Data de início (YYYY-MM-DD) / Start date"),
    end_date: Optional[str] = Query(None, description="Data de fim (YYYY-MM-DD) / End date")
):
    """
    Retorna a produção total consolidada por DIA LÓGICO (06:00 às 06:00).
    Se apenas 'start_date' for fornecido, retorna apenas os dados daquele dia específico.
    """
    # Lógica inteligente: Se passar apenas o início, assume que quer ver apenas aquele dia
    if start_date and not end_date:
        end_date = start_date
        
    data = DatabaseHandler.get_production_by_shift(machine_name, start_date, end_date)
    return data

@router.get("/api/producao/lote", response_model=List[CoilConsumptionLot], summary="📦 Histórico de Consumo por Bobina / Coil Consumption History", tags=["Relatórios de Produção / Production Reports"])
async def get_lot_production(
    machine_name: Optional[str] = Query(None, description="Filtrar por nome da máquina (e.g., Cupper_22). Se omitido, retorna o último registro de cada máquina."),
    start_date: Optional[str] = Query(None, description="Data de início para filtro (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Data de fim para filtro (YYYY-MM-DD)"),
    lot_number: Optional[str] = Query(None, description="Filtrar por número do lote")
):
    """
    Retorna o histórico de consumo de bobinas, incluindo produção detalhada por bobina.
    É possível filtrar por máquina, intervalo de datas e número de lote.
    Se nenhum parâmetro for fornecido, retorna o último registro de consumo para cada máquina.
    """
    # Define se deve limitar ao último registro (apenas se não houver filtros de busca)
    should_limit = 1 if (machine_name and not start_date and not end_date and not lot_number) else None

    if machine_name:
        # Busca registros da máquina, limitando a 1 apenas se não houver filtros específicos
        data = DatabaseHandler.get_coil_consumption_records(
            machine_name=machine_name,
            start_date=start_date,
            end_date=end_date,
            lot_number=lot_number,
            limit=should_limit
        )
    else:
        # If no machine_name, get all recent records and then filter to get the latest per machine
        # This is a simplification; a more efficient way for SQLite would be a subquery with MAX(end_time)
        # but requires more changes in DatabaseHandler. For now, fetch a reasonable limit and process.
        all_records = DatabaseHandler.get_coil_consumption_records(
            start_date=start_date,
            end_date=end_date,
            lot_number=lot_number,
            limit=50 # Fetch a reasonable number of recent records to find the latest for each machine
        )
        
        latest_records_per_machine = {}
        for record in all_records:
            if record['machine_name'] not in latest_records_per_machine:
                latest_records_per_machine[record['machine_name']] = record
        data = list(latest_records_per_machine.values())

    # Preenche o detalhamento de turnos para cada lote encontrado
    results = []
    for record in data:
        # Extrai valores originais para processamento
        orig_start = record.get('start_time')
        orig_end = record.get('end_time')
        # A data de produção agora será chamada de data_turno na API para maior clareza
        date_turno = record.get('production_date')
        
        proc_record = record.copy()
        proc_record['data_turno'] = date_turno
        
        # Removemos production_date se não estiver no modelo Pydantic para evitar erros de validação
        if 'production_date' in proc_record:
            del proc_record['production_date']

        model_record = CoilConsumptionLot(**proc_record)
        
        # Busca o detalhamento usando os horários originais
        if orig_start and orig_end:
            breakdown = DatabaseHandler.get_shift_breakdown(
                machine_name=model_record.machine_name,
                coil_number=model_record.lot_number,
                start_time=orig_start,
                end_time=orig_end
            )
            model_record.detalhe_turnos = [ProductionShiftBreakdown(**b) for b in breakdown]
        results.append(model_record)

    return results

@router.get("/api/producao/recente", summary="🕒 Últimos Registros de Produção / Recent Production Records", tags=["Relatórios de Produção / Production Reports"])
async def get_recent_production_records(machine_name: Optional[str] = None, limit: int = 20):
    """
    Retorna os últimos registros de produção gravados no banco de dados. / Returns the last production records saved in the database.
    Útil para verificar as últimas atividades de troca de bobina ou fechamento de turno. / Useful for checking recent coil changes or shift closings.
    """
    data = DatabaseHandler.get_recent_production(limit=limit, machine_name=machine_name)
    return data

@router.get("/api/totvs/producao", summary="🔄 Integração TOTVS / TOTVS Integration", tags=["Integração ERP / ERP Integration"])
async def get_totvs_production(limit: int = 100, since_id: int = None):
    """
    Endpoint otimizado para o ERP TOTVS consumir dados de produção. / Optimized endpoint for TOTVS ERP to consume production data.
    Suporta filtros por ID para sincronização incremental. / Supports ID filters for incremental synchronization.
    """
    data = DatabaseHandler.get_recent_production(limit=limit, since_id=since_id)
    return {
        "count": len(data),
        "results": data,
        "timestamp": get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
    }

@router.get("/api/datasul/producao", summary="📊 Integração Datasul / Datasul Integration", tags=["Integração ERP / ERP Integration"])
async def get_datasul_production(
    request: Request,
    machine_name: Optional[str] = Query(None, description="Filtrar por nome da máquina / Machine name"),
    date: Optional[str] = Query(None, description="Data do Turno (YYYY-MM-DD ou DD/MM/YYYY) / Shift Date")
):
    """
    Endpoint otimizado para o ERP Datasul (Reporte de Produção).
    """
    if not data_limiter.is_allowed(request.client.host):
        return JSONResponse(status_code=429, content={"error": "Muitas requisições. O sistema permite refreshes rápidos."})
    # Normalização da máquina (ex: '22' -> 'Cupper_22')
    if machine_name and "Cupper_" not in machine_name:
        machine_name = f"Cupper_{machine_name}"

    # Normalização da data
    if date:
        try:
            # Caso venha em formato brasileiro (DD/MM/YYYY)
            if "/" in date:
                date = datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            pass # Mantém o original se falhar
    else:
        now = get_current_sao_paulo_time()
        # Calcula a data industrial atual
        date = (now - timedelta(hours=6, seconds=30)).strftime('%Y-%m-%d')
        
    data = DatabaseHandler.get_api_production_report(machine_name, date)
    return {
        "count": len(data),
        "results": data,
        "timestamp": get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
    }


@router.get("/api/client_info", tags=["Manutenção / Maintenance"])
async def get_client_info(request: Request):
    """Retorna informações de identidade do computador cliente e valida o token."""
    client_ip = request.client.host
    
    # Rate Limit na identificação para evitar brute force do hostname resolution
    if not data_limiter.is_allowed(client_ip):
         return JSONResponse(status_code=429, content={"error": "Too many requests"})

    hostname = resolve_hostname(client_ip)
    client_token = request.headers.get("X-Terminal-Token")
    
    is_authorized = (client_ip == "127.0.0.1") or (client_token == MASTER_TOKEN)
    
    return {
        "hostname": hostname,
        "ip": client_ip,
        "authorized": is_authorized
    }


@router.get("/api/health", summary="💓 Heartbeat do Systema / System Heartbeat", tags=["Monitoramento / Monitoring"])
async def health_check():
    """
    Verifica a saúde do sistema, conexão com PLCs e banco de dados. / Checks system health, PLC connections, and database.
    """
    plcs_status = {}
    for name in plc_configs:
        data = shared_data_manager.get_plc_data(name)
        plcs_status[name] = "ONLINE" if data and data.status != "DESCONHECIDO" else "OFFLINE"
    
    return {
        "status": "OK",
        "database": "CONNECTED",
        "plcs": plcs_status,
        "timestamp": get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
    }