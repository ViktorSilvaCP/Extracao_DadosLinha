# Script para instalar o monitoramento via Agendador de Tarefas do Windows
# Execute o PowerShell como Administrador

$ServiceName = "CanpackPLCMonitor"
$ScriptPath = $PSScriptRoot
$AppScript = Join-Path $ScriptPath "app.py"
$ServiceUser = "SYSTEM"       # Ex: "CANPACK\svc_monitor"
$ServicePassword = ""         # Ex: "SenhaSegura123"

# 1. Verifica Permissões de Admin
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Este script precisa ser executado como Administrador!"
    exit
}

# 2. Tenta encontrar o Python
try {
    $PythonPath = (Get-Command python).Source
} catch {
    $PythonPath = "C:\Python313\python.exe"
}

if (-not (Test-Path $PythonPath)) {
    Write-Error "Python não encontrado em $PythonPath"
    exit 1
}

# 3. Limpeza de tarefa anterior
Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false -ErrorAction SilentlyContinue

# 4. Configuração da Tarefa
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $AppScript -WorkingDirectory $ScriptPath
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# 5. Registrar Tarefa
if ($ServiceUser -eq "SYSTEM") {
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount
    Register-ScheduledTask -TaskName $ServiceName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Sistema de Monitoramento PLC - CANPACK (Via Task Scheduler)"
} else {
    # Instalação com usuário específico (Requer senha)
    $Principal = New-ScheduledTaskPrincipal -UserId $ServiceUser -LogonType Password -RunLevel Highest
    Register-ScheduledTask -TaskName $ServiceName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -User $ServiceUser -Password $ServicePassword -Description "Sistema de Monitoramento PLC - CANPACK (Via Task Scheduler)"
}

Write-Host "✅ Tarefa '$ServiceName' instalada com sucesso!"
Write-Host "Iniciando tarefa..."
Start-ScheduledTask -TaskName $ServiceName