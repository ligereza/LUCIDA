[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MediaRoot,

    [string]$ProjectRoot,

    [int]$MinimumFreeGB = 20
)

$ErrorActionPreference = 'Stop'
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [ValidateSet('PASS', 'WARN', 'FAIL')]
        [string]$Status,
        [string]$Detail
    )

    $results.Add([pscustomobject]@{
        Status = $Status
        Check  = $Name
        Detail = $Detail
    })
}

if (Test-Path -LiteralPath $MediaRoot -PathType Container) {
    Add-Check 'Carpeta de medios' 'PASS' $MediaRoot
    $mediaRootResolved = (Resolve-Path -LiteralPath $MediaRoot).Path
    $mediaDrive = [System.IO.Path]::GetPathRoot($mediaRootResolved)
    $mediaDisk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID = '$($mediaDrive.TrimEnd('\'))'"
    if ($mediaDisk) {
        $freeGB = [math]::Round($mediaDisk.FreeSpace / 1GB, 1)
        if ($freeGB -lt $MinimumFreeGB) {
            Add-Check 'Espacio libre en medios' 'FAIL' "${freeGB} GB libres; mínimo configurado: ${MinimumFreeGB} GB."
        } else {
            Add-Check 'Espacio libre en medios' 'PASS' "${freeGB} GB libres en $mediaDrive."
        }
    } else {
        Add-Check 'Espacio libre en medios' 'WARN' "No se pudo consultar el volumen $mediaDrive."
    }
} else {
    Add-Check 'Carpeta de medios' 'FAIL' "No existe: $MediaRoot"
}

if ($ProjectRoot) {
    if (Test-Path -LiteralPath $ProjectRoot -PathType Container) {
        Add-Check 'Carpeta de proyecto' 'PASS' $ProjectRoot
    } else {
        Add-Check 'Carpeta de proyecto' 'FAIL' "No existe: $ProjectRoot"
    }
}

$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
if ($battery) {
    if ($battery.BatteryStatus -in 2, 6, 7, 8, 9, 11) {
        Add-Check 'Alimentación' 'PASS' 'El sistema reporta alimentación externa o estado compatible.'
    } else {
        Add-Check 'Alimentación' 'WARN' 'No se confirmó alimentación externa; conecta el cargador para el show.'
    }
} else {
    Add-Check 'Alimentación' 'WARN' 'No se pudo leer el estado de batería; confirma el cargador manualmente.'
}

$renderProcesses = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -in 'Adobe Media Encoder', 'AfterFX' }
if ($renderProcesses) {
    Add-Check 'Renders Adobe activos' 'WARN' 'Hay procesos Adobe de render activos; ciérralos si no son necesarios durante el show.'
} else {
    Add-Check 'Renders Adobe activos' 'PASS' 'No se detectaron procesos Adobe de render.'
}

$resolume = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -in 'ResolumeAvenue', 'ResolumeArena' }
if ($resolume) {
    Add-Check 'Resolume' 'PASS' 'Resolume está abierto.'
} else {
    Add-Check 'Resolume' 'WARN' 'Resolume no está abierto; ábrelo y valida el proyecto antes de salir.'
}

$gpu = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
    Where-Object { $_.Name } |
    Select-Object -ExpandProperty Name
if ($gpu) {
    Add-Check 'Adaptador de video' 'PASS' (($gpu | Select-Object -Unique) -join '; ')
} else {
    Add-Check 'Adaptador de video' 'WARN' 'No se pudo consultar el adaptador de video.'
}

$results | Format-Table -AutoSize

$failures = @($results | Where-Object Status -eq 'FAIL').Count
$warnings = @($results | Where-Object Status -eq 'WARN').Count
Write-Host "`nResultado: $failures fallo(s), $warnings advertencia(s)."

if ($failures -gt 0) {
    exit 1
}

