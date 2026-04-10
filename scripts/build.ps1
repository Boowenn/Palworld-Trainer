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

Write-Host "Build completed:"
Get-ChildItem "$root\\dist" -Force

