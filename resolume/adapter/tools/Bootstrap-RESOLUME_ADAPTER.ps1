[CmdletBinding()]
param(
    [switch]$Gpu,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    throw "No se encontro Python 3.11+ en PATH."
}

$venvPath = Join-Path $repositoryRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $python.Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual en $venvPath"
    }
}

& $venvPython -m pip install -r (Join-Path $repositoryRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron instalar las dependencias base de RESOLUME_ADAPTER."
}

if ($Dev) {
    & $venvPython -m pip install -r (Join-Path $repositoryRoot "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias de desarrollo."
    }
}

if ($Gpu) {
    & $venvPython -m pip install -r (Join-Path $repositoryRoot "requirements-gpu.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias GPU."
    }
}

Write-Output "RESOLUME_ADAPTER listo en $venvPath"
Write-Output "Uso: .\tools\Invoke-RESOLUME_ADAPTER.ps1 --help"
