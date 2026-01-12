from datetime import datetime
import pytz
SAO_PAULO_TZ = pytz.timezone('America/Sao_Paulo')

def get_current_sao_paulo_time():
    return datetime.now(SAO_PAULO_TZ)