# Gerenciamento do Serviço Windows

O sistema roda como um serviço Windows em segundo plano utilizando o **NSSM (Non-Sucking Service Manager)**. Isso garante que a aplicação inicie automaticamente com o Windows e reinicie em caso de falhas.

## Comandos Básicos

Todos os comandos devem ser executados no PowerShell ou CMD como **Administrador**.

### Verificar Status
```powershell
nssm status CanpackPLCMonitor
```
*Retornos comuns: `SERVICE_RUNNING`, `SERVICE_STOPPED`, `SERVICE_PAUSED`*

### Iniciar o Serviço
```powershell
nssm start CanpackPLCMonitor
```

### Parar o Serviço
```powershell
nssm stop CanpackPLCMonitor
```

### Reiniciar o Serviço
```powershell
nssm restart CanpackPLCMonitor
```

---

## Configuração do Serviço

Para editar as configurações do serviço (como caminhos, argumentos ou usuário):

```powershell
nssm edit CanpackPLCMonitor
```

Isso abrirá a interface gráfica do NSSM.

### Parâmetros Importantes

- **Application Path**: `C:\Python313\python.exe` (ou onde seu Python estiver instalado)
- **Startup Directory**: `C:\programs\Extracao_DadosLinha`
- **Arguments**: `app.py`
- **I/O Redirection**:
    - Stdout: `logs\service_output.log`
    - Stderr: `logs\service_error.log`

## Troubleshooting do Serviço

Se o serviço não iniciar (`SERVICE_PAUSED` ou falha ao iniciar):

1. Verifique o arquivo `logs\service_error.log`. Ele contém erros de inicialização do Python (ex: biblioteca faltando).
2. Tente rodar manualmente para ver o erro na tela:
   ```powershell
   cd C:\programs\Extracao_DadosLinha
   python app.py
   ```