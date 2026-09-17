param(
    [string]$BuildRoot = (Join-Path $PSScriptRoot '..\..\..\work\resolume-plugin-build')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$downloads = Join-Path $BuildRoot 'downloads'
$resources = Join-Path $downloads 'depthgen-resources'
$ortRoot = Join-Path $BuildRoot 'deps\ort-dml-1.17.3'
New-Item -ItemType Directory -Force -Path $downloads, $resources | Out-Null

function Get-VerifiedFile([string]$Path, [string]$Url, [string]$ExpectedSha256) {
    if (!(Test-Path -LiteralPath $Path)) {
        Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $Path. Expected $ExpectedSha256, got $actual."
    }
}

$release = Join-Path $downloads 'DepthGen.aex'
Get-VerifiedFile $release `
    'https://github.com/palf-gh/DepthGen/releases/download/v1.0.1/DepthGen.aex' `
    '800b5b3ed758b147ced86ef2e0cad638abded87be9146b91c43bd0142f027fef'

$ortZip = Join-Path $downloads 'Microsoft.ML.OnnxRuntime.DirectML.1.17.3.zip'
Get-VerifiedFile $ortZip `
    'https://github.com/microsoft/onnxruntime/releases/download/v1.17.3/Microsoft.ML.OnnxRuntime.DirectML.1.17.3.zip' `
    '60e5e2d86a900d5d292266dc400e81c41f51d54d8e76e1654b069f5a4c95f250'

if (!(Test-Path -LiteralPath (Join-Path $ortRoot 'build\native\include\onnxruntime_cxx_api.h'))) {
    New-Item -ItemType Directory -Force -Path $ortRoot | Out-Null
    Expand-Archive -LiteralPath $ortZip -DestinationPath $ortRoot -Force
}

if (!('LUCIDAResourceExtractor' -as [type])) {
    Add-Type @'
using System;
using System.IO;
using System.Runtime.InteropServices;
public static class LUCIDAResourceExtractor {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr LoadLibraryEx(string name, IntPtr file, uint flags);
  [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
  [DllImport("kernel32.dll")] static extern IntPtr FindResource(IntPtr module, IntPtr name, IntPtr type);
  [DllImport("kernel32.dll")] static extern IntPtr LoadResource(IntPtr module, IntPtr resource);
  [DllImport("kernel32.dll")] static extern IntPtr LockResource(IntPtr resource);
  [DllImport("kernel32.dll")] static extern uint SizeofResource(IntPtr module, IntPtr resource);
  public static void Extract(string pe, int id, string output) {
    var module = LoadLibraryEx(pe, IntPtr.Zero, 2);
    if (module == IntPtr.Zero) throw new Exception("LoadLibraryEx failed: " + Marshal.GetLastWin32Error());
    try {
      var resource = FindResource(module, new IntPtr(id), new IntPtr(10));
      var loaded = resource == IntPtr.Zero ? IntPtr.Zero : LoadResource(module, resource);
      var data = loaded == IntPtr.Zero ? IntPtr.Zero : LockResource(loaded);
      var size = resource == IntPtr.Zero ? 0U : SizeofResource(module, resource);
      if (data == IntPtr.Zero || size == 0) throw new Exception("Missing RCDATA resource " + id);
      var bytes = new byte[size];
      Marshal.Copy(data, bytes, 0, (int)size);
      Directory.CreateDirectory(Path.GetDirectoryName(output));
      File.WriteAllBytes(output, bytes);
    } finally { FreeLibrary(module); }
  }
}
'@
}

$expected = @{
    256 = @{Name='zipdepth_base_npu_dynamic.onnx'; Hash='0741a0d574609da33c5081b1054a2dd1e8845ecdbed9a5f69c48807c22400d59'}
    257 = @{Name='depth_anything_v2_vits_dml.onnx'; Hash='237cfaaf329bc97b9914c14e2d2497b1159cc05cca1b6d7a68aa42a262ea99bf'}
    258 = @{Name='DepthGen-onnxruntime.dll'; Hash='e268219a33cf3898c16ae364efc79a4a656c87d2ee67fd872b079aca769fd97e'}
}
foreach ($id in $expected.Keys) {
    $destination = Join-Path $resources $expected[$id].Name
    [LUCIDAResourceExtractor]::Extract($release, $id, $destination)
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected[$id].Hash) {
        throw "SHA-256 mismatch for embedded resource $id. Expected $($expected[$id].Hash), got $actual."
    }
}

Write-Output "DepthGen resources ready: $resources"
Write-Output "ONNX Runtime headers ready: $ortRoot"
