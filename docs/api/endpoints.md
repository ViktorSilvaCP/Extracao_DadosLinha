# Referência de API

## Endpoints Disponíveis

O sistema oferece uma API REST completa com documentação interativa disponível em:

**[http://10.81.5.219:15789/docs](http://10.81.5.219:15789/docs)** :octicons-link-external-16:

---

## Monitoramento em Tempo Real

### Status Individual de Linha

Retorna dados completos de uma linha específica.

!!! example "GET `/api/lote/{plc_name}`"

    === "Request"
        ```http
        GET /api/lote/Cupper_22 HTTP/1.1
        Host: 10.81.5.219:15789
        Accept: application/json
        ```

    === "Response 200"
        ```json
        {
          "lote_atual": "284043",
          "tipo_bobina": "M",
          "bobina_saida": "279254",
          "data_bobina_saida": "06/10/2025 09:44:52",
          "status_maquina": "ATIVO",
          "status_bobina_plc": "Nenhuma Bobina Consumida",
          "formato": "350ml_STD",
          "feed_rate": 5.5848,
          "producao_bobina": 12500,
          "producao_total_acumulada": 1250000,
          "turno_atual": "DIA (07-19)",
          "ultima_atualizacao": "12/01/2026 14:30:00",
          "conectado": true
        }
        ```

    === "Response 404"
        ```json
        {
          "error": "Máquina não encontrada"
        }
        ```

**Parâmetros:**

| Nome | Tipo | Descrição |
|------|------|-----------|
| `plc_name` | string | Nome da máquina (`Cupper_22` ou `Cupper_23`) |

---

### Resumo Geral

Retorna o status consolidado de todas as linhas.

!!! example "GET `/api/lotes`"

    === "Response"
        ```json
        {
          "dados_plcs": {
            "Cupper_22": { /* dados completos */ },
            "Cupper_23": { /* dados completos */ }
          },
          "lotes": {
            "Cupper_22": "284043",
            "Cupper_23": "271435"
          },
          "timestamp": "12/01/2026 14:30:00",
          "total_plcs": 2
        }
        ```

---

## Relatórios de Produção

### Produção por Turno

Consolida a produção total agrupada por turno e linha.

!!! example "GET `/api/producao/turno`"

    **Query Parameters:**
    
    | Nome | Tipo | Obrigatório | Descrição |
    |------|------|-------------|-----------|
    | `machine_name` | string | Não | Filtrar por máquina específica |

    === "Response"
        ```json
        [
          {
            "machine_name": "Cupper_22",
            "shift": "DIA (07-19)",
            "coil_number": "284043",
            "total": 125000,
            "last_update": "2026-01-12 14:30:00"
          },
          {
            "machine_name": "Cupper_22",
            "shift": "NOITE (19-07)",
            "coil_number": "284043",
            "total": 98000,
            "last_update": "2026-01-12 02:15:00"
          }
        ]
        ```

---

### Produção por Lote

Histórico detalhado de cada bobina processada.

!!! example "GET `/api/producao/lote`"

    **Query Parameters:**
    
    | Nome | Tipo | Obrigatório | Descrição |
    |------|------|-------------|-----------|
    | `machine_name` | string | Não | Filtrar por máquina específica |

    === "Response"
        ```json
        [
          {
            "machine_name": "Cupper_22",
            "coil_number": "284043",
            "shift": "DIA (07-19)",
            "total": 223000,
            "start_time": "2026-01-12 07:00:00",
            "end_time": "2026-01-12 14:30:00"
          }
        ]
        ```

---

## Integração ERP (TOTVS)

### Sincronização de Produção

Endpoint otimizado para consumo pelo ERP com suporte a sincronização incremental.

!!! example "GET `/api/totvs/producao`"

    **Query Parameters:**
    
    | Nome | Tipo | Default | Descrição |
    |------|------|---------|-----------|
    | `limit` | integer | 100 | Quantidade máxima de registros |
    | `since_id` | integer | null | ID do último registro sincronizado |

    === "Request"
        ```http
        GET /api/totvs/producao?limit=50&since_id=1234 HTTP/1.1
        Host: 10.81.5.219:15789
        ```

    === "Response"
        ```json
        {
          "count": 50,
          "results": [
            {
              "id": 1235,
              "timestamp": "2026-01-12 14:30:00",
              "machine_name": "Cupper_22",
              "coil_number": "284043",
              "cups_produced": 12500,
              "consumption_type": "Baixa Completa",
              "shift": "DIA (07-19)"
            }
          ],
          "timestamp": "2026-01-12 14:35:00"
        }
        ```

!!! tip "Sincronização Incremental"
    Para evitar duplicação de dados, o TOTVS deve:
    
    1. Armazenar o `id` do último registro processado
    2. Na próxima consulta, usar `since_id={ultimo_id}`
    3. Processar apenas os novos registros retornados

---

## Health Check

### Verificação de Saúde

Monitora o status do sistema e conectividade dos PLCs.

!!! example "GET `/api/health`"

    === "Response (Tudo OK)"
        ```json
        {
          "status": "OK",
          "database": "CONNECTED",
          "plcs": {
            "Cupper_22": "ONLINE",
            "Cupper_23": "ONLINE"
          },
          "timestamp": "2026-01-12 14:30:00"
        }
        ```

    === "Response (Com Problemas)"
        ```json
        {
          "status": "OK",
          "database": "CONNECTED",
          "plcs": {
            "Cupper_22": "OFFLINE",
            "Cupper_23": "ONLINE"
          },
          "timestamp": "2026-01-12 14:30:00"
        }
        ```

!!! warning "Monitoramento Proativo"
    Recomenda-se configurar uma ferramenta de monitoramento (como Grafana ou Zabbix) para consultar este endpoint a cada 30 segundos e alertar em caso de falhas.

---

## Operação de Lotes

### Inserir Novo Lote

Interface para input manual de códigos de lote via formulário web.

!!! example "POST `/enviar_lote`"

    **Form Data:**
    
    | Campo | Tipo | Validação | Descrição |
    |-------|------|-----------|-----------|
    | `lote` | string | Min 3 chars | Código do lote |
    | `plc` | string | Required | `Cupper_22` ou `Cupper_23` |
    | `tipo_bobina` | string | Required | Espessura (L1, L2, L3, M, H1, H2, H3) |

    === "Request"
        ```http
        POST /enviar_lote HTTP/1.1
        Host: 10.81.5.219:15789
        Content-Type: application/x-www-form-urlencoded

        lote=284043&plc=Cupper_22&tipo_bobina=M
        ```

    === "Response 200"
        ```json
        {
          "success": true,
          "message": "✅ Lote 284043 processado com sucesso para Cupper_22.",
          "plc_written": true
        }
        ```

    === "Response 403 (Forbidden)"
        ```json
        {
          "success": false,
          "message": "Acesso Negado: Este terminal não possui um token de autorização válido. Entre em contato com o suporte para autorizar este computador."
        }
        ```

!!! danger "Token Authorization"
    Este endpoint possui uma trava de segurança baseada em **Token (LocalStorage)**. Somente terminais autorizados que possuam o token `CANPACK_PROD_2026_AUTHORIZATION` podem realizar esta operação. Localhost (`127.0.0.1`) é autorizado por padrão.

---

## Identidade e Segurança

### Informações do Cliente

Retorna a identidade resolvida do computador que está realizando a chamada.

!!! example "GET `/api/client_info`"

    === "Response"
        ```json
        {
          "hostname": "PC-PRODUCAO-01",
          "ip": "10.81.19.12",
          "authorized": true
        }
        ```

---

## Códigos de Status HTTP

| Código | Significado | Quando Ocorre |
|--------|-------------|---------------|
| 200 | OK | Requisição bem-sucedida |
| 400 | Bad Request | Parâmetros inválidos |
| 403 | Forbidden | Acesso negado (terminal não autorizado) |
| 404 | Not Found | Recurso não encontrado |
| 500 | Internal Server Error | Erro no servidor |

---

## Rate Limiting

!!! info "Sem Limitação Atual"
    Atualmente o sistema **não possui rate limiting**. Para uso em produção com o TOTVS, recomenda-se:
    
    - Consultas a cada 5-10 segundos para dados em tempo real
    - Sincronização a cada 1 minuto para histórico
    - Health check a cada 30 segundos
