param(
    [string]$Blender = "",
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

if (-not $Blender) {
    $cmd = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($cmd) { $Blender = $cmd.Source }
}

if (-not $Blender) {
    $candidates = @(
        "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 5.2 LTS\blender.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $Blender = $candidate
            break
        }
    }
}

if (-not $Blender -or -not (Test-Path $Blender)) {
    throw "Blender executable not found."
}

$inputGlb = Join-Path $Repo "assets\characters\low_poly_girl\low_poly_girl .glb"
$output = Join-Path $Repo "build\phase10_5\pose_lab_attempt1_contact.png"
$report = Join-Path $Repo "build\phase10_5\pose_lab_attempt1_report.json"
$script = Join-Path $Repo "tools\blender\build_ballet_pose_lab_v1.py"

Write-Host "PHASE 10.5 — BALLET POSE LAB — ATTEMPT 1 OF 2"
Write-Host "No animation. No GLB export."
Write-Host "Contact sheet: $output"

& $Blender --background --python $script -- --input $inputGlb --output $output --report $report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($path in @($output, $report)) {
    if (-not (Test-Path $path)) {
        throw "Expected Phase 10.5 pose-lab output missing: $path"
    }
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.5") { throw "Expected Phase 10.5 report." }
if ($data.attempt -ne "1/2") { throw "Expected attempt 1/2." }
if ($data.animation_rendered) { throw "Attempt 1 must not render animation." }
if ($data.glb_exported) { throw "Attempt 1 must not export GLB." }
if ($data.renders.Count -ne 15) { throw "Expected exactly 15 pose views." }

Write-Host ""
Write-Host "PHASE 10.5 POSE LAB ATTEMPT 1 PASS"
Write-Host "Rows:    BRAS_BAS | EN_AVANT_PASSAGE | PLACEMENT_AND_SOFTEN | ACKNOWLEDGEMENT | RISE_AND_OPEN"
Write-Host "Columns: FRONT | THREE_QUARTER | SIDE"
Write-Host "Contact: $output"
Write-Host "Report:  $report"
