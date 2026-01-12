from pylogix import PLC

ip = '10.81.72.11'
slot = 4
output_file = 'tags_pylogix.txt'
with PLC() as comm:
    comm.IPAddress = ip
    comm.ProcessorSlot = slot
    # Obtém a lista de todas as tags
    print(f"Conectando ao PLC {ip} e obtendo a lista de tags...")
    tag_list = comm.GetTagList()
    # Verifica se a obtenção da lista de tags foi bem-sucedida
    if tag_list.Status == 'Success' and tag_list.Value:
        print(f"Encontradas {len(tag_list.Value)} tags. Lendo e salvando os valores...")
        with open(output_file, 'w', encoding='utf-8') as f:
            for tag in tag_list.Value:
                try:
                    # Ler cada tag individualmente
                    result = comm.Read(tag.TagName)
                    if result.Status == 'Success':
                        f.write(f"{tag.TagName}: {result.Value}\n")
                    else:
                        f.write(f"{tag.TagName}: Erro ao ler valor - Status: {result.Status}\n")
                except Exception as e:
                    # Captura exceções que podem ocorrer durante a leitura de uma tag específica
                    f.write(f"{tag.TagName}: Erro excepcional ao ler valor - {e}\n")
        print(f"Tags e valores salvos em {output_file}")
    else:
        # Informa o erro caso não consiga obter a lista de tags
        print(f"Falha ao obter a lista de tags do PLC. Status: {tag_list.Status}")
