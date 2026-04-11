param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$localGameRoot = Split-Path -Parent $root
$localGameExe = Join-Path $localGameRoot "Palworld.exe"
$builtExe = Join-Path $root "dist\\PalworldTrainer.exe"
$mirroredExe = Join-Path $localGameRoot "PalworldTrainer.exe"

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\\build"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\\dist"
}

Get-Process PalworldTrainer -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -eq $builtExe -or $_.Path -eq $mirroredExe
} | Stop-Process -Force -ErrorAction SilentlyContinue

python -m PyInstaller "$root\\PalworldTrainer.spec" --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

& "$root\\scripts\\smoke_test_exe.ps1" -ExePath $builtExe

if ((Test-Path $localGameExe) -and (Test-Path $builtExe)) {
    Copy-Item -Path $builtExe -Destination (Join-Path $localGameRoot "PalworldTrainer.exe") -Force
    Write-Host "Mirrored latest build to $localGameRoot\\PalworldTrainer.exe"
}

Write-Host "Build completed:"
Get-ChildItem "$root\\dist" -Force
