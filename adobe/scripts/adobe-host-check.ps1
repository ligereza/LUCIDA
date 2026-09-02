param(
  [switch]$IncludeAfterEffects,
  [switch]$NoAutoDiscover,
  [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
$toolkitRoot = Split-Path -Parent $PSScriptRoot
$configPath = if ($ConfigPath) { [System.IO.Path]::GetFullPath($ConfigPath) } else { Join-Path $toolkitRoot "config.local.json" }
$config = $null
$configState = "missing"
if (Test-Path -LiteralPath $configPath) {
  $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  $configState = "local-config"
}

$searchRoots = @(
  "C:\Program Files\Adobe",
  "C:\Program Files (x86)\Adobe"
) | Where-Object { Test-Path -LiteralPath $_ }

function Find-AdobeExecutable([string]$name) {
  $productPattern = switch ($name) {
    "photoshop" { "^Adobe Photoshop( |$)"; break }
    "illustrator" { "^Adobe Illustrator( |$)"; break }
    "after-effects" { "^Adobe After Effects( |$)"; break }
    default { return $null }
  }
  $fileName = switch ($name) {
    "photoshop" { "Photoshop.exe"; break }
    "illustrator" { "Illustrator.exe"; break }
    "after-effects" { "AfterFX.exe"; break }
  }
  foreach ($root in $searchRoots) {
    $products = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match $productPattern } |
      Sort-Object Name -Descending
    foreach ($product in $products) {
      $candidate = Get-ChildItem -LiteralPath $product.FullName -Recurse -File -Filter $fileName -ErrorAction SilentlyContinue |
        Sort-Object FullName | Select-Object -First 1
      if ($candidate) { return $candidate.FullName }
    }
  }
  return $null
}

function Resolve-AdobeExecutable([string]$name, [string]$configured) {
  $configuredText = if ($configured) { $configured.Trim() } else { "" }
  if ($configuredText -and (Test-Path -LiteralPath $configuredText)) {
    return [pscustomobject]@{ path = $configuredText; source = "local-config" }
  }
  if (-not $NoAutoDiscover) {
    $discovered = Find-AdobeExecutable $name
    if ($discovered) {
      return [pscustomobject]@{ path = $discovered; source = "auto-discovered" }
    }
  }
  return [pscustomobject]@{
    path = if ($configuredText) { $configuredText } else { $null }
    source = if ($configuredText) { "configured-path-missing" } else { "not-found" }
  }
}

$configuredAdobe = if ($config) { $config.adobe } else { $null }
$configuredIllustrator = if ($configuredAdobe) { [string]$configuredAdobe.illustrator } else { "" }
$configuredPhotoshop = if ($configuredAdobe) { [string]$configuredAdobe.photoshop } else { "" }
$configuredAfterEffects = if ($configuredAdobe) { [string]$configuredAdobe.'after-effects' } else { "" }
$hosts = [ordered]@{
  illustrator = Resolve-AdobeExecutable "illustrator" $configuredIllustrator
  photoshop = Resolve-AdobeExecutable "photoshop" $configuredPhotoshop
}

if ($IncludeAfterEffects) {
  $hosts["after-effects"] = Resolve-AdobeExecutable "after-effects" $configuredAfterEffects
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
  $hostInfo = $hosts[$name]
  $executable = $hostInfo.path
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
    executablePresent = [bool]($executable -and (Test-Path -LiteralPath $executable))
    executableSource = $hostInfo.source
    adapter = $adapter
    adapterPresent = [bool](Test-Path -LiteralPath $adapter)
    adapterSyntax = if ($syntaxOk) { "ok" } else { "pending-or-invalid" }
    hostRuntime = if ($verifiedApps.ContainsKey($name)) { "verified-result-envelope" } else { "not-run" }
  }
}

[pscustomobject]@{
  config = $configState
  configPath = $configPath
  autoDiscovery = -not $NoAutoDiscover
  hosts = @($results)
} | ConvertTo-Json -Depth 4
