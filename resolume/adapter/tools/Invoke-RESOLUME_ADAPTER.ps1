[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$ResolumeAdapterArgument
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$cliPath = Join-Path $repositoryRoot "tools\resolume_adapter_cli.py"
$venvPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonCommand = $venvPython
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        throw "No se encontro Python. Ejecuta tools\Bootstrap-RESOLUME_ADAPTER.ps1 o instala Python 3.11+."
    }
    $pythonCommand = $python.Source
}

if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) {
    throw "No se encontro la CLI de RESOLUME_ADAPTER: $cliPath"
}

& $pythonCommand $cliPath @ResolumeAdapterArgument
exit $LASTEXITCODE
