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
        
    def clean_subject(self, subject):
        """Remove emojis and special characters from subject"""
        return ''.join(char for char in subject if ord(char) < 128)

    def _send_email(self, subject, message, is_error=False, attachments=None): # attachments is now a list
        try:
            # Fix subject encoding
            subject = subject.encode('latin1', 'ignore').decode('latin1')
            
            recipients = ERROR_RECIPIENTS if is_error else PRODUCTION_RECIPIENTS
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