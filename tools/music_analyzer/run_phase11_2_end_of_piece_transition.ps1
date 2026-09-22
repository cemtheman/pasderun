param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host "PHASE 11.2 END-OF-PIECE TRANSITION"
Write-Host "Repo: $Repo"

Push-Location $Repo
try {
    & $Python "tools/music_analyzer/test_phase11_2_end_of_piece_transition.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python "tools/music_analyzer/test_phase9_graceful_opening_full_piece_runtime.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    git diff --check origin/main...HEAD
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "PHASE11_2_END_OF_PIECE_TRANSITION=PASS"
}
finally {
    Pop-Location
}
