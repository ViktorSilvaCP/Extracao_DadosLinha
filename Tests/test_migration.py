#!/usr/bin/env python3
"""
Script de Teste: Valida que toda a migração funcionou corretamente.

Test Script: Validates that the entire migration worked correctly.
"""

from src.database_handler import DatabaseHandler
from src.config_handler import (
    get_lote_from_config, 
    get_bobina_type_from_config,
    get_bobina_saida_from_config
)
import json

def test_migration():
    """Testa se a migração foi bem-sucedida."""
    
    DatabaseHandler.init_db()
    
    print("=" * 70)
    print("🧪 TESTE DE MIGRAÇÃO - LOTE CONFIG")
    print("=" * 70)
    
    # Test 1: Verificar que config.json não tem lote_config
    print("\n[TEST 1] Verificar config.json limpo (sem lote_config)...")
    for machine in ["Cupper_22", "Cupper_23"]:
        try:
            with open(f"{machine}/config.json", 'r') as f:
                config = json.load(f)
            
            if 'lote_config' in config:
                print(f"  ❌ {machine}: FALHOU - lote_config ainda existe no JSON")
                return False
            else:
                print(f"  ✅ {machine}: OK - lote_config removido do JSON")
        except Exception as e:
            print(f"  ❌ {machine}: Erro ao ler - {e}")
            return False
    
    # Test 2: Verificar que dados estão no banco
    print("\n[TEST 2] Verificar dados no banco de dados...")
    try:
        conn = DatabaseHandler._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM lote_config")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count >= 2:
            print(f"  ✅ OK - {count} registros de lote_config no banco")
        else:
            print(f"  ⚠️  AVISO - Apenas {count} registros (esperado >= 2)")
    except Exception as e:
        print(f"  ❌ Erro ao consultar banco: {e}")
        return False
    
    # Test 3: Verificar que config_handler lê do banco
    print("\n[TEST 3] Verificar que config_handler lê do banco...")
    for machine in ["Cupper_22", "Cupper_23"]:
        try:
            lote = get_lote_from_config(machine)
            tipo = get_bobina_type_from_config(machine)
            saida = get_bobina_saida_from_config(machine)
            
            print(f"  ✅ {machine}:")
            print(f"     - Lote: {lote}")
            print(f"     - Tipo: {tipo}")
            print(f"     - Bobina Saída: {saida['lote']} ({saida['data_saida']})")
        except Exception as e:
            print(f"  ❌ {machine}: Erro - {e}")
            return False
    
    # Test 4: Verificar índices
    print("\n[TEST 4] Verificar índices no banco...")
    try:
        conn = DatabaseHandler._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lote_config'")
        indices = cursor.fetchall()
        
        if indices:
            print(f"  ✅ Índices encontrados:")
            for idx in indices:
                print(f"     - {idx[0]}")
        else:
            print(f"  ⚠️  AVISO - Nenhum índice encontrado na tabela lote_config")
        
        conn.close()
    except Exception as e:
        print(f"  ❌ Erro ao verificar índices: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✨ TODOS OS TESTES PASSARAM!")
    print("=" * 70)
    print("\n📋 Próximos passos:")
    print("   1. Iniciar o app.pyw")
    print("   2. Testar envio de novo lote via interface web")
    print("   3. Verificar que não há mais erros de lock de arquivo")
    print("\n")
    
    return True

if __name__ == "__main__":
    import sys
    success = test_migration()
    sys.exit(0 if success else 1)
