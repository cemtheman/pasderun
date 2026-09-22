param(
    [string]$Godot = "",
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if (-not $Godot) {
    $candidate = "C:\Users\chodo\OneDrive\Belgeler\Godot_v4.7.2\Godot_v4.7.2-stable_win64.exe"
    if (Test-Path $candidate) { $Godot = $candidate }
}
if (-not $Godot -or -not (Test-Path $Godot)) {
    throw "Godot 4.7.2 executable not found. Pass -Godot explicitly."
}

Write-Host "PHASE 11 - 30-60s GAMEPLAY DENSITY"
Write-Host "Three full-piece 1.3-unit gaps at X=175.448, 184.832, 227.556"
Write-Host ""

& python (Join-Path $Repo "tools\music_analyzer\test_phase11_30_60_gameplay_density.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& python (Join-Path $Repo "tools\music_analyzer\test_full_audio_runway.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& python (Join-Path $Repo "tools\music_analyzer\test_phase9_graceful_opening_full_piece_runtime.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Godot --headless --editor --path $Repo --quit-after 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "PHASE 11 30-60s GAMEPLAY DENSITY SOURCE PROOF PASS"
Write-Host "New gaps:        3"
Write-Host "Gap length:      1.3"
Write-Host "Fork/ramp clash: NONE"
Write-Host "Accepted 0-120:  UNCHANGED"
Write-Host "Runtime visual:  HUMAN CHECK NEXT"
