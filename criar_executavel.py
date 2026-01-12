#!/usr/bin/env python3
"""
Script para criar executável do visualizador de lotes
"""

import subprocess
import sys
import os

def install_pyinstaller():
    """Instala o PyInstaller"""
    try:
        print("📦 Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller instalado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao instalar PyInstaller: {e}")
        return False

def create_executable():
    """Cria o executável"""
    try:
        print("🔨 Criando executável...")
        
        # Comando para criar executável
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",           # Arquivo único
            "--noconsole",         # Sem console
            "--name=Sistema_Lotes", # Nome do executável
            "--icon=icon.ico",     # Ícone (se existir)
            "lote_viewer_webview.py"
        ]
        
        # Remover ícone se não existir
        if not os.path.exists("icon.ico"):
            cmd.remove("--icon=icon.ico")
        
        subprocess.check_call(cmd)
        
        print("✅ Executável criado com sucesso!")
        print("📁 Localização: dist/Sistema_Lotes.exe")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar executável: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Criando Executável do Sistema de Lotes")
    print("=" * 50)
    
    # Instalar PyInstaller
    if not install_pyinstaller():
        return
    
    # Criar executável
    if not create_executable():
        return
    
    print("\n🎉 Executável criado com sucesso!")
    print("📋 Próximos passos:")
    print("   1. Vá para a pasta 'dist'")
    print("   2. Execute 'Sistema_Lotes.exe'")
    print("   3. O sistema abrirá automaticamente")
    
    input("\nPressione Enter para sair...")

if __name__ == "__main__":
    main() 