# Script para remover a tarefa agendada
# Execute o PowerShell como Administrador

$ServiceName = "CanpackPLCMonitor"

if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Este script precisa ser executado como Administrador!"
    exit
}

Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "✅ Tarefa '$ServiceName' removida."