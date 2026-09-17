param(
    [string]$BaseUri = "http://127.0.0.1:8080/api/v1"
)

$ErrorActionPreference = "Stop"

function Get-LUCIDAEffects($composition) {
    foreach ($layer in @($composition.layers)) {
        foreach ($clip in @($layer.clips)) {
            foreach ($effect in @($clip.video.effects)) {
                if ($effect.name -eq "LUCIDA Depth") {
                    [pscustomobject]@{
                        Layer = $layer.name.value
                        Clip = $clip.name.value
                        ClipId = $clip.id
                        Connected = $clip.connected.value
                        EffectId = $effect.id
                        Bypassed = $effect.bypassed.value
                        Params = $effect.params
                    }
                }
            }
        }
    }
}

try {
    $composition = Invoke-RestMethod -Uri "$BaseUri/composition" -TimeoutSec 5
    $instances = @(Get-LUCIDAEffects $composition)
    if ($instances.Count -eq 0) {
        Write-Error "No se encontró una instancia LUCIDA Depth en la composición activa."
        exit 2
    }
    foreach ($instance in $instances) {
        Write-Output ("LUCIDA Depth: layer='{0}' clip='{1}' connected='{2}' bypassed={3}" -f
            $instance.Layer, $instance.Clip, $instance.Connected, $instance.Bypassed)
        $params = $instance.Params
        foreach ($name in @("Model", "Quality", "OutputStyle", "InferenceRate", "TemporalStabilit", "EffectMix")) {
            $parameter = $params.PSObject.Properties[$name]
            if ($null -ne $parameter) {
                Write-Output ("  {0}={1}" -f $name, $parameter.Value.value)
            }
        }
    }

    $logPath = Join-Path $env:TEMP "LUCIDA_Depth_runtime.log"
    if (Test-Path -LiteralPath $logPath) {
        $lines = Get-Content -LiteralPath $logPath
        $recent = @($lines | Select-Object -Last 80)
        $shaderFailures = @($recent | Where-Object { $_ -match "shader compilation failed|contained exception|lectura de textura falló" })
        $inferences = @($recent | Where-Object { $_ -match "inference model=" })
        Write-Output ("Runtime log: {0} líneas recientes={1} shader_failures={2} inference_events={3}" -f
            $logPath, $recent.Count, $shaderFailures.Count, $inferences.Count)
        $inferences | Select-Object -Last 4 | ForEach-Object { Write-Output ("  " + $_) }
        $shaderFailures | Select-Object -Last 4 | ForEach-Object { Write-Output ("  ERROR " + $_) }
    } else {
        Write-Output "Runtime log no encontrado: todavía no se ha inicializado el efecto."
    }
} catch {
    Write-Error ("No se pudo inspeccionar Resolume en {0}: {1}" -f $BaseUri, $_.Exception.Message)
    exit 3
}
