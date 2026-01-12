from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from timezone_utils import get_current_sao_paulo_time

class PLCReportData:
    def __init__(self, plc_name, feed_value, size, main_value, total_cups,
                 update_time=None, status='ATIVO', bobina_saida=None, bobina_consumida=None,
                 attachment_filename=None, attachment_content=None, temp_attachment_path=None,
                 current_shift=None, count_discharge_total=0):
        self.plc_name = plc_name
        self.feed_value = feed_value
        self.size = size
        self.main_value = main_value
        self.total_cups = total_cups
        self.update_time = update_time or get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
        self.status = status
        self.bobina_saida = bobina_saida
        self.bobina_consumida = bobina_consumida
        self.attachment_filename = attachment_filename
        self.attachment_content = attachment_content
        self.temp_attachment_path = temp_attachment_path
        self.current_shift = current_shift
        self.count_discharge_total = count_discharge_total

class PLCStatsResponse(BaseModel):
    lote_atual: str = Field(..., description="Número do lote atualmente em produção")
    tipo_bobina: Optional[str] = Field(None, description="Tipo da bobina sendo utilizada")
    bobina_saida: str = Field(..., description="Número do lote da última bobina finalizada")
    data_bobina_saida: str = Field(..., description="Data e hora em que a última bobina foi finalizada")
    status_maquina: str = Field("ATIVO", description="Status operacional da máquina")
    status_bobina_plc: Optional[str] = Field(None, description="Status da bobina reportado pelo PLC")
    formato: Optional[str] = Field(None, description="Formato/tamanho do copo")
    feed_rate: Optional[float] = Field(None, description="Taxa de alimentação (polegadas)")
    producao_bobina: Optional[int] = Field(None, description="Total de copos produzidos pela bobina atual")
    producao_total_acumulada: Optional[int] = Field(None, description="Produção total acumulada")
    turno_atual: str = Field(..., description="Turno de trabalho atual")
    ultima_atualizacao: str = Field(..., description="Data e hora da última coleta de dados")
    conectado: bool = Field(..., description="Indica se a conexão com o PLC está ativa")
    detalhe: Optional[str] = Field(None, description="Informações adicionais ou erros")

class AllPLCsResponse(BaseModel):
    dados_plcs: Dict[str, PLCStatsResponse] = Field(..., description="Dados detalhados por PLC")
    lotes: Dict[str, str] = Field(..., description="Mapeamento simplificado de PLC para Lote")
    timestamp: str = Field(..., description="Horário do servidor no momento da resposta")
    total_plcs: int = Field(..., description="Quantidade total de PLCs processados")

class ShiftProductionSummary(BaseModel):
    machine_name: str = Field(..., description="Nome da linha de produção (ex: Cupper 22)")
    shift: str = Field(..., description="Turno em que a produção ocorreu (DIA/NOITE)")
    coil_number: str = Field(..., description="Número da bobina processada")
    total: int = Field(..., description="Quantidade total de copos produzidos no turno para esta bobina")
    last_update: str = Field(..., description="Data e hora do último registro neste turno")

class LotProductionSummary(BaseModel):
    machine_name: str = Field(..., description="Nome da linha de produção")
    coil_number: str = Field(..., description="Número identificador do lote/bobina")
    shift: str = Field(..., description="Turno principal de processamento")
    total: int = Field(..., description="Produção total consolidada para este lote")
    start_time: str = Field(..., description="Horário de início do processamento do lote")
    end_time: str = Field(..., description="Horário de término do processamento do lote")
