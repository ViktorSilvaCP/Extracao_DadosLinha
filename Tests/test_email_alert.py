import logging
import sys
import os

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from email_templates import format_late_lot_alert
from email_utils import send_email_direct

# Configuração de log para ver o que está acontecendo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_test():
    print("--- INICIANDO TESTE DE EMAIL DE ALERTA DE LOTE ---")
    
    # Dados fictícios para o teste
    plc_name = "CUPPER_TEST_22"
    lote_teste = "LOTE_TESTE_12345"
    
    print(f"1. Gerando template para: PLC={plc_name}, Lote={lote_teste}")
    try:
        message = format_late_lot_alert(plc_name, lote_teste)
        print("   ✅ Template gerado com sucesso.")
    except Exception as e:
        print(f"   ❌ Erro ao gerar template: {e}")
        return

    # Definindo destinatário (usando apenas um para não spammar todo mundo no teste)
    recipients = ["VICTOR.NASCIMENTO@CANPACK.COM", "RUI.SILVA@CANPACK.COM"]
    subject = f"[TESTE] Informativo: Lote Inalterado - {plc_name}"
    
    print(f"2. Enviando email para: {recipients}")
    try:
        send_email_direct(recipients, subject, message)
        print("   ✅ Email enviado com sucesso! Verifique sua caixa de entrada.")
    except Exception as e:
        print(f"   ❌ Erro ao enviar email: {e}")

if __name__ == "__main__":
    run_test()
