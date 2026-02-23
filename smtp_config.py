import os
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 25))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER = os.getenv("SMTP_SENDER")
SMTP_USE_AUTH = os.getenv("SMTP_USE_AUTH", "True") == "True"
SMTP_AUTH_TYPE = os.getenv("SMTP_AUTH_TYPE", "basic")
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", 30))
SMTP_MAX_SIZE = int(os.getenv("SMTP_MAX_SIZE", 20))
NOTIFICATION_RECIPIENTS = os.getenv("NOTIFICATION_RECIPIENTS", "").split(",")
ERROR_RECIPIENTS = os.getenv("ERROR_RECIPIENTS", "").split(",")
PRODUCTION_RECIPIENTS = os.getenv("PRODUCTION_RECIPIENTS", "").split(",")
