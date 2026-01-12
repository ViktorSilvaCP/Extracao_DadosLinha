import logging
import os
import sys
import tempfile
from threading import Thread
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Novos módulos organizados
from src.config_handler import load_config
from src.database_handler import DatabaseHandler
from src.plc_manager import SharedPLCData, PLCMonitorManager
from src.api_routes import router, init_api
from email_utils import EmailNotifier
from timezone_utils import get_current_sao_paulo_time
from backup_utils import backup_database

# Metadados para Documentação (Swagger)
tags_metadata = [
    {
        "name": "Monitoramento",
        "description": "Visualização de dados em tempo real vindos diretamente dos PLCs.",
    },
    {
        "name": "Relatórios de Produção",
        "description": "Consultas históricas de produção registradas a cada troca de bobina.",
    },
    {
        "name": "Operação de Lotes",
        "description": "Comandos para alteração de lotes e tipos de bobina nas máquinas.",
    },
]

# Configuração da aplicação
app = FastAPI(
    title="🚀 Sistema de Extração de Dados - Canpack",
    description="""
Monitoramento industrial avançado para linhas Cupper.
Este sistema centraliza a coleta de dados de produção, controle de lotes e geração de relatórios automáticos.

### Categorias:
* **Monitoramento**: Status atual de produção e conexão.
* **Relatórios**: Dados históricos por turno e bobina.
* **Operação**: Interface para input de novos lotes.
    """,
    version="2.1.0",
    openapi_tags=tags_metadata
)

# Monta arquivos estáticos
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Adiciona as rotas organizadas
app.include_router(router)

def setup_logging():
    """Configura o sistema de logs."""
    log_dir = r'F:\Doc_Comp\(Publico)\Dados\ControlLogix\logs'
    if not os.path.exists(log_dir):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"plc_system_{get_current_sao_paulo_time().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

@app.on_event("startup")
async def startup_event():
    """Inicializa os serviços em segundo plano ao iniciar o servidor."""
    setup_logging()
    logging.info("Iniciando sistema...")
    DatabaseHandler.init_db()
    shared_data = SharedPLCData()
    monitor_manager = PLCMonitorManager(shared_data)
    
    # Realiza backup preventivo na inicialização
    backup_database()
    configs = {
        "Cupper_22": load_config('Cupper_22/config.json'),
        "Cupper_23": load_config('Cupper_23/config.json')
    }
    init_api(shared_data, configs)
    email_notifier = EmailNotifier(max_workers=4)
    lock_dir = os.path.join(tempfile.gettempdir(), 'canpack_plc_monitor_locks')
    
    plcs_to_monitor = [
        {"name": "Cupper_22", "config": configs["Cupper_22"]},
        {"name": "Cupper_23", "config": configs["Cupper_23"]}
    ]
    
    monitor_manager.start_monitoring(plcs_to_monitor, email_notifier, lock_dir)
    logging.info("Monitoramento de PLCs iniciado.")

if __name__ == "__main__":
    # Host e porta configurados conforme original
    uvicorn.run(app, host="10.81.5.219", port=15789)