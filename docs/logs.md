# Logs do Sistema

O sistema gera logs detalhados para auditoria, depuração e monitoramento de erros.

## Localização dos Arquivos

Os logs são salvos em dois locais simultaneamente para redundância:

1. **Local (Principal)**:
   - Caminho: `c:\programs\Extracao_DadosLinha\logs\`
   - Formato: `plc_system_YYYYMMDD.log`

2. **Rede (Secundário)**:
   - Caminho: `F:\Doc_Comp\(Publico)\Dados\ControlLogix\logs\`
   - Objetivo: Acesso facilitado para equipe de TI sem acesso direto ao servidor.

## Níveis de Log

- **INFO**: Eventos normais de operação (início do sistema, conexão bem-sucedida, e-mail enviado).
- **WARNING**: Situações de alerta que não param o sistema (falha de ping, reconexão, valores fora da tolerância).
- **ERROR**: Falhas críticas (erro de banco de dados, exceções não tratadas, falha de leitura de tag crítica).

## Análise de Problemas Comuns

### 1. Falha de Conexão com PLC
```text
ERROR - [Cupper_22] Falha na leitura: Timeout
WARNING - [Cupper_22] Ping to 10.81.71.11 failed.
```
**Ação**: Verificar cabo de rede, switch e se o PLC está ligado.

### 2. Erro de Banco de Dados
```text
ERROR - [Cupper_23] Falha ao inserir registro no banco de dados: database is locked
```
**Ação**: Verificar se outro processo (como um visualizador de SQLite) está bloqueando o arquivo `production_data.db`.

### 3. Tamanho de Copo Desconhecido
```text
WARNING - [Cupper_22] Feed value 5.8000 outside tolerance ranges
```
**Ação**: Verificar se a máquina está rodando um formato novo não cadastrado no `config.json`.

## Rotação de Logs

Um novo arquivo de log é criado a cada dia (baseado na data no nome do arquivo).

!!! tip "Dica"
    Para monitorar os logs em tempo real no Windows (similar ao `tail -f` do Linux), use o PowerShell:
    `Get-Content logs\plc_system_20260112.log -Wait`