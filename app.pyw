import logging
import os
import sys
import tempfile
from threading import Thread
import uvicorn
import subprocess
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.database_handler import DatabaseHandler
from src.plc_manager import SharedPLCData, PLCMonitorManager
from src.api_routes import router, init_api
from email_utils import EmailNotifier
from timezone_utils import get_current_sao_paulo_time
from backup_utils import backup_database

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
    
    # Backup log path as secondary (Configurable via .env)
    secondary_log_dir = os.getenv("SECONDARY_LOG_DIR")
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
    existing_plcs = DatabaseHandler.get_all_plcs()
    if not existing_plcs:
        logging.info("Semeando PLCs iniciais (Cupper_22/23)...")
        default_plcs = [
            {
                "name": "Cupper_22",
                "ip": "10.81.71.11",
                "slot": 4,
                "socket_timeout": 5,
                "main_tag": "Count_discharge",
                "feed_tag": "Feed_Progression_INCH",
                "bobina_tag": "Bobina_Consumida",
                "trigger_coil_tag": "Bobina_Trocada",
                "lote_tag": "Cupper22_Bobina_Consumida_Serial",
                "stroke_tag": "oHMI_Daily_Stroke_Count",
                "tool_size_tag": "IGN_Tool_Size",
                "is_active": 1
            },
            {
                "name": "Cupper_23",
                "ip": "10.81.72.11",
                "slot": 4,
                "socket_timeout": 5,
                "main_tag": "Count_discharge",
                "feed_tag": "Feed_Progression_INCH",
                "bobina_tag": "Bobina_Consumida",
                "trigger_coil_tag": "Bobina_Trocada",
                "lote_tag": "Cupper22_Bobina_Consumida_Serial",
                "stroke_tag": "oHMI_Daily_Stroke_Count",
                "tool_size_tag": "IGN_Tool_Size",
                "is_active": 1
            }
        ]
        for p in default_plcs:
            DatabaseHandler.save_plc(p)
        existing_plcs = DatabaseHandler.get_all_plcs()

    shared_data = SharedPLCData()
    monitor_manager = PLCMonitorManager(shared_data)
    backup_database()
    plc_configs_db = {}
    plcs_to_monitor = []
    
    for plc in existing_plcs:
        merged_config = {
            "plc_config": {
                "ip_address": plc['ip'],
                "processor_slot": plc['slot'],
                "socket_timeout": 5
            },
            "tag_config": {
                "main_tag": plc['main_tag'],
                "feed_tag": plc['feed_tag'],
                "bobina_tag": plc['bobina_tag'],
                "trigger_coil_tag": plc['trigger_coil_tag'],
                "lote_tag": plc['lote_tag'],
                "stroke_tag": plc['stroke_tag'],
                "tool_size_tag": plc['tool_size_tag']
            },
            "connection_config": {
                "read_interval": 5,
                "retry_delay": 5
            },
            "cup_size_config": {
                "tolerance": 0.0004,
                "sizes": {
                    "269ml_FIT": 5.1312,
                    "269ml_FIT_LW": 5.0168,
                    "350ml_FIT": 5.5693,
                    "350ml_STD": 5.5848,
                    "350ml_STD_": 5.5722,
                    "473ml": 6.0768,
                    "550ml": 6.4304
                }
            }
        }

        plc_configs_db[plc['name']] = merged_config
        
        if plc['is_active']:
            plcs_to_monitor.append({"name": plc['name'], "config": merged_config})

    init_api(shared_data, plc_configs_db, monitor_manager)
    email_notifier = EmailNotifier(max_workers=4)
    lock_dir = os.path.join(tempfile.gettempdir(), 'canpack_plc_monitor_locks')
    
    monitor_manager.start_monitoring(plcs_to_monitor, email_notifier, lock_dir)
    logging.info(f"Monitoramento de {len(plcs_to_monitor)} PLCs iniciado.")
    yield

# Configuração da aplicação
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*; style-src 'self' 'unsafe-inline' https://*; font-src 'self' data: https://*; img-src 'self' data: https://*;"
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]
        return response

app = FastAPI(
    title=os.getenv("APP_TITLE", "API Canpack"),
    description="""
Monitoramento industrial avançado para linhas Cupper.
Este sistema centraliza a coleta de dados de produção, controle de lotes e geração de relatórios automáticos. / This system centralizes production data collection, batch control, and automatic report generation.

### Categorias / Categories:
*♥ **Monitoramento / Monitoring**: Status atual de produção e conexão. / Current production and connection status.
* **Relatórios / Reports**: Dados históricos por turno e bobina. / Historical data by shift and coil.
* **Operação / Operation**: Interface para input de novos lotes. / Interface for new batch input.
    """,
    version=os.getenv("APP_VERSION", "1.0.0"),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None
)

allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
allow_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")
try:
    print("Gerando documentação MkDocs...")
    subprocess.run([sys.executable, "-m", "mkdocs", "build"], check=True)
except Exception as e:
    logging.error(f"Erro ao gerar documentação MkDocs: {e}")
try:
    app.mount("/documentation", StaticFiles(directory="site", html=True), name="documentation")
except Exception as e:
    logging.warning(f"Documentação MkDocs não encontrada. Execute 'python -m mkdocs build' para gerar.")
app.include_router(router)

@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def redirect_to_docs():
    """Redireciona /docs para /api/docs para compatibilidade."""
    return HTMLResponse(content="""
    <html>
        <head>
            <title>Redirecting...</title>
            <meta http-equiv="refresh" content="0; url=/api/docs" />
        </head>
        <body>
            Redirecionando para <a href="/api/docs">/api/docs</a>...
        </body>
    </html>
    """)

@app.get("/api/logs", tags=["Manutenção / Maintenance"])
def get_system_logs(request: Request,
                    level: str = Query(None, description="Filtrar por nível: INFO, DEBUG, ERROR"), 
                    limit: int = Query(500, description="Número máximo de linhas a retornar (padrão: 500)")):
    # Proteção de token para logs do sistema
    token = request.headers.get("X-Terminal-Token")
    if token != os.getenv("API_MASTER_TOKEN"):
        raise HTTPException(status_code=403, detail="Acesso negado aos logs do servidor.")
        
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
        uvicorn.run(app, host=os.getenv("API_HOST", "0.0.0.0"), port=int(os.getenv("API_PORT", 15789)))
