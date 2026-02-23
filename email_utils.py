import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from smtp_config import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_SENDER, ERROR_RECIPIENTS, PRODUCTION_RECIPIENTS

class EmailNotifier:
    def __init__(self, max_workers=2):
        self.smtp_server = SMTP_SERVER
        self.port = SMTP_PORT
        self.sender_email = SMTP_SENDER
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.email_pool = ThreadPoolExecutor(max_workers=max_workers)
        
    def _get_database_recipients(self):
        """Busca destinatários ativos do banco de dados."""
        from src.database_handler import DatabaseHandler
        active_recipients = DatabaseHandler.get_all_recipients(only_active=True)
        return [r['email'] for r in active_recipients]

    def _send_email(self, subject, message, is_error=False, attachments=None): # attachments is now a list
        try:
            # Fix subject encoding
            subject = subject.encode('latin1', 'ignore').decode('latin1')
            
            # Tenta carregar do banco primeiro para priorizar escalabilidade do Admin
            db_recipients = self._get_database_recipients()
            if is_error:
                recipients = ERROR_RECIPIENTS if ERROR_RECIPIENTS and ERROR_RECIPIENTS[0] else db_recipients
            else:
                recipients = db_recipients if db_recipients else PRODUCTION_RECIPIENTS

            if not recipients:
                logging.warning("Nenhum destinatário de e-mail configurado no banco ou .env")
                return

            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = subject

            # Add HTML version
            msg.attach(MIMEText(message['text'], 'plain', 'utf-8'))
            msg.attach(MIMEText(message['html'], 'html', 'utf-8'))
            
            if attachments: # attachments is a list of dicts
                for att_info in attachments:
                    attachment_filename = att_info.get('filename')
                    attachment_content = att_info.get('content')
                    if attachment_filename and attachment_content:
                        try:
                            part = MIMEApplication(attachment_content)
                            part.add_header('Content-Disposition', 'attachment', 
                                          filename=attachment_filename)
                            msg.attach(part)
                            logging.info(f"Arquivo anexado: {attachment_filename}")
                        except Exception as e:
                            logging.error(f"Erro ao criar anexo MIME para {attachment_filename}: {str(e)}")

            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                logging.info(f"Email enviado: {subject}")
                
        except Exception as e:
            logging.error(f"Erro ao enviar email: {str(e)}")

    def send_notification(self, subject, message, is_error=False, attachments=None): # attachments is now a list
        """Envia email de forma assíncrona usando thread pool"""
        self.email_pool.submit(self._send_email, subject, message, is_error, attachments)
    
    def __del__(self):
        """Cleanup thread pool on object destruction"""
        self.email_pool.shutdown(wait=False)


def send_email_direct(to, subject, message, attachments=None):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_SENDER
        msg['To'] = ", ".join(to)
        msg['Subject'] = subject
        msg.attach(MIMEText(message['text'], 'plain', 'utf-8'))
        msg.attach(MIMEText(message['html'], 'html', 'utf-8'))
        if attachments:
            for att_info in attachments:
                attachment_filename = att_info.get('filename')
                attachment_content = att_info.get('content')
                if attachment_filename and attachment_content:
                    part = MIMEApplication(attachment_content)
                    part.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
                    msg.attach(part)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            logging.info(f"Email enviado para {to}: {subject}")
    except Exception as e:
        logging.error(f"Erro ao enviar email direto: {str(e)}")