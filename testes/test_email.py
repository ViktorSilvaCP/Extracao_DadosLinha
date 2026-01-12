from email_templates import format_feed_unknown_alert_email
from email_utils import send_email_direct
from timezone_utils import get_current_sao_paulo_time
import logging
import sys

def setup_test_logging():
    """Configura um logging básico para o teste, apenas para o console."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

if __name__ == "__main__":
    setup_test_logging()

    # --- DADOS DE TESTE ---
    plc_name = "Cupper 99 (Teste)"
    feed_value = 9.9999
    lote = "LOTE-TESTE-123"
    bobina = "BOB-TESTE-01"
    timestamp = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")

    # --- ALTERE AQUI O SEU E-MAIL ---
    meu_email = ["victor.nascimento@canpack.com"] 

    logging.info("Gerando conteúdo do e-mail de teste...")
    email_content = format_feed_unknown_alert_email(plc_name, feed_value, lote, bobina, timestamp)

    logging.info(f"Tentando enviar e-mail de teste para: {meu_email}")
    send_email_direct(
        to=meu_email,
        subject="[TESTE] Alerta de Tamanho de Copo Desconhecido",
        message=email_content
    )
    logging.info("Script de teste finalizado. Verifique sua caixa de entrada.")