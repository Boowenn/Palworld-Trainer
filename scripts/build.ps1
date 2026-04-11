param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\\build"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\\dist"
}

python -m PyInstaller "$root\\PalworldTrainer.spec" --noconfirm --clean

$localGameRoot = Split-Path -Parent $root
$localGameExe = Join-Path $localGameRoot "Palworld.exe"
$builtExe = Join-Path $root "dist\\PalworldTrainer.exe"

if ((Test-Path $localGameExe) -and (Test-Path $builtExe)) {
    Copy-Item -Path $builtExe -Destination (Join-Path $localGameRoot "PalworldTrainer.exe") -Force
    Write-Host "Mirrored latest build to $localGameRoot\\PalworldTrainer.exe"
}

Write-Host "Build completed:"
Get-ChildItem "$root\\dist" -Force
