param(
  [switch]$IncludeAfterEffects
)

$ErrorActionPreference = "Stop"
$toolkitRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $toolkitRoot "config.local.json"

if (-not (Test-Path -LiteralPath $configPath)) {
  throw "Missing config.local.json. Run the local setup first."
}

$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$hosts = [ordered]@{
  illustrator = $config.adobe.illustrator
  photoshop = $config.adobe.photoshop
}

if ($IncludeAfterEffects) {
  $hosts["after-effects"] = $config.adobe.'after-effects'
}

$adapterFiles = [ordered]@{
  illustrator = Join-Path $toolkitRoot "adapters\adobe\illustrator\agent.jsx"
  photoshop = Join-Path $toolkitRoot "adapters\adobe\photoshop\agent.psjs"
}

$verifiedApps = @{}
$resultsRoot = Join-Path $toolkitRoot "jobs"
if (Test-Path -LiteralPath $resultsRoot) {
  Get-ChildItem -LiteralPath $resultsRoot -Recurse -File -Filter "*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "[\\/]adobe[\\/]results[\\/]" } |
    ForEach-Object {
      try {
        $record = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        if ($record.state -eq "completed" -and $record.app) { $verifiedApps[[string]$record.app] = $true }
      } catch {}
    }
}

if ($IncludeAfterEffects) {
  $adapterFiles["after-effects"] = Join-Path $toolkitRoot "adapters\adobe\after-effects\agent.jsx"
}

$results = foreach ($name in $hosts.Keys) {
  $executable = $hosts[$name]
  $adapter = $adapterFiles[$name]
  $syntaxOk = $false
  if (Test-Path -LiteralPath $adapter) {
    $source = Get-Content -LiteralPath $adapter -Raw
    $source = $source -replace '(?m)^#include .*$', ''
    $source | & node --check - 2>$null
    $syntaxOk = ($LASTEXITCODE -eq 0)
  }

  [pscustomobject]@{
    host = $name
    executable = $executable
    executablePresent = [bool](Test-Path -LiteralPath $executable)
    adapter = $adapter
    adapterPresent = [bool](Test-Path -LiteralPath $adapter)
    adapterSyntax = if ($syntaxOk) { "ok" } else { "pending-or-invalid" }
    hostRuntime = if ($verifiedApps.ContainsKey($name)) { "verified-result-envelope" } else { "not-run" }
  }
}

$results | ConvertTo-Json -Depth 4
