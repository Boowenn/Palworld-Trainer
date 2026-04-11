param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\\release"
}

powershell -ExecutionPolicy Bypass -File "$root\\scripts\\build.ps1" @(
    if ($Clean) { "-Clean" }
)

$env:PYTHONPATH = "$root\\src"
$version = python -c "from palworld_trainer import __version__; print(__version__)"
if (-not $version) {
    throw "Unable to resolve package version."
}

$releaseDir = Join-Path $root "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

$releaseExeName = "PalworldTrainer-v$version-win64.exe"
$releaseExePath = Join-Path $releaseDir $releaseExeName
$archiveName = "PalworldTrainer-v$version-win64.zip"
$archivePath = Join-Path $releaseDir $archiveName
$exeHashPath = "$releaseExePath.sha256"
$hashPath = "$archivePath.sha256"

Copy-Item -Path "$root\\dist\\PalworldTrainer.exe" -Destination $releaseExePath -Force
Compress-Archive -Path "$root\\dist\\PalworldTrainer.exe" -DestinationPath $archivePath -Force

$exeHash = Get-FileHash -Algorithm SHA256 $releaseExePath
"$($exeHash.Hash.ToLower())  $releaseExeName" | Set-Content -Path $exeHashPath -Encoding ascii

$hash = Get-FileHash -Algorithm SHA256 $archivePath
"$($hash.Hash.ToLower())  $archiveName" | Set-Content -Path $hashPath -Encoding ascii

Write-Host "Release package completed:"
Get-ChildItem $releaseDir -Force
