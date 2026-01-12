# Guia de Configuração

O sistema utiliza arquivos JSON individuais para configurar cada PLC monitorado. Estes arquivos estão localizados na pasta raiz de cada máquina (ex: `Cupper_22/config.json`).

## Estrutura do Arquivo `config.json`

O arquivo de configuração é dividido em seções específicas para cada aspecto do monitoramento.

### 1. Configuração do PLC (`plc_config`)

Define os parâmetros de conexão física com o controlador.

```json
"plc_config": {
  "ip_address": "10.81.71.11",  // Endereço IP do PLC
  "processor_slot": 4           // Slot do processador no rack
}
```

### 2. Mapeamento de Tags (`tag_config`)

Define quais tags do ControlLogix serão lidas.

```json
"tag_config": {
  "main_tag": "Count_discharge",      // Contador principal de produção
  "feed_tag": "Feed_Progression_INCH", // Tag para identificar formato
  "bobina_tag": "Bobina_Consumida",    // Status do consumo da bobina
  "trigger_coil_tag": "Coil_change"    // Gatilho de troca de bobina
}
```

### 3. Conexão e Timeout (`connection_config`)

Parâmetros de estabilidade e retentativa de conexão.

```json
"connection_config": {
  "max_attempts": 3,      // Tentativas antes de considerar falha
  "retry_delay": 2.0,     // Segundos entre tentativas
  "read_interval": 1.0    // Intervalo entre leituras (loop principal)
}
```

### 4. Configuração de Formatos (`cup_size_config`)

Tabela de referência para identificar o tamanho do copo baseado no avanço da fita (Feed Rate).

```json
"cup_size_config": {
  "tolerance": 0.0004,    // Tolerância aceitável (+/-)
  "sizes": {
    "269ml_FIT": 5.1312,
    "350ml_STD": 5.5848,
    "473ml": 6.0768,
    "550ml": 6.4304
  }
}
```

### 5. Configuração de Arquivos (`file_config` e `production_config`)

Define onde e como os arquivos de log locais (legado) serão salvos.

```json
"file_config": {
  "base_format": "Producao_{size}.txt",
  "date_format": "Producao_{size}_{date}.txt"
},
"production_config": {
  "size_data_dir": "production_data/Cupper_22" // Diretório de saída
}
```

---

## Exemplo Completo

```json
{
  "plc_name": "Cupper_22",
  "plc_config": {
    "ip_address": "10.81.71.11",
    "processor_slot": 4
  },
  "tag_config": {
    "main_tag": "Count_discharge",
    "feed_tag": "Feed_Progression_INCH",
    "bobina_tag": "Bobina_Consumida"
  },
  "connection_config": {
    "max_attempts": 3,
    "retry_delay": 2.0,
    "read_interval": 1.0
  },
  "cup_size_config": {
    "tolerance": 0.0004,
    "sizes": { "350ml_STD": 5.5848 }
  },
  "status": "ATIVO"
}
```