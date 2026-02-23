#!/usr/bin/env python3
"""
Script de Inicialização: Cria registros de lote_config padrão no banco de dados.
Para máquinas sem histórico anterior.

Initialization Script: Creates default lote_config records in database.
For machines without previous history.
"""

from src.database_handler import DatabaseHandler
from timezone_utils import get_current_sao_paulo_time

def init_default_lote_config():
    """Cria registros padrão de lote_config para máquinas sem dados."""
    
    # Inicializa o banco de dados
    DatabaseHandler.init_db()
    
    machines = ["Cupper_22", "Cupper_23"]
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    
    for machine in machines:
        try:
            # Tenta buscar se já existe
            existing_lote = DatabaseHandler.get_lote_from_db(machine)
            
            if existing_lote == "Nenhum lote definido":
                print(f"📝 {machine}: Criando registro padrão...")
                
                # Insere registro padrão
                success = DatabaseHandler.save_lote_to_db(machine, "N/A")
                if success:
                    print(f"✅ {machine}: Registro padrão criado")
                else:
                    print(f"❌ {machine}: Erro ao criar registro")
            else:
                print(f"✅ {machine}: Já possui lote definido ({existing_lote})")
                
        except Exception as e:
            print(f"❌ {machine}: Erro - {e}")
    
    print("\n✨ Inicialização concluída!")

if __name__ == "__main__":
    print("🚀 Inicializando lote_config padrão...")
    print("=" * 60)
    init_default_lote_config()
