param(
    [string]$Blender = "",
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

if (-not $Blender) {
    $candidate = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
    if (Test-Path $candidate) { $Blender = $candidate }
}

if (-not $Blender -or -not (Test-Path $Blender)) {
    throw "Blender 5.2 executable not found."
}

$script = Join-Path $Repo "tools\blender\author_stumble_keyposes_a_v1.py"
$outDir = Join-Path $Repo "build\phase11_3_final_rig"
$inputBlend = Join-Path $outDir "stumble_recovery_final_rig_authoring_lab_v1.blend"
$outputBlend = Join-Path $outDir "stumble_recovery_final_rig_keyposes_a_v1.blend"
$preview = Join-Path $outDir "stumble_recovery_final_rig_keyposes_a_v1_preview.mp4"
$report = Join-Path $outDir "stumble_recovery_final_rig_keyposes_a_v1_report.json"

if (-not (Test-Path $inputBlend)) {
    throw "Final-rig authoring lab missing. Run run_phase11_3_final_rig_authoring_lab.ps1 first."
}

@($outputBlend, $preview, $report) | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Force $_
    }
}

Write-Host "PHASE 11.3 - FINAL-RIG KEYPOSES A"
Write-Host "Input:   $inputBlend"
Write-Host "Output:  $outputBlend"
Write-Host "Preview: $preview"
Write-Host ""

& $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --input-blend $inputBlend --output-blend $outputBlend --preview $preview --report $report

if ($LASTEXITCODE -ne 0) {
    throw "Blender keyposes A build failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path $outputBlend)) {
    throw "Keyposes A blend missing: $outputBlend"
}
if (-not (Test-Path $preview)) {
    throw "Keyposes A preview missing: $preview"
}
if (-not (Test-Path $report)) {
    throw "Keyposes A report missing: $report"
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "11.3") {
    throw "Phase mismatch in keyposes A report."
}
if ($data.mode -ne "final_rig_direct_keyposes_a") {
    throw "Authoring mode mismatch."
}
if ($data.source_transform_sampling) {
    throw "Source transforms must not drive authored target poses."
}
if ($data.poses.Count -ne 3) {
    throw "Expected exactly three authored key poses."
}

Write-Host ""
Write-Host "PHASE 11.3 FINAL-RIG KEYPOSES A PASS"
Write-Host "Preview: $preview"
Write-Host "Report:  $report"
