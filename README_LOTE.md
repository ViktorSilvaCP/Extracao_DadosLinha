# 🚀 Sistema de Extração de Dados e Controle de Lotes - CANPACK BRASIL

## 📋 Visão Geral
Este sistema avançado de monitoramento industrial permite a coleta em tempo real de dados de produção das linhas **Cupper_22** e **Cupper_23**. Ele gerencia o ciclo de vida das bobinas, registra a produção por turno e fornece uma API documentada para integração com o **ERP TOTVS**.

---

## 🛠️ Tecnologias Utilizadas
- **Backend**: FastAPI (Python 3.13)
- **Comunicação Industrial**: Pylogix (Protocolo EtherNet/IP)
- **Banco de Dados**: SQLite (Persistência de produção)
- **Arquitetura**: Modular (Diretório `src/`)
- **Documentação**: Swagger UI / OpenAPI

---

## 🏗️ Estrutura do Sistema

### 1. Monitoramento e Lógica de Negócio
A lógica é **estritamente baseada no bit `Bobina_Trocada`**:
- O sistema monitora as tags do PLC continuamente.
- Quando o bit `Bobina_Trocada` (Bool) vai para `1`, o sistema captura:
    - Produção acumulada da bobina (`Count_discharge`).
    - Número do lote/serial da bobina.
    - Turno atual (regras 07-19 / 19-07).
    - Status de consumo.
- Os dados são salvos no banco de dados `production_data.db` e um log detalhado é gerado.

### 2. Definição de Turnos
O sistema segue a regra de turnos de 12 horas:
- **Turno DIA**: 07:00 às 18:59:59
- **Turno NOITE**: 19:00 às 06:59:59 (do dia seguinte)

---

## 🌐 APIs e Documentação Online
O sistema conta com uma documentação interativa completa (Swagger).
- **URL da Documentação**: `http://10.81.5.219:15789/docs`

### Principais Endpoints:

#### 📊 Monitoramento (Tempo Real)
- **GET `/api/lote/{plc_name}`**: Retorna o status atual da máquina, produção da bobina em curso e conexão.
- **GET `/api/lotes`**: Resumo geral de todas as linhas ativas.

#### 📅 Relatórios de Produção
- **GET `/api/producao/turno`**: Produção total consolidada por turno e linha. Exibe o último lote e total de copos.
- **GET `/api/producao/lote`**: Histórico detalhado de cada bobina processada, incluindo horários de início e fim.

#### ✍️ Operação de Lotes
- **POST `/enviar_lote`**: Interface para input manual de novos códigos de lote e tipo de bobina.

#### 🔄 Integração ERP (TOTVS)
- **GET `/api/totvs/producao`**: Endpoint especializado para sincronização incremental com o TOTVS. Suporta parâmetros `limit` e `since_id`.
- **GET `/api/health`**: Check de saúde do sistema e conectividade dos PLCs para ferramentas de monitoramento.

---

## 🛠️ Manutenção e Confiabilidade

### 1. Execução como Serviço do Windows
Para garantir que o sistema inicie com o Windows e se recupere de falhas, utilize o **NSSM** (Non-Sucking Service Manager):
1. Baixe o `nssm.exe`.
2. No terminal: `nssm install CanpackPLCMonitor`.
3. Configure o *Path* para o executável do Python e o *Startup directory* para a raiz do projeto.
4. Argumento: `app.py`.

### 2. Backup Automático
O sistema realiza um backup preventivo do banco de dados (`production_data.db`) toda vez que é iniciado. Os backups são armazenados na pasta `backups/`, mantendo apenas os 10 mais recentes.

### 3. Logs Industriais
Os logs de erros e alertas de conexão são salvos em:
`F:\Doc_Comp\(Publico)\Dados\ControlLogix\logs` (ou pasta local `/logs` se o mapeamento falhar).

---

## 📂 Organização de Arquivos (Modular)
- `app.py`: Ponto de entrada e configuração do servidor.
- `src/api_routes.py`: Definição de todas as rotas da API.
- `src/plc_manager.py`: Gerenciamento das threads de monitoramento.
- `src/database_handler.py`: Consultas e inserções no banco de dados.
- `src/models.py`: Modelos de dados Pydantic para validação.
- `src/monitor_utils.py`: Funções auxiliares de turno e travas de segurança.
- `plc_handler.py`: Comunicação direta com o hardware (ControlLogix).

---

## 🖥️ Logs e Diagnóstico
O sistema foi configurado para ser silencioso, registrando apenas eventos críticos:
- **Log Local**: `/logs/plc_system_YYYYMMDD.log`
- **Nível de Log**: `ERROR` (Apenas falhas críticas e interrupções de conexão).
- **Modo Debug**: Logs de produção detalhados estão disponíveis em nível `DEBUG` para manutenção.

---

## 📧 Notificações
O sistema envia notificações automáticas via e-mail para os responsáveis em casos de:
- Troca de bobina (Relatório de produção anexo).
- Inserção manual de novo lote.
- Alertas de valores de `Feed` fora da tolerância configurada.

---

## 📞 Suporte Técnico
**Responsável**: Victor Nascimento Silva
**Email**: victor.nascimento@canpack.com
**Localização**: Canpack Brasil - Tecnologia