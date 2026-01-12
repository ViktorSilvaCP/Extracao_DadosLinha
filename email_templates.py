from datetime import datetime
from timezone_utils import get_current_sao_paulo_time
import re # Import regex module

def format_plc_error_message(plc_name, error_details):
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    return f"""
CANPACK BRASIL - Sistema de Monitoramento PLC
============================================

⚠️ ALERTA DE ERRO - {plc_name}
Data/Hora: {current_time}

Detalhes do Erro:
----------------
{error_details}

Status do Sistema:
----------------
• Local: Linha {plc_name}
• Tipo: Erro de Conexão
• Impacto: Interrupção na coleta de dados

Ações Recomendadas:
-----------------
1. Verificar conexão física com o PLC
2. Confirmar se o PLC está ligado e operacional
3. Validar configurações de rede
4. Verificar logs do sistema

Em caso de dúvidas, contate a equipe de TI.

--------------------------------------------
Este é um email automático - não responda
Sistema de Monitoramento PLC - CANPACK BR
"""

def format_system_status_message(error_details):
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    return f"""
CANPACK BRASIL - Sistema de Monitoramento PLC
============================================

🔴 ALERTA CRÍTICO - SISTEMA
Data/Hora: {current_time}

Status do Sistema:
----------------
• Estado: CRÍTICO
• Problema: Falha na conexão com PLCs
• Impacto: Sistema totalmente offline

Detalhes do Erro:
----------------
{error_details}

Ações Necessárias:
----------------
1. Verificar conexão de rede
2. Validar status dos PLCs
3. Verificar logs do sistema
4. Contatar equipe de manutenção

ATENÇÃO: Sistema necessita verificação imediata!

--------------------------------------------
Este é um email automático - não responda
Sistema de Monitoramento PLC - CANPACK BR
"""

def should_send_production_report(current_values, previous_values):
    """Determina se deve enviar relatório baseado nas mudanças"""
    if not previous_values or not current_values:
        return True
        
    return (current_values['feed'] != previous_values['feed'] or
            current_values['main'] != previous_values['main'] or
            current_values['size'] != previous_values['size'])
            
def format_production_report(plcs_data, lote_values):
    """Format production report for multiple PLCs"""
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    
    # --- Plain Text Version ---
    text_sections = []
    for data in plcs_data:
        # Format numbers for plain text
        formatted_main = "{:,}".format(data.main_value).replace(",", ".") if hasattr(data, 'main_value') and data.main_value is not None else "-"
        formatted_total = "{:,}".format(data.total_cups).replace(",", ".") if hasattr(data, 'total_cups') and data.total_cups is not None else "-"
        formatted_feed = f"{data.feed_value:.4f}" if hasattr(data, 'feed_value') and data.feed_value is not None else "-"
        status_text = getattr(data, 'status', 'ATIVO')

        text_section = f"""
🏭 Linha {data.plc_name}:
-------------------------
• Lote Atual:      {lote_values.get(f'Cupper_{data.plc_name}', 'N/A')}
• Bobina Saída:    {getattr(data, 'bobina_saida', 'N/A')}
• Formato:         {getattr(data, 'size', '-')}
• Feed Rate:     {formatted_feed} inch
• Contador:       {formatted_main}
• Total Acumulado: {formatted_total} copos
• Status:          {status_text}
• Status Bobina:   {getattr(data, 'bobina_saida', 'N/A')}
"""
        text_sections.append(text_section)

    overall_status_text_plain = "Monitorando"
    if any(getattr(data, 'status', 'ATIVO') == 'MANUTENÇÃO' for data in plcs_data):
        overall_status_text_plain = "Manutenção em Andamento"
    elif all(getattr(data, 'status', 'ATIVO') == 'PARADO' for data in plcs_data) and plcs_data:
        overall_status_text_plain = "Todas Paradas"
    elif any(getattr(data, 'status', 'ATIVO') == 'PARADO' for data in plcs_data):
        overall_status_text_plain = "Algumas Paradas"

    text_report = f"""
CANPACK BRASIL - Relatório de Produção
=====================================
Data/Hora: {current_time}

{"\n---\n".join(text_sections)}

Status Geral: {overall_status_text_plain}
PLCs Monitorados: {len(plcs_data)}
Status: ✅ Produção atualizada
Arquivos de detalhes anexados ao email.

--------------------------------------------
Em caso de divergência ou dúvidas, contactar: Victor.nascimento@canpack.com

--------------------------------------------
Sistema de Monitoramento PLC - CANPACK BR"""

    # --- HTML Version ---
    html_sections = []
    for data in plcs_data:
        # Define status colors based on status
        status_colors = {
            'ATIVO': {'bg': '#dbeafe', 'text': '#1e40af'},  # Blue
            'PROGRAMADA': {'bg': '#fef9c3', 'text': '#854d0e'},  # Yellow
            'PARADA': {'bg': '#fee2e2', 'text': '#991b1b'},  # Red
            'MANUTENÇÃO': {'bg': '#fef9c3', 'text': '#854d0e'}  # Yellow
        }
        
        status = getattr(data, 'status', 'ATIVO')
        status_style = status_colors.get(status, status_colors['ATIVO'])
        
        # Format the values based on status
        if status == 'PROGRAMADA':
            formatted_main = "-"
            formatted_total = "-"
        else:
            formatted_main = "{:,}".format(data.main_value).replace(",", ".") if hasattr(data, 'main_value') and data.main_value is not None else "-"
            formatted_total = "{:,}".format(data.total_cups).replace(",", ".") if hasattr(data, 'total_cups') and data.total_cups is not None else "-"
        
        formatted_feed = f"{data.feed_value:.4f}" if hasattr(data, 'feed_value') and data.feed_value is not None else "-"
        
        plc_card = f"""
            <tr>
                <td>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="border:1px solid #e5e7eb; border-radius:8px; margin-bottom:20px;">
                        <tr>
                            <td style="padding:15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td>
                                            <table cellpadding="0" cellspacing="0" border="0">
                                                <tr>
                                                    <td valign="top" width="24" style="padding-right:8px;">
                                                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#00529B" style="margin-top:3px;">
                                                            <path d="M22 22h-4v-4h-4v-4h-4v-4H8V4H4v16H2V2h2v20h18v2z"/>
                                                        </svg>
                                                    </td>
                                                    <td valign="top">
                                                        <h4 style="font-size:18px; font-weight:700; color:#1f2937; margin:0;">Linha {data.plc_name}</h4>
                                                    </td>
                                                </tr>
                                            </table>
                                            <p style="font-size:12px; color:#6b7280; margin:5px 0 0 32px;">
                                                Lote: {lote_values.get(f'Cupper_{data.plc_name}', 'N/A')} | Bobina: {getattr(data, 'bobina_consumida', 'N/A')} | Atualizado: {data.update_time}
                                            </p>
                                        </td>
                                        <td align="right" width="30%">
                                            <span style="font-size:12px; font-weight:500; background-color:{status_style['bg']}; color:{status_style['text']}; padding:4px 12px; border-radius:99px;">
                                                {status}
                                            </span>
                                        </td>
                                    </tr>
                                </table>
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" class="plc-grid" style="margin-top:20px;">
                                    <tr>
                                        <td class="plc-stat" width="20%" align="center" style="padding:8px; background-color:#f9fafb; border-radius:8px; margin:4px;">
                                            <p style="font-size:12px; font-weight:500; color:#6b7280; margin:0;">Formato</p>
                                            <p style="font-size:14px; font-weight:500; color:#374151; margin-top:3px;">{getattr(data, 'size', '-')}</p>
                                        </td>
                                        <td class="plc-stat" width="20%" align="center" style="padding:8px; background-color:#f9fafb; border-radius:8px; margin:4px;">
                                            <p style="font-size:12px; font-weight:500; color:#6b7280; margin:0;">Feed Rate</p>
                                            <p style="font-size:14px; font-weight:500; color:#374151; margin-top:3px;">{formatted_feed} inch</p>
                                        </td>
                                        <td class="plc-stat" width="20%" align="center" style="padding:8px; background-color:#f9fafb; border-radius:8px; margin:4px;">
                                            <p style="font-size:12px; font-weight:500; color:#6b7280; margin:0;">Contador</p>
                                            <p style="font-size:14px; font-weight:500; color:#374151; margin-top:3px;">{formatted_main}</p>
                                        </td>
                                        <td class="plc-stat" width="20%" align="center" style="padding:8px; background-color:#f9fafb; border-radius:8px; margin:4px;">
                                            <p style="font-size:12px; font-weight:500; color:#6b7280; margin:0;">Total Acumulado</p>
                                            <p style="font-size:14px; font-weight:500; color:#374151; margin-top:3px;">{formatted_total} copos</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        """
        html_sections.append(plc_card)

    # Read template and replace content
    with open('c:\\programs\\Extracao_DadosLinha\\template.html', 'r', encoding='utf-8') as f:
        template = f.read()

    # Find and replace the PLC cards section in the template
    start_marker = "<!-- Seção PLC -->"
    end_marker = "<!-- Informações Adicionais -->"
    
    plc_section_pattern = f"{start_marker}.*?{end_marker}"
    new_plc_section = f"""
            <!-- Seção PLC -->
            <tr>
                <td bgcolor="#ffffff" style="padding:20px 15px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="padding-bottom:10px;">
                                <h3 style="font-size:18px; font-weight:600; color:#00529B; margin:0; position:relative; padding-left:15px;">
                                    <div style="position:absolute; top:8px; left:0; width:8px; height:8px; background-color:#FF6B00; border-radius:50%;"></div>
                                    Linhas de Produção
                                </h3>
                            </td>
                        </tr>
                        {''.join(html_sections)}
                    </table>
                </td>
            </tr>
            <!-- Informações Adicionais -->
    """

    # Replace the dynamic content
    html_report = re.sub(
        plc_section_pattern,
        new_plc_section,
        template,
        flags=re.DOTALL
    ).replace(
        '16/06/2023 14:30:45',
        current_time
    ).replace(
        '<p class="stat-value">4</p>',
        f'<p class="stat-value">{len(plcs_data)}</p>'
    )

    return {'text': text_report, 'html': html_report}

def format_critical_error_message(error_details, traceback_info=None):
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    return f"""
CANPACK BRASIL - ALERTA CRÍTICO DO SISTEMA
=========================================

⚠️ ERRO CRÍTICO DO SISTEMA
Data/Hora: {current_time}

Detalhes do Erro:
---------------
Tipo: Erro Crítico do Sistema
Mensagem: {error_details}

Informações Técnicas:
------------------
{traceback_info if traceback_info else 'Não disponível'}

Ações Necessárias:
----------------
1. Verificar logs do sistema em F:\\Doc_Comp\\(Publico)\\Dados\\ControlLogix\\logs
2. Reiniciar o serviço se necessário
3. Verificar conectividade com PLCs
4. Contatar equipe de suporte técnico

ATENÇÃO: Sistema pode estar comprometido!

--------------------------------------------
Este é um email automático - não responda
Sistema de Monitoramento PLC - CANPACK BR
"""

def format_lote_notification(lote_value, plc_name, config_info):
    """Formata email de notificação de lote inserido"""
    current_time = get_current_sao_paulo_time().strftime("%d/%m/%Y %H:%M:%S")
    
    # Text version
    text_message = f"""
CANPACK BRASIL - Lote Inserido com Sucesso
=========================================

✅ LOTE INSERIDO COM SUCESSO
Data/Hora: {current_time}

Detalhes do Lote:
----------------
• Código do Lote: {lote_value}
• Linha de Produção: {plc_name}
• Status: Inserido no PLC e Configuração

Informações Técnicas:
-------------------
• PLC: {plc_name}
• IP do PLC: {config_info.get('plc_config', {}).get('ip_address', 'N/A')}
• Tag do Lote: {config_info.get('tag_config', {}).get('lote_tag', 'N/A')}

--------------------------------------------
Este é um email automático - não responda
Sistema de Monitoramento PLC - CANPACK BR
"""

    # HTML version
    html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Lote Inserido - {plc_name}</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #059669; margin: 0;">✅ Lote Inserido com Sucesso</h1>
            <p style="color: #6b7280; margin: 10px 0 0 0;">CANPACK BRASIL - Sistema de Controle de Bobinas</p>
        </div>
        
        <div style="background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 20px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0; color: #1e40af;">Detalhes do Lote</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">Código do Lote:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{lote_value}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">Linha de Produção:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{plc_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">Data/Hora:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{current_time}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">Status:</td>
                    <td style="padding: 8px 0; color: #059669; font-weight: bold;">✅ Inserido no PLC e Configuração</td>
                </tr>
            </table>
        </div>
        
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px;">
            <h3 style="margin: 0 0 15px 0; color: #92400e;">Informações Técnicas</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">PLC:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{plc_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">IP do PLC:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{config_info.get('plc_config', {}).get('ip_address', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #374151;">Tag do Lote:</td>
                    <td style="padding: 8px 0; color: #6b7280;">{config_info.get('tag_config', {}).get('lote_tag', 'N/A')}</td>
                </tr>
            </table>
        </div>
        
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <p style="color: #6b7280; font-size: 12px; margin: 0;">
                Este é um email automático - não responda<br>
                Sistema de Monitoramento PLC - CANPACK BR
            </p>
        </div>
    </div>
</body>
</html>
"""

    return {'text': text_message, 'html': html_message}

def format_feed_unknown_alert_email(plc_name, feed_value, lote, bobina, timestamp):
    # Texto simples
    text = f"""
ALERTA DO SISTEMA DE CONTROLE DE BOBINAS
========================================
Linha: {plc_name}
Tamanho de copo detectado: DESCONHECIDO
Feed detectado: {feed_value}
Lote: {lote}
Bobina: {bobina}
Hora da detecção: {timestamp}

Atenção: O sistema identificou um valor de tamanho de copo que não está sendo controlado pelo sistema de bobinas.
Verifique a configuração da máquina e atualize o sistema com o tamanho correto do copo.

AÇÃO IMEDIATA: Envie um e-mail para victor.nascimento@canpack.com para cadastrar a configuração correta de passo do Die Set.
"""
    # HTML bonito, compatível com o template base
    html = f'''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta: Tamanho de Copo Desconhecido</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
        body {{
            font-family: 'Poppins', Arial, sans-serif;
            background-color: #f8fafc;
            margin: 0;
            padding: 0;
            color: #1e293b;
        }}
        .email-container {{
            max-width: 700px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.05);
        }}
        .alert-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 999px;
            background-color: #fef3c7;
            color: #92400e;
            font-weight: 600;
            font-size: 14px;
        }}
        .alert-badge:before {{
            content: "⚠️";
        }}
        .divider {{
            height: 1px;
            background: linear-gradient(90deg, rgba(251, 191, 36, 0.1), rgba(251, 191, 36, 0.5), rgba(251, 191, 36, 0.1));
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <center>
        <table class="email-container" width="100%" cellpadding="0" cellspacing="0" border="0">
            <!-- Header -->
            <tr>
                <td bgcolor="#f97316" style="background: linear-gradient(135deg, #f97316, #ea580c); padding: 28px 24px; color: white;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="text-align: left;">
                                <h1 style="font-size: 22px; margin: 0; font-weight: 700; letter-spacing: -0.5px;">⚠️ ALERTA DO SISTEMA DE BOBINAS</h1>
                                <p style="font-size: 15px; margin: 8px 0 0 0; opacity: 0.9;">Tamanho de copo não reconhecido</p>
                            </td>
                            <td style="text-align: right; width: 80px;">
                                <div style="display: inline-block; background-color: rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 8px;">
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 20C7.59 20 4 16.41 4 12C4 7.59 7.59 4 12 4C16.41 4 20 7.59 20 12C20 16.41 16.41 20 12 20Z" fill="white"/>
                                        <path d="M11 7H13V9H11V7ZM11 11H13V17H11V11Z" fill="white"/>
                                    </svg>
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- Content -->
            <tr>
                <td style="padding: 32px 28px;">
                    <h2 style="font-size: 18px; color: #ea580c; font-weight: 600; margin: 0 0 16px 0; letter-spacing: -0.3px;">
                        ATENÇÃO: Tamanho de copo não cadastrado detectado
                    </h2>
                    
                    <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 24px 0;">
                        O sistema identificou um valor de tamanho de copo que não está sendo controlado pelo sistema de bobinas. 
                        Isso pode afetar a qualidade da produção e o controle de estoque.
                    </p>

                    <!-- Alert Box -->
                    <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 18px; border-radius: 8px; margin-bottom: 24px;">
                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td width="24" valign="top" style="padding-right: 12px;">
                                    <div style="background-color: #f59e0b; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 20C7.59 20 4 16.41 4 12C4 7.59 7.59 4 12 4C16.41 4 20 7.59 20 12C20 16.41 16.41 20 12 20Z" fill="white"/>
                                            <path d="M11 7H13V9H11V7ZM11 11H13V17H11V11Z" fill="white"/>
                                        </svg>
                                    </div>
                                </td>
                                <td>
                                    <p style="margin: 0; font-size: 15px; color: #92400e; font-weight: 600;">
                                        Ação Requerida
                                    </p>
                                    <p style="margin: 6px 0 0 0; font-size: 14px; color: #92400e; line-height: 1.5;">
                                        Envie um e-mail para <a href="mailto:victor.nascimento@canpack.com" style="color: #ea580c; font-weight: 600; text-decoration: none;">victor.nascimento@canpack.com</a> 
                                        com a configuração correta do Die Set para cadastro imediato.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </div>

                    <!-- Details Card -->
                    <div style="border: 1px solid #f3f4f6; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05); margin-bottom: 28px;">
                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td style="padding: 20px; background-color: #fff7ed;">
                                    <p style="margin: 0; font-size: 15px; color: #92400e; font-weight: 600;">
                                        Detalhes da Ocorrência
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 0 20px 20px;">
                                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size: 14px;">
                                        <tr>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #64748b;">Linha de Produção</td>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #1e293b; font-weight: 500; text-align: right;">{plc_name}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #64748b;">Tamanho Detectado</td>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #b45309; font-weight: 600; text-align: right;">DESCONHECIDO</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #64748b;">Feed Detectado</td>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #1e293b; font-weight: 500; text-align: right;">{feed_value}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #64748b;">Lote</td>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #1e293b; font-weight: 500; text-align: right;">{lote}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #64748b;">Bobina</td>
                                            <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #1e293b; font-weight: 500; text-align: right;">{bobina}</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 12px 0; color: #64748b;">Hora da Detecção</td>
                                            <td style="padding: 12px 0; color: #1e293b; font-weight: 500; text-align: right;">{timestamp}</td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </div>

                    <!-- Possible Causes -->
                    <div style="margin-bottom: 24px;">
                        <p style="font-size: 15px; color: #475569; margin: 0 0 12px 0; font-weight: 600;">Possíveis causas:</p>
                        <ul style="margin: 0 0 0 18px; padding: 0; color: #92400e;">
                            <li style="margin-bottom: 8px; padding-left: 8px;">Configuração incorreta da máquina</li>
                            <li style="margin-bottom: 8px; padding-left: 8px;">Bobina não cadastrada no sistema</li>
                            <li style="margin-bottom: 8px; padding-left: 8px;">Falha na comunicação com o PLC</li>
                            <li style="padding-left: 8px;">Alteração não autorizada nos parâmetros</li>
                        </ul>
                    </div>

                    <div class="divider"></div>

                    <!-- Footer Note -->
                    <p style="font-size: 13px; color: #9ca3af; margin: 0; text-align: center;">
                        Este é um alerta automático gerado pelo Sistema de Controle de Bobinas. Não responda este e-mail.
                    </p>
                </td>
            </tr>

            <!-- Footer -->
            <tr>
                <td bgcolor="#f8fafc" style="padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                    <p style="font-size: 12px; color: #94a3b8; margin: 0;">
                        © 2025 Sistema de Controle de Bobinas - Canpack Group. Todos os direitos reservados.
                    </p>
                </td>
            </tr>
        </table>
    </center>
</body>
</html>
'''
    return {"text": text, "html": html}
