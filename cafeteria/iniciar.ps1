param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Ejecuta instalar.ps1 primero.' }
if (-not (Test-Path -LiteralPath 'models\yolov8n.pt')) { throw 'Falta el modelo. Ejecuta instalar.ps1 primero.' }
Write-Host 'Iniciando MesaVista en http://127.0.0.1:8765…'
try { $mesaState = Invoke-RestMethod 'http://127.0.0.1:8765/api/state' -TimeoutSec 2 } catch { $mesaState = $null }
if ($mesaState -and $mesaState.application -ne 'MesaVista') { throw 'El puerto 8765 está ocupado por otra aplicación.' }
if (-not $mesaState) {
    New-Item -ItemType Directory -Force -Path 'data' | Out-Null
    $mesaServer = Start-Process -FilePath $projectPython -ArgumentList 'app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'data\server-output.log') -RedirectStandardError (Join-Path $PSScriptRoot 'data\server-error.log') -PassThru
    for ($mesaAttempt = 0; $mesaAttempt -lt 30; $mesaAttempt++) {
        Start-Sleep -Milliseconds 300
        try { $mesaState = Invoke-RestMethod 'http://127.0.0.1:8765/api/state' -TimeoutSec 1; break } catch { }
    }
    if (-not $mesaState) { throw 'No se pudo iniciar. Revisa data\server-error.log.' }
}
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8765' }
Write-Host 'El servidor está en segundo plano. Usa DETENER.cmd para cerrarlo.'
