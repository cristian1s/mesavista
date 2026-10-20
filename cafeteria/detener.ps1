$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath 'data\server.json') {
    $mesaMetadata = Get-Content -LiteralPath 'data\server.json' -Raw | ConvertFrom-Json
    $mesaPid = [int]$mesaMetadata.pid
    $mesaProcess = Get-Process -Id $mesaPid -ErrorAction SilentlyContinue
    $mesaEpoch = [datetime]::new(1970,1,1,0,0,0,[DateTimeKind]::Utc)
    $mesaStartMatches = $false
    if ($mesaProcess) { $mesaStartMatches = [math]::Abs(($mesaProcess.StartTime.ToUniversalTime() - $mesaEpoch).TotalSeconds - [double]$mesaMetadata.started_epoch) -lt 2 }
    if ($mesaProcess -and $mesaProcess.Path -eq $mesaMetadata.executable -and $mesaStartMatches) {
        Stop-Process -Id $mesaPid
        Write-Host 'MesaVista se ha detenido. El historial permanece guardado.'
    } else { Write-Host 'No se encontró el servidor de esta carpeta.' }
} else { Write-Host 'No hay un servidor registrado en esta carpeta.' }
