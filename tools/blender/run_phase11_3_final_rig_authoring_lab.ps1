param(
    [string]$Blender = "",
    [string]$Repo = "",
    [string]$SourceBlend = ""
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

if (-not $SourceBlend) {
    $SourceBlend = "C:\Users\chodo\Documents\Codex\2026-09-22\x20-ko-arken-t-kezleyip-toparlanan\outputs\tokezleme_toparlanma.blend"
}

if (-not (Test-Path $SourceBlend)) {
    $searchRoot = "C:\Users\chodo\Documents\Codex\2026-09-22"
    if (Test-Path $searchRoot) {
        $candidate = Get-ChildItem -Path $searchRoot -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*toparlanma.blend" } |
            Sort-Object FullName |
            Select-Object -First 1
        if ($candidate) {
            $SourceBlend = $candidate.FullName
            Write-Host "Resolved authored source: $SourceBlend"
        }
    }
}

if (-not (Test-Path $SourceBlend)) {
    throw "Source authored stumble blend not found."
}

$script = Join-Path $Repo "tools\blender\build_stumble_recovery_final_rig_lab_v1.py"
$contract = Join-Path $Repo "data\choreography\stumble_recovery_final_rig_v1.authoring_contract.json"
$outDir = Join-Path $Repo "build\phase11_3_final_rig"
$outputBlend = Join-Path $outDir "stumble_recovery_final_rig_authoring_lab_v1.blend"
$report = Join-Path $outDir "stumble_recovery_final_rig_authoring_lab_v1_report.json"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

@($outputBlend, $report) | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Force $_
    }
}

Write-Host "PHASE 11.3 - FINAL-RIG DIRECT AUTHORING LAB"
Write-Host "Source reference: $SourceBlend"
Write-Host "Target rig:       low_poly_girl"
Write-Host "Output:           $outputBlend"
Write-Host ""

& $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --source-blend $SourceBlend --contract $contract --output-blend $outputBlend --report $report

if ($LASTEXITCODE -ne 0) {
    throw "Blender authoring-lab build failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path $outputBlend)) {
    throw "Authoring lab blend missing: $outputBlend"
}
if (-not (Test-Path $report)) {
    throw "Authoring lab report missing: $report"
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "11.3") {
    throw "Phase mismatch in authoring lab report."
}
if ($data.mode -ne "final_rig_direct_authoring") {
    throw "Authoring mode mismatch."
}
if ($data.source.frame_count -ne 49) {
    throw "Expected 49 source reference frames."
}
if ($data.policy.automated_retarget) {
    throw "Automated retarget must remain disabled."
}
if ($data.policy.source_drives_target) {
    throw "Source reference must not drive target rig."
}

Write-Host ""
Write-Host "PHASE 11.3 FINAL-RIG AUTHORING LAB PASS"
Write-Host "Frames: $($data.source.frame_start)..$($data.source.frame_end)"
Write-Host "Blend:  $outputBlend"
Write-Host "Report: $report"
