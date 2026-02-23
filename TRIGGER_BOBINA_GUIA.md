# Sistema de Trigger de Troca de Bobina com Email 3H

## Visão Geral

O sistema implementa um **trigger automático** que é acionado toda vez que uma bobina é trocada. Após a troca de bobina, o sistema aguarda **3 horas** e então envia um **email informativo** confirmando que a bobina não foi alterada durante esse período.

## Como Funciona

### 1. **Detecção de Troca de Bobina**

O trigger é acionado quando:
- O PLC registra o sinal `Coil_change` (trigger_coil_tag) = 1
- O sistema não está em um estado de mudança ativa (`self.coil_change_active == False`)

**Código:**
```python
if current_trigger_coil == 1 and not self.coil_change_active:
    self.coil_change_active = True
    # ... processa a troca
```

### 2. **Registro de Dados**

Quando a bobina muda, o sistema:
- ✅ Registra o **consumo total** da bobina anterior no banco de dados
- ✅ Calcula a quantidade de copos produzidos
- ✅ Identifica o tipo de troca (Completa ou Parcial)
- ✅ Armazena referências de horário e turno

### 3. **Agendamento do Email (3 Horas)**

Imediatamente após a troca:
- 🔔 Um alerta é agendado para ser **disparado em 3 horas**
- ⏰ O horário exato é registrado em `pending_lot_checks`
- 📝 Um log é gerado informando:
  - Qual lote foi trocado
  - Exatamente quando o email será enviado

**Log de Exemplo:**
```
[Cupper_22] 🔔 TRIGGER BOBINA ACIONADO: Lote 'LOTE001' - Email será enviado em 14/02/2026 15:45:30 (São Paulo)
```

### 4. **Verificação Periódica (5 em 5 segundos)**

O sistema verifica continuamente se algum alerta agendado deve ser disparado:

```python
for check in self.pending_lot_checks:
    if now_sp >= check['check_time']:
        # Tempo atingido! Verifica se lote mudou
        current_lote_check = get_lote_from_config(self.plc_name)
        if current_lote_check == check['lot']:
            # Lote não mudou - ENVIA EMAIL
            self._send_late_lot_alert(...)
```

### 5. **Envio do Email**

Quando o tempo de 3 horas é atingido:

**Cenário 1: Lote NÃO foi alterado**
- ✉️ Email é enviado aos operadores
- 📊 Confirma que a produção continuou com o mesmo lote
- ⏱️ Informa que já passaram 3 horas

**Cenário 2: Lote JÁ foi alterado**
- ✓ Email NÃO é enviado
- 📝 Um log informa que o lote foi alterado antes do disparo

**Log de Exemplo:**
```
[Cupper_22] ⏱️ ALERTA 3H DISPARADO: Lote 'LOTE001' não foi alterado após 3 horas de produção
[Cupper_22] 📧 Email de alerta do lote 'LOTE001' agendado no pool (3h).
```

Ou:
```
[Cupper_22] ✓ Lote foi alterado antes do disparo do alerta (de 'LOTE001' para 'LOTE002')
```

## Fluxograma Visual

```
┌─────────────────────────────────────┐
│  TROCA DE BOBINA DETECTADA          │
│  trigger_coil_tag = 1               │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  REGISTRA NO BANCO DE DADOS         │
│  - Consumo da bobina anterior       │
│  - Quantidade de copos              │
│  - Tipo (Completa/Parcial)          │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  AGENDA ALERTA PARA +3 HORAS        │
│  check_time = now + 3h              │
└────────────┬────────────────────────┘
             │
             ▼
        [ESPERA 3 HORAS]
             │
             ▼
┌─────────────────────────────────────┐
│  VERIFICA: LOTE MUDOU?              │
└────────┬───────────────────┬────────┘
         │                   │
     NÃO │                   │ SIM
         │                   │
         ▼                   ▼
    ┌──────────────┐    ┌──────────────┐
    │  ENVIA EMAIL │    │  NÃO ENVIA   │
    │    ✉️        │    │  ✓ (skipped) │
    └──────────────┘    └──────────────┘
```

## Estrutura de Dados

### Pendentes de Alerta

```python
{
    'check_time': datetime,      # Quando o alerta deve disparar
    'lot': str,                  # Número do lote
    'start_time': datetime       # Quando a bobina foi trocada
}
```

## Configuração Necessária

Para que o trigger funcione, o arquivo de configuração deve ter:

```json
{
    "tag_config": {
        "trigger_coil_tag": "Coil_change",  // Tag do PLC que indica troca
        "bobina_tag": "NumBobina",           // Tag com tipo de bobina
        // ... outras tags
    }
}
```

## Email Enviado

### Destinatários
- VICTOR.NASCIMENTO@CANPACK.COM
- RUI.SILVA@CANPACK.COM

### Formato
- **Assunto:** ⚠️ ALERTA 3H: Lote não trocado na [MÁQUINA]
- **Corpo:** HTML formatado com status da produção

## Logs para Monitoramento

### Logs Importantes

1. **Trigger Acionado:**
   ```
   [Cupper_22] 🔔 TRIGGER BOBINA ACIONADO: Lote 'LOTE001' - Email será enviado em DD/MM/YYYY HH:MM:SS
   ```

2. **Alerta Disparado:**
   ```
   [Cupper_22] ⏱️ ALERTA 3H DISPARADO: Lote 'LOTE001' não foi alterado após 3 horas
   ```

3. **Email Enviado:**
   ```
   [Cupper_22] 📧 Email de alerta do lote 'LOTE001' agendado no pool (3h).
   ```

4. **Lote Alterado (sem email):**
   ```
   [Cupper_22] ✓ Lote foi alterado antes do disparo do alerta (de 'LOTE001' para 'LOTE002')
   ```

## Troubleshooting

### Email não é enviado após 3 horas

**Verificar:**
1. ✓ Tag `trigger_coil_tag` está configurada corretamente?
2. ✓ PLC está enviando valor 1 quando bobina troca?
3. ✓ Serviço está rodando continuamente (sem pausas)?
4. ✓ Email SMTP está configurado em `smtp_config.py`?

### Email é enviado mas lote já foi alterado

**Verificar:**
1. ✓ Tag `lote_tag` está sendo atualizada corretamente?
2. ✓ Configuração do lote está sendo lida de `get_lote_from_config()`?

## Resumo

✅ **Sistema automático** que dispara quando bobina muda  
✅ **Aguarda 3 horas** antes de enviar notificação  
✅ **Verifica mudanças** antes de enviar (não envia se lote mudou)  
✅ **Logging detalhado** para rastreamento  
✅ **Email informativo** aos operadores  

---

**Data de Implementação:** Fevereiro de 2026  
**Versão:** 1.0
