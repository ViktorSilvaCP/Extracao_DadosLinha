import logging
import os
import sys
import tempfile
from threading import Thread
import uvicorn
import subprocess
from fastapi import FastAPI, Query
from contextlib import asynccontextmanager
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
        "name": "Monitoramento / Monitoring",
        "description": "Visualização de dados em tempo real vindos diretamente dos PLCs. / Real-time data visualization directly from PLCs.",
    },
    {
        "name": "Relatórios de Produção / Production Reports",
        "description": "Consultas históricas de produção registradas a cada troca de bobina. / Historical production queries recorded at each coil change.",
    },
    {
        "name": "Operação de Lotes / Batch Operations",
        "description": "Comandos para alteração de lotes e tipos de bobina nas máquinas. / Commands for changing batches and coil types on machines.",
    },
    {
        "name": "Integração ERP / ERP Integration",
        "description": "Endpoints dedicados para sincronização com sistemas externos. / Dedicated endpoints for synchronization with external systems.",
    },
]

def setup_logging():
    """Configura o sistema de logs."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Backup log path as secondary
    secondary_log_dir = r'F:\Doc_Comp\(Publico)\Dados\ControlLogix\logs'
    log_file = os.path.join(log_dir, f"plc_system_{get_current_sao_paulo_time().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
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
    yield

# Configuração da aplicação
app = FastAPI(
    title="🚀 Sistema de Extração de Dados - Canpack",
    description="""
Monitoramento industrial avançado para linhas Cupper.
Este sistema centraliza a coleta de dados de produção, controle de lotes e geração de relatórios automáticos. / This system centralizes production data collection, batch control, and automatic report generation.

### Categorias / Categories:
* **Monitoramento / Monitoring**: Status atual de produção e conexão. / Current production and connection status.
* **Relatórios / Reports**: Dados históricos por turno e bobina. / Historical data by shift and coil.
* **Operação / Operation**: Interface para input de novos lotes. / Interface for new batch input.
    """,
    version="2.1.1",
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

# Monta arquivos estáticos
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Gera a documentação automaticamente antes de montar a rota
try:
    print("Gerando documentação MkDocs...")
    subprocess.run([sys.executable, "-m", "mkdocs", "build"], check=True)
except Exception as e:
    logging.error(f"Erro ao gerar documentação MkDocs: {e}")

# Monta documentação MkDocs
try:
    app.mount("/documentation", StaticFiles(directory="site", html=True), name="documentation")
except Exception as e:
    logging.warning(f"Documentação MkDocs não encontrada. Execute 'python -m mkdocs build' para gerar.")

# Adiciona as rotas organizadas
app.include_router(router)

@app.get("/api/logs", tags=["Manutenção / Maintenance"])
def get_system_logs(level: str = Query(None, description="Filtrar por nível: INFO, DEBUG, ERROR"), 
                    limit: int = Query(500, description="Número máximo de linhas a retornar (padrão: 500)")):
    """Retorna os logs do sistema do dia atual."""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        log_file = os.path.join(log_dir, f"plc_system_{get_current_sao_paulo_time().strftime('%Y%m%d')}.log")
        
        if not os.path.exists(log_file):
            return {"error": "Arquivo de log não encontrado para hoje."}
            
        from collections import deque
        logs = deque(maxlen=limit)
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if level:
                    if level.upper() in line:
                        logs.append(line.strip())
                else:
                    logs.append(line.strip())
                    
        return {"count": len(logs), "logs": list(logs)}
    except Exception as e:
        return {"error": f"Erro ao ler logs: {str(e)}"}

if __name__ == "__main__":
    # Host e porta configurados conforme original
    uvicorn.run(app, host="0.0.0.0", port=15789)