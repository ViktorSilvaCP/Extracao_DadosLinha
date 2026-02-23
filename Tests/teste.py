from pylogix import PLC

with PLC() as comm:
    comm.IPAddress = '10.81.71.11'
    comm.ProcessorSlot = 4
    
    # Lê a tag completa (o pylogix no Python 3 costuma resolver a String sozinho)
    ret = comm.Read('Cupper22_Bobina_Consumida_Serial')
    
    if ret.Status == 'Success':
        # Se o valor vier como float/científico, tratamos. Se vier string, imprimimos.
        if isinstance(ret.Value, float):
            print(f"{ret.Value:.0f}")
        else:
            print(ret.Value)
    else:
        print(f"Erro: {ret.Status}")