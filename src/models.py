from pydantic import BaseModel, Field
from typing import Optional, Dict, List
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
    lote_atual: str = Field(..., description="Número do lote atualmente em produção / Current batch number in production")
    tipo_bobina: Optional[str] = Field(None, description="Tipo da bobina sendo utilizada / Coil type being used")
    bobina_saida: str = Field(..., description="Número do lote da última bobina finalizada / Last finished coil batch number")
    data_bobina_saida: str = Field(..., description="Data e hora em que a última bobina foi finalizada / Date and time when the last coil was finished")
    status_maquina: str = Field("ATIVO", description="Status operacional da máquina / Machine operational status")
    status_bobina_plc: Optional[str] = Field(None, description="Status da bobina reportado pelo PLC / Coil status reported by PLC")
    formato: Optional[str] = Field(None, description="Formato/tamanho do copo / Cup size/format")
    feed_rate: Optional[float] = Field(None, description="Taxa de alimentação (polegadas) / Feed rate (inches)")
    producao_bobina: Optional[int] = Field(None, description="Total de copos produzidos pela bobina atual / Total cups produced by current coil")
    producao_total_acumulada: Optional[int] = Field(None, description="Produção total acumulada / Total accumulated production")
    turno_atual: str = Field(..., description="Turno de trabalho atual / Current work shift")
    ultima_atualizacao: str = Field(..., description="Data e hora da última coleta de dados / Last data collection timestamp")
    conectado: bool = Field(..., description="Indica se a conexão com o PLC está ativa / Indicates if PLC connection is active")
    detalhe: Optional[str] = Field(None, description="Informações adicionais ou erros / Additional info or errors")

class AllPLCsResponse(BaseModel):
    dados_plcs: Dict[str, PLCStatsResponse] = Field(..., description="Dados detalhados por PLC / Detailed data per PLC")
    lotes: Dict[str, str] = Field(..., description="Mapeamento simplificado de PLC para Lote / Simplified PLC to Batch mapping")
    timestamp: str = Field(..., description="Horário do servidor no momento da resposta / Server timestamp")
    total_plcs: int = Field(..., description="Quantidade total de PLCs processados / Total PLCs processed")

class ShiftProductionSummary(BaseModel):
    Linha: str = Field(..., description="Número da linha (ex: 22, 23)")
    Maquina: str = Field(..., description="Nome da máquina (ex: Cupper_22)")
    Turno: str = Field(..., description="Turno de produção (A, B ou DIA, NOITE)")
    Dt_turno: str = Field(..., description="Data lógica de produção (YYYY-MM-DD)")
    Lote: str = Field(..., description="Número do lote/bobina")
    Quantidade: int = Field(..., description="Quantidade de copos (Delta se turno, Total se bobina)")
    Tamanho: Optional[str] = Field(None, description="Tamanho/formato do copo")
    Tipo_Reporte: Optional[str] = Field(None, description="Tipo: Turno ou Total")
    Coil_Type: Optional[str] = Field(None, description="Tipo do material")
    Horário_Evento: Optional[str] = Field(None, description="Horário exato do registro")

class LotProductionSummary(BaseModel):
    machine_name: str = Field(..., description="Nome da linha de produção / Production line name")
    coil_number: str = Field(..., description="Número identificador do lote/bobina / Batch/Coil identifier number")
    shift: str = Field(..., description="Turno principal de processamento / Main processing shift")
    total: int = Field(..., description="Produção total consolidada para este lote / Consolidated total production for this batch")
    start_time: str = Field(..., description="Horário de início do processamento do lote / Batch processing start time")
    end_time: str = Field(..., description="Horário de término do processamento do lote / Batch processing end time")
    consumption_type: Optional[str] = Field(None, description="Tipo de consumo da bobina (Completa/Parcial) / Coil consumption type")

class ProductionShiftBreakdown(BaseModel):
    shift: str
    production_date: str
    total_cups: int

class CoilConsumptionLot(BaseModel):
    id: Optional[int] = Field(None, description="ID único do registro de consumo de bobina")
    machine_name: str = Field(..., description="Nome da máquina (e.g., Cupper_22)")
    coil_id: str = Field(..., description="Identificador único da bobina")
    lot_number: str = Field(..., description="Número do lote associado à bobina")
    data_turno: str = Field(..., description="Data de produção (Turno em formato YYYY-MM-DD)")
    start_time: Optional[datetime] = Field(None, description="Timestamp completo de início para auditoria")
    end_time: Optional[datetime] = Field(None, description="Timestamp completo de fim para auditoria")
    consumed_quantity: int = Field(..., description="Quantidade produzida da bobina")
    unit: str = Field(..., description="Unidade de medida (e.g., 'cups')")
    shift: str = Field(..., description="Turno de consumo (DIA/NOITE)")
    consumption_type: str = Field(..., description="Tipo de consumo (Completa/Parcial)")
    coil_type: Optional[str] = Field(None, description="Tipo da bobina (L1, L2, M1, H1, etc.)")
    detalhe_turnos: Optional[List['ProductionShiftBreakdown']] = Field(None, description="Detalhamento da produção fatiado por turno")
