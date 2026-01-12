# Backup e Recuperação

O sistema possui um mecanismo automático de backup do banco de dados SQLite para garantir a segurança dos dados de produção.

## Funcionamento Automático

O backup é acionado automaticamente em dois momentos:
1. **Inicialização do Sistema**: Sempre que o serviço é reiniciado (`app.py` startup event).
2. **Rotina Manual**: Pode ser executado via script `backup_utils.py`.

### Localização

Os arquivos são armazenados na pasta `backups/` na raiz do projeto.

- **Origem**: `production_data.db`
- **Destino**: `backups/production_backup_YYYYMMDD_HHMMSS.db`

### Política de Retenção

O sistema mantém automaticamente apenas os **últimos 10 backups**. Arquivos mais antigos são excluídos automaticamente após a criação de um novo backup bem-sucedido para economizar espaço em disco.

---

## Como Restaurar um Backup

Caso o banco de dados principal seja corrompido, siga estes passos para restaurar:

1. **Pare o serviço** do sistema:
   ```powershell
   nssm stop CanpackPLCMonitor
   ```

2. **Renomeie** o banco atual (se existir) para `production_data.db.old`.

3. **Escolha** o arquivo de backup mais recente na pasta `backups/`.

4. **Copie** o arquivo escolhido para a raiz do projeto e renomeie-o para `production_data.db`.

5. **Inicie o serviço** novamente:
   ```powershell
   nssm start CanpackPLCMonitor
   ```

!!! warning "Atenção"
    A restauração substituirá todos os dados atuais pelos dados do momento do backup. Dados gerados entre o backup e o momento atual serão perdidos.