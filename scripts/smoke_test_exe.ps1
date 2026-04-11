param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExePath)) {
    throw "Executable was not found: $ExePath"
}

$resolvedExePath = (Resolve-Path $ExePath).Path
$existingProcessIds = @(
    Get-Process PalworldTrainer -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $resolvedExePath } |
        ForEach-Object { $_.Id }
)

$previousSmoke = $env:PALWORLD_TRAINER_SMOKE_TEST
$previousMarker = $env:PALWORLD_TRAINER_SMOKE_TEST_FILE
$env:PALWORLD_TRAINER_SMOKE_TEST = "1"
$markerPath = Join-Path (Split-Path -Parent $resolvedExePath) ("palworld-trainer-smoke-" + [System.Guid]::NewGuid().ToString("N") + ".txt")
$env:PALWORLD_TRAINER_SMOKE_TEST_FILE = $markerPath

try {
    & $resolvedExePath --smoke-test
} finally {
    if ($null -eq $previousSmoke) {
        Remove-Item Env:PALWORLD_TRAINER_SMOKE_TEST -ErrorAction SilentlyContinue
    } else {
        $env:PALWORLD_TRAINER_SMOKE_TEST = $previousSmoke
    }

    if ($null -eq $previousMarker) {
        Remove-Item Env:PALWORLD_TRAINER_SMOKE_TEST_FILE -ErrorAction SilentlyContinue
    } else {
        $env:PALWORLD_TRAINER_SMOKE_TEST_FILE = $previousMarker
    }
}

for ($index = 0; $index -lt $TimeoutSeconds * 4; $index++) {
    if (Test-Path $markerPath) {
        break
    }
    Start-Sleep -Milliseconds 250
}

if (-not (Test-Path $markerPath)) {
    throw "Executable smoke test did not reach the startup marker within $TimeoutSeconds seconds: $ExePath"
}

Get-Process PalworldTrainer -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $resolvedExePath -and $_.Id -notin $existingProcessIds } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Remove-Item -Path $markerPath -Force -ErrorAction SilentlyContinue
Write-Host "Executable smoke test passed: $ExePath"
