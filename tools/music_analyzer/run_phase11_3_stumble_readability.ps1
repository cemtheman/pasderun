param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host "PHASE 11.3 STUMBLE READABILITY"
Write-Host "Repo: $Repo"

Push-Location $Repo
try {
    & $Python "tools/music_analyzer/test_phase11_3_stumble_readability.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    git diff --check origin/main...HEAD
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "PHASE11_3_STUMBLE_READABILITY=PASS"
}
finally {
    Pop-Location
}
