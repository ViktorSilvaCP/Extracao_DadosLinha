#!/usr/bin/env python3
"""
Visualizador de Lotes com pywebview - CANPACK BRASIL
Abre a interface web DENTRO de uma janela desktop usando pywebview
"""

import webview
import threading
import time
import sys
from datetime import datetime

class LoteWebViewer:
    def __init__(self):
        self.url = "http://10.81.5.219:15789/"
        self.running = True
        
    def run(self):
        """Executa a aplicação"""
        print("Iniciando Sistema de Controle de Lotes...")
        print("=" * 50)
        print("Funcionalidades:")
        print("   - Interface web embarcada")
        print("   - Impede fechamento acidental")
        print("   - Confirmacao antes de sair")
        print("   - Tela cheia disponivel")
        print("=" * 50)
        
        # Iniciar thread de verificação de conectividade
        connectivity_thread = threading.Thread(target=self.check_connectivity, daemon=True)
        connectivity_thread.start()
        
        # Executar webview com configurações simples
        try:
            print("Iniciando interface web...")
            webview.create_window(
                title='Sistema de Controle de Lotes - CANPACK BRASIL',
                url=self.url,
                width=1200,
                height=800,
                resizable=True,
                confirm_close=True
            )
            webview.start(debug=False)
        except Exception as e:
            print(f"Erro ao executar webview: {e}")
            # Tentar com configurações mínimas
            try:
                webview.create_window('Sistema de Lotes', self.url)
                webview.start()
            except Exception as e2:
                print(f"Erro ao executar webview (segunda tentativa): {e2}")
        
        print("Sistema encerrado. Obrigado!")
    
    def check_connectivity(self):
        """Verifica conectividade com o servidor"""
        import urllib.request
        import urllib.error
        
        while self.running:
            try:
                urllib.request.urlopen(self.url, timeout=5)
                print(f"Conectado ao sistema - {datetime.now().strftime('%H:%M:%S')}")
            except (urllib.error.URLError, urllib.error.HTTPError):
                print(f"Sem conexao com o sistema - {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"Erro de conectividade: {e} - {datetime.now().strftime('%H:%M:%S')}")
                
            time.sleep(30)  # Verificar a cada 30 segundos

def main():
    """Função principal"""
    try:
        # Verificar se pywebview está instalado
        try:
            import webview
        except ImportError:
            print("pywebview nao esta instalado.")
            print("Instalando pywebview...")
            
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])
            
            print("pywebview instalado com sucesso!")
            print("Reinicie o script...")
            return
        
        viewer = LoteWebViewer()
        viewer.run()
    except KeyboardInterrupt:
        print("Sistema interrompido pelo usuario.")
    except Exception as e:
        print(f"Erro na aplicacao: {e}")
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    main() 