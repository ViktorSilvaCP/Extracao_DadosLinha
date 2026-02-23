#!/usr/bin/env python3
"""
Script de Migração: Transfere lote_config de config.json para banco de dados.
Executar uma única vez antes de usar a nova versão.

Migration Script: Transfers lote_config from config.json to database.
Run once before using the new version.
"""

import json
import sys
import os
from src.database_handler import DatabaseHandler
from timezone_utils import get_current_sao_paulo_time

def migrate_lote_config():
    """Migra lote_config do JSON para o banco de dados."""
    
    # Inicializa o banco de dados
    DatabaseHandler.init_db()
    
    machines = ["Cupper_22", "Cupper_23"]
    
    for machine in machines:
        config_path = f"{machine}/config.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"❌ Erro ao ler {config_path}: {e}")
            continue
        
        # Extrai lote_config se existir
        lote_cfg = config.get('lote_config', {})
        
        if not lote_cfg:
            print(f"⏭️  {machine}: Nenhum lote_config encontrado, pulando...")
            continue
        
        # Salva no banco
        try:
            current_lote = lote_cfg.get('current_lote', 'N/A')
            last_updated = lote_cfg.get('last_updated', get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S"))
            bobina_saida = lote_cfg.get('bobina_saida', None)
            data_saida = lote_cfg.get('data_saida', None)
            tipo_bobina = lote_cfg.get('tipo_bobina', None)
            
            # Tenta UPDATE primeiro, se não existir faz INSERT
            conn = DatabaseHandler._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM lote_config WHERE machine_name = ?", (machine,))
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute("""
                UPDATE lote_config 
                SET current_lote = ?, last_updated = ?, bobina_saida = ?, data_saida = ?, tipo_bobina = ?
                WHERE machine_name = ?
                """, (current_lote, last_updated, bobina_saida, data_saida, tipo_bobina, machine))
                print(f"✅ {machine}: ATUALIZADO no banco")
            else:
                cursor.execute("""
                INSERT INTO lote_config (machine_name, current_lote, last_updated, bobina_saida, data_saida, tipo_bobina)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (machine, current_lote, last_updated, bobina_saida, data_saida, tipo_bobina))
                print(f"✅ {machine}: INSERIDO no banco")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erro ao migrar {machine}: {e}")
            return False
    
    print("\n✨ Migração concluída com sucesso!")
    print("   Os arquivos config.json foram atualizados (lote_config removido).")
    print("   Os dados estão agora no banco de dados para melhor performance.")
    return True

if __name__ == "__main__":
    print("🚀 Iniciando migração de lote_config...")
    print("=" * 60)
    
    success = migrate_lote_config()
    sys.exit(0 if success else 1)
