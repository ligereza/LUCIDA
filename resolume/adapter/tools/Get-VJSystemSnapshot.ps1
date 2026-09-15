[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Get-DriveSummary {
    Get-CimInstance Win32_LogicalDisk -Filter "DriveType = 3" |
        Sort-Object DeviceID |
        ForEach-Object {
            [pscustomobject]@{
                Drive   = $_.DeviceID
                Label   = $_.VolumeName
                SizeGB  = [math]::Round($_.Size / 1GB, 1)
                FreeGB  = [math]::Round($_.FreeSpace / 1GB, 1)
                FreePct = if ($_.Size) { [math]::Round(100 * $_.FreeSpace / $_.Size, 1) } else { 0 }
            }
        }
}

function Get-ProcessSummary {
    $names = 'ResolumeAvenue', 'ResolumeArena', 'Adobe Media Encoder', 'AfterFX', 'Illustrator', 'Photoshop', 'firefox'
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $names -contains $_.ProcessName } |
        Sort-Object ProcessName |
        ForEach-Object {
            [pscustomobject]@{
                Name          = $_.ProcessName
                Id            = $_.Id
                CPUSeconds    = if ($null -ne $_.CPU) { [math]::Round($_.CPU, 1) } else { $null }
                WorkingSetGB  = [math]::Round($_.WorkingSet64 / 1GB, 2)
            }
        }
}

$computer = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$cpuLoad = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$activePowerPlan = (powercfg /getactivescheme 2>$null) -join ' '

$snapshot = [pscustomobject]@{
    TimestampLocal       = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'
    ComputerName         = if ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { $computer.Name }
    Manufacturer         = $computer.Manufacturer
    Model                = $computer.Model
    OperatingSystem      = $os.Caption
    OSVersion            = $os.Version
    Processor            = $processor.Name
    Cores                = $processor.NumberOfCores
    LogicalProcessors    = $processor.NumberOfLogicalProcessors
    MemoryGB             = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
    CurrentCpuLoadPercent = if ($null -ne $cpuLoad) { [math]::Round($cpuLoad, 1) } else { $null }
    ActivePowerPlan      = $activePowerPlan.Trim()
    Drives               = @(Get-DriveSummary)
    RelevantProcesses    = @(Get-ProcessSummary)
}

$snapshot | ConvertTo-Json -Depth 5

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $snapshot | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    Write-Host "Snapshot guardado en $OutputPath"
}
