from datetime import datetime
import pytz
def convert_pacific_to_brazil_time(dt_pacific=None):
    try:
        pacific_tz = pytz.timezone('America/Los_Angeles')
        brazil_tz = pytz.timezone('America/Sao_Paulo')
        if dt_pacific is None:
            dt_pacific = pacific_tz.localize(datetime.now())
        elif dt_pacific.tzinfo is None or dt_pacific.tzinfo.utcoffset(dt_pacific) is None:
            dt_pacific = pacific_tz.localize(dt_pacific)
        else:
            dt_pacific = dt_pacific.astimezone(pacific_tz)
        dt_brazil = dt_pacific.astimezone(brazil_tz)
        return dt_pacific, dt_brazil
    except pytz.exceptions.UnknownTimeZoneError as e:
        print(f"Erro: Fuso horário desconhecido. {e}")
        return None, None
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
        return None, None
if __name__ == "__main__":
    print("Convertendo o horário atual do Pacífico para o Brasil:")
    pacific_time_now, brazil_time_now = convert_pacific_to_brazil_time()
    if pacific_time_now and brazil_time_now:
        print(f"Horário no Pacífico (America/Los_Angeles): {pacific_time_now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Horário em São Paulo (America/Sao_Paulo): {brazil_time_now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    print("-" * 30)
    print("\nConvertendo um horário específico do Pacífico para o Brasil:")
    specific_pacific_datetime_naive = datetime(2023, 10, 27, 14, 30, 0) # Um datetime "naive"
    pacific_time_specific, brazil_time_specific = convert_pacific_to_brazil_time(specific_pacific_datetime_naive)
    if pacific_time_specific and brazil_time_specific:
        print(f"Horário específico no Pacífico: {pacific_time_specific.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Horário correspondente em São Paulo: {brazil_time_specific.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    print("-" * 30)
    print("\nConvertendo um datetime 'aware' (UTC) para o Brasil, passando por Pacífico:")
    utc_datetime_aware = pytz.utc.localize(datetime.utcnow())
    pacific_time_from_utc, brazil_time_from_utc = convert_pacific_to_brazil_time(utc_datetime_aware)
    if pacific_time_from_utc and brazil_time_from_utc:
        print(f"Horário original (UTC): {utc_datetime_aware.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Convertido para Pacífico: {pacific_time_from_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"Convertido para São Paulo: {brazil_time_from_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

