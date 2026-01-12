# Guia de Instalação

Este guia detalha como instalar e configurar o Sistema de Monitoramento PLC.

---

## Pré-requisitos

### Software Necessário

- [x] **Python 3.13+** - [Download](https://www.python.org/downloads/)
- [x] **Git** (opcional) - Para versionamento
- [x] **NSSM** (opcional) - Para executar como serviço Windows

### Requisitos de Rede

- Acesso à rede industrial (10.81.x.x)
- Conectividade com PLCs nas portas EtherNet/IP
- Porta 15789 disponível para o servidor web

---

## Instalação Rápida

### 1. Clonar ou Baixar o Projeto

```bash
# Opção 1: Via Git
git clone <repository-url>
cd Extracao_DadosLinha

# Opção 2: Download manual
# Extrair o ZIP para C:\programs\Extracao_DadosLinha
```

### 2. Instalar Dependências

```bash
# Instalar pacotes Python
pip install -r requirements.txt
```

??? info "requirements.txt"
    ```txt
    fastapi==0.109.0
    uvicorn[standard]==0.27.0
    pylogix==0.8.4
    pydantic==2.5.3
    python-multipart==0.0.6
    jinja2==3.1.3
    ```

### 3. Configurar PLCs

Edite os arquivos de configuração para cada máquina:

=== "Cupper_22/config.json"
    ```json
    {
      "plc_config": {
        "ip_address": "10.81.71.11",
        "processor_slot": 4
      },
      "production_config": {
        "size_data_dir": "production_data/Cupper_22"
      }
    }
    ```

=== "Cupper_23/config.json"
    ```json
    {
      "plc_config": {
        "ip_address": "10.81.72.11",
        "processor_slot": 4
      },
      "production_config": {
        "size_data_dir": "production_data/Cupper_23"
      }
    }
    ```

### 4. Executar o Sistema

```bash
python app.py
```

Acesse: **http://10.81.5.219:15789**

---

## Instalação como Serviço Windows

Para garantir que o sistema inicie automaticamente com o Windows:

### 1. Baixar NSSM

1. Acesse [nssm.cc](https://nssm.cc/download)
2. Baixe a versão 64-bit
3. Extraia `nssm.exe` para `C:\nssm\`

### 2. Instalar o Serviço

Abra o PowerShell como **Administrador**:

```powershell
# Navegar até o diretório do NSSM
cd C:\nssm

# Instalar o serviço
.\nssm.exe install CanpackPLCMonitor
```

### 3. Configurar o Serviço

Na janela que abrir, configure:

| Campo | Valor |
|-------|-------|
| **Path** | `C:\Python313\python.exe` |
| **Startup directory** | `C:\programs\Extracao_DadosLinha` |
| **Arguments** | `app.py` |

**Aba "Details":**

| Campo | Valor |
|-------|-------|
| **Display name** | Sistema de Monitoramento PLC - CANPACK |
| **Description** | Monitoramento em tempo real das linhas Cupper |
| **Startup type** | Automatic |

### 4. Configurar Recuperação

**Aba "Exit Actions":**

- Restart application
- Delay: 10000 ms

**Aba "I/O":**

- Output (stdout): `C:\programs\Extracao_DadosLinha\logs\service_output.log`
- Error (stderr): `C:\programs\Extracao_DadosLinha\logs\service_error.log`

### 5. Iniciar o Serviço

```powershell
# Iniciar
.\nssm.exe start CanpackPLCMonitor

# Verificar status
.\nssm.exe status CanpackPLCMonitor

# Parar (se necessário)
.\nssm.exe stop CanpackPLCMonitor
```

---

## Verificação da Instalação

### 1. Health Check

```bash
curl http://10.81.5.219:15789/api/health
```

Resposta esperada:
```json
{
  "status": "OK",
  "database": "CONNECTED",
  "plcs": {
    "Cupper_22": "ONLINE",
    "Cupper_23": "ONLINE"
  }
}
```

### 2. Verificar Logs

```bash
# Ver últimas 20 linhas do log
Get-Content logs\plc_system_20260112.log -Tail 20
```

### 3. Testar Interface Web

Acesse no navegador:

- Interface principal: http://10.81.5.219:15789
- Documentação API: http://10.81.5.219:15789/docs

---

## Estrutura de Diretórios

Após a instalação, a estrutura será:

```
Extracao_DadosLinha/
├── app.py                  # Aplicação principal
├── src/                    # Código modular
│   ├── api_routes.py
│   ├── database_handler.py
│   ├── plc_manager.py
│   └── ...
├── Cupper_22/             # Configuração Linha 22
│   └── config.json
├── Cupper_23/             # Configuração Linha 23
│   └── config.json
├── production_data/       # Dados de produção
│   ├── Cupper_22/
│   └── Cupper_23/
├── backups/               # Backups automáticos
├── logs/                  # Logs do sistema
└── production_data.db     # Banco de dados SQLite
```

---

## Troubleshooting

### Erro: "ModuleNotFoundError"

```bash
# Reinstalar dependências
pip install -r requirements.txt --force-reinstall
```

### Erro: "Address already in use"

Outro processo está usando a porta 15789:

```powershell
# Encontrar processo
netstat -ano | findstr :15789

# Matar processo (substitua PID)
taskkill /PID <PID> /F
```

### PLCs aparecem como OFFLINE

1. Verificar conectividade de rede:
   ```bash
   ping 10.81.71.11
   ping 10.81.72.11
   ```

2. Verificar IPs nos arquivos de configuração

3. Verificar firewall do Windows

---

## Próximos Passos

- [Configuração Avançada](configuration.md)
- [Referência de API](../api/endpoints.md)
- [Integração TOTVS](../api/totvs.md)
