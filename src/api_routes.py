from fastapi import APIRouter, Form, Request, Depends, HTTPException
from typing import List
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from src.models import PLCStatsResponse, AllPLCsResponse, ShiftProductionSummary, LotProductionSummary
from src.config_handler import (
    load_config, save_lote_to_config, save_bobina_type_to_config,
    get_lote_from_config, get_bobina_type_from_config, get_bobina_saida_from_config
)
from src.monitor_utils import get_current_shift
from src.database_handler import DatabaseHandler
from timezone_utils import get_current_sao_paulo_time
from email_utils import EmailNotifier, send_email_direct
from email_templates import format_lote_notification
import logging

router = APIRouter()
templates = Jinja2Templates(directory=".")

# Variável global para acessar os dados compartilhados (será injetada pelo app principal)
shared_data_manager = None
plc_configs = {}

def init_api(sdm, configs):
    global shared_data_manager, plc_configs
    shared_data_manager = sdm
    plc_configs = configs

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root(request: Request):
    return templates.TemplateResponse("lote.html", {"request": request})

@router.post("/enviar_lote", response_class=HTMLResponse, summary="✍️ Enviar Novo Lote", tags=["Operação de Lotes"])
async def enviar_lote(lote: str = Form(..., description="Código do lote (mínimo 3 caracteres)"), 
                       plc: str = Form(..., description="Nome da máquina (Cupper_22/23)"), 
                       tipo_bobina: str = Form(..., description="Tipo da bobina (ex: M, Alu)")):
    """
    Envia o código do lote e tipo de bobina para a máquina especificada.
    Valida o lote, salva na configuração local e tenta enviar para o PLC.
    """
    try:
        if not lote or len(lote.strip()) < 3:
            raise HTTPException(status_code=400, detail="O código do lote deve ter pelo menos 3 caracteres.")
        
        lote = lote.strip().upper()
        config = plc_configs.get(plc)
        if not config:
             raise HTTPException(status_code=404, detail=f"PLC {plc} não encontrado.")

        # Lógica de salvar e notificar
        save_lote_to_config(plc, lote)
        save_bobina_type_to_config(plc, tipo_bobina)
        
        # Notificação por e-mail
        try:
            email_message = format_lote_notification(lote, plc, config)
            send_email_direct(
                to=["victor.nascimento@canpack.com"],
                subject=f"✅ Lote {lote} Inserido - {plc}",
                message=email_message
            )
        except Exception as e:
            logging.error(f"Erro ao enviar notificação de lote: {e}")

        return HTMLResponse(content=f"Lote {lote} processado com sucesso para {plc}.")
    except Exception as e:
        logging.error(f"Erro em enviar_lote: {e}")
        return HTMLResponse(content=f"Erro: {str(e)}", status_code=500)

@router.get("/api/lote/{plc_name}", response_model=PLCStatsResponse, summary="📊 Status em Tempo Real", tags=["Monitoramento"])
async def get_plc_stats(plc_name: str):
    """
    Retorna os dados completos (tempo real + configuração) de um PLC específico.
    """
    if plc_name not in plc_configs:
        return JSONResponse(status_code=404, content={"error": "Máquina não encontrada"})

    # Dados em tempo real do manager
    real_time_data = shared_data_manager.get_plc_data(plc_name)
    
    # Dados de configuração
    lote_atual = get_lote_from_config(plc_name)
    tipo_bobina = get_bobina_type_from_config(plc_name)
    bobina_saida_info = get_bobina_saida_from_config(plc_name)
    
    # Cálculo do turno usando a nova regra (07-19)
    current_shift = get_current_shift()

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
            "producao_bobina": real_time_data.count_discharge_total,
            "producao_total_acumulada": real_time_data.total_cups,
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

@router.get("/api/lotes", response_model=AllPLCsResponse, summary="🌐 Resumo Geral das Linhas", tags=["Monitoramento"])
async def get_all_plc_stats():
    """
    Retorna o status consolidado de todas as máquinas monitoradas pelo sistema.
    """
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

@router.get("/api/producao/turno", response_model=List[ShiftProductionSummary], summary="📅 Histórico por Turno", tags=["Relatórios de Produção"])
async def get_shift_production(machine_name: str = None):
    """
    Retorna a produção total agrupada por turno e linha. Exibe também o último lote registrado.
    """
    data = DatabaseHandler.get_production_by_shift(machine_name)
    return data

@router.get("/api/producao/lote", response_model=List[LotProductionSummary], summary="📦 Histórico por Lote/Bobina", tags=["Relatórios de Produção"])
async def get_lot_production(machine_name: str = None):
    """
    Retorna a produção detalhada de cada lote (bobina), incluindo o turno em que ocorreu.
    """
    data = DatabaseHandler.get_production_by_lot(machine_name)
    return data

@router.get("/api/totvs/producao", summary="🔄 Integração TOTVS", tags=["Integração ERP"])
async def get_totvs_production(limit: int = 100, since_id: int = None):
    """
    Endpoint otimizado para o ERP TOTVS consumir dados de produção.
    Suporta filtros por ID para sincronização incremental.
    """
    data = DatabaseHandler.get_recent_production(limit=limit, since_id=since_id)
    return {
        "count": len(data),
        "results": data,
        "timestamp": get_current_sao_paulo_time().strftime("%Y-%m-%d %H:%M:%S")
    }

@router.get("/api/health", summary="💓 Heartbeat do Sistema", tags=["Monitoramento"])
async def health_check():
    """
    Verifica a saúde do sistema, conexão com PLCs e banco de dados.
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
