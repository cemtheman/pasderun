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

Write-Host "PHASE 10.12 - OPENING REVERENCE RUN HANDOFF"
Write-Host "Audience-facing BOW/READY -> command -> EXIT_TURN -> RUN/music t=0"
Write-Host ""

& python (Join-Path $Repo "tools\music_analyzer\test_phase10_12_opening_handoff.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& python (Join-Path $Repo "tools\music_analyzer\test_phase10_3_single_humanoid_motion_authority.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Godot --headless --editor --path $Repo --quit-after 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "PHASE 10.12 OPENING HANDOFF SOURCE PROOF PASS"
Write-Host "Audience hold:    REQUIRED"
Write-Host "Exit turn:        BEFORE RUN"
Write-Host "Music release:    POST-TURN t=0"
Write-Host "Dancer physics:   SINGLE AUTHORITY"
Write-Host "Runtime visual:   HUMAN CHECK NEXT"
