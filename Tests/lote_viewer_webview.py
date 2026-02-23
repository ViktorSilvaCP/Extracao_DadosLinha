import webview
import os
import sys

def main():
    # O Token que será usado
    TOKEN = os.getenv("API_MASTER_TOKEN", "CANPACK_PROD_2026_AUTHORIZATION")
    
    # URL de autorização que você pediu para incluir
    # Note que agora o sistema abre DIRETO nela para validar o acesso
    AUTH_URL = f"http://10.81.5.219:15789/?set_token={TOKEN}"
    
    # Criar a janela iniciando pela URL de autorização
    window = webview.create_window(
        '🚀 Sistema de Controle de Lotes | CANPACK',
        AUTH_URL,
        width=1280,
        height=850,
        min_size=(1024, 768)
    )
    
    def on_loaded():
        # 1. Injeta o token no localStorage para garantir persistência
        window.evaluate_js(f"localStorage.setItem('terminal_auth_token', '{TOKEN}');")
        print("🛡️ Autorização processada e Token injetado.")

    # Inicia o webview
    webview.start(on_loaded)

if __name__ == '__main__':
    main()