$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PIP_NO_INDEX = '0'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
$mesaTorch = 'torch'
$mesaVision = 'torchvision'
if (Test-Path -LiteralPath 'requirements-lock.txt') {
    $mesaTorch = Get-Content -LiteralPath 'requirements-lock.txt' | Where-Object { $_ -like 'torch==*' } | Select-Object -First 1
    $mesaVision = Get-Content -LiteralPath 'requirements-lock.txt' | Where-Object { $_ -like 'torchvision==*' } | Select-Object -First 1
}
python -m pip --python .venv install $mesaTorch $mesaVision --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar PyTorch.' }
$mesaRequirements = if (Test-Path -LiteralPath 'requirements-lock.txt') { 'requirements-lock.txt' } else { 'requirements.txt' }
python -m pip --python .venv install -r $mesaRequirements
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& '.\.venv\Scripts\python.exe' download_model.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar el modelo.' }
Write-Host 'Listo. Abre INICIAR.cmd para presentar MesaVista.'
