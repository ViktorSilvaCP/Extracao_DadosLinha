# Modelos de Dados

Esta seção descreve as estruturas de dados (Schemas) utilizadas na API REST.

## ProductionRecord

Representa um registro único de produção ou evento de troca de bobina.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | integer | Identificador único sequencial (Primary Key) |
| `timestamp` | string | Data e hora do registro (ISO 8601) |
| `machine_name` | string | Nome da máquina (ex: `Cupper_22`) |
| `coil_number` | string | Número do lote/bobina |
| `cups_produced` | integer | Quantidade produzida neste registro |
| `consumption_type` | string | Tipo do evento (`Baixa Completa`, `Fechamento Turno`, etc) |
| `shift` | string | Turno de produção (`DIA (07-19)` ou `NOITE (19-07)`) |

```json title="Exemplo JSON"
{
  "id": 1542,
  "timestamp": "2026-01-12 14:30:00",
  "machine_name": "Cupper_22",
  "coil_number": "284043",
  "cups_produced": 12500,
  "consumption_type": "Baixa Completa",
  "shift": "DIA (07-19)"
}
```

## PLCStatus

Representa o estado atual de uma máquina em tempo real.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lote_atual` | string | Lote configurado atualmente |
| `tipo_bobina` | string | Tipo de material (ex: `M`, `L1`) |
| `bobina_saida` | string | Última bobina consumida |
| `status_maquina` | string | Status operacional (`ATIVO`, `PARADO`) |
| `formato` | string | Formato detectado (ex: `350ml_STD`) |
| `feed_rate` | float | Valor lido do avanço da fita |
| `producao_total_acumulada` | integer | Contador total acumulado |
| `conectado` | boolean | Status da conexão com o PLC |

```json title="Exemplo JSON"
{
  "lote_atual": "284043",
  "tipo_bobina": "M",
  "formato": "350ml_STD",
  "feed_rate": 5.5848,
  "producao_total_acumulada": 1250000,
  "conectado": true
}
```

## HealthCheck

Status de saúde do sistema.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | Status geral (`OK` ou `ERROR`) |
| `database` | string | Status da conexão com SQLite |
| `plcs` | object | Mapa com status de cada PLC (`ONLINE`/`OFFLINE`) |
| `timestamp` | string | Data da verificação |

```json title="Exemplo JSON"
{
  "status": "OK",
  "database": "CONNECTED",
  "plcs": {
    "Cupper_22": "ONLINE",
    "Cupper_23": "OFFLINE"
  },
  "timestamp": "2026-01-12 14:30:00"
}
```

## TOTVSResponse

Estrutura de resposta para a integração com ERP.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `count` | integer | Quantidade de registros retornados |
| `results` | list | Lista de objetos ProductionRecord |
| `timestamp` | string | Data da consulta |