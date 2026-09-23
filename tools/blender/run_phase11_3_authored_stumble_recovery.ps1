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
    $SourceBlend = "C:\Users\chodo\Documents\Codex\2026-09-22\x20-ko-arken-t-kezleyip-toparlanan\outputs\tokezleme\_toparlanma.blend"
}

if (-not (Test-Path $SourceBlend)) {
    $searchRoot = "C:\Users\chodo\Documents\Codex\2026-09-22"
    if (Test-Path $searchRoot) {
        $candidate = Get-ChildItem -Path $searchRoot -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -eq "_toparlanma.blend" -or
                $_.Name -like "*toparlanma.blend"
            } |
            Sort-Object FullName |
            Select-Object -First 1

        if ($candidate) {
            $SourceBlend = $candidate.FullName
            Write-Host "Resolved authored source: $SourceBlend"
        }
    }
}

if (-not (Test-Path $SourceBlend)) {
    throw "Source authored stumble blend not found. Pass -SourceBlend explicitly if it lives outside C:\Users\chodo\Documents\Codex\2026-09-22."
}

$script = Join-Path $Repo "tools\blender\build_stumble_recovery_v1.py"
$contract = Join-Path $Repo "data\choreography\stumble_recovery_v1.retarget_contract.json"
$outDir = Join-Path $Repo "build\phase11_3_authored"
$outputBlend = Join-Path $outDir "stumble_recovery_retargeted_v1.blend"
$preview = Join-Path $outDir "stumble_recovery_v1_preview.mp4"
$report = Join-Path $outDir "stumble_recovery_v1_report.json"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "PHASE 11.3 - AUTHORED STUMBLE / RECOVERY RETARGET"
Write-Host "Source:  $SourceBlend"
Write-Host "Target:  low_poly_girl"
Write-Host "Preview: $preview"
Write-Host ""

& $Blender --background --python $script -- --repo $Repo --source-blend $SourceBlend --contract $contract --output-blend $outputBlend --preview $preview --report $report

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $outputBlend)) {
    throw "Retargeted Blender output missing: $outputBlend"
}
if (-not (Test-Path $preview)) {
    throw "Preview video missing: $preview"
}
if (-not (Test-Path $report)) {
    throw "Retarget report missing: $report"
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "11.3") {
    throw "Phase mismatch in retarget report."
}
if ($data.action -ne "stumble_recovery_v1") {
    throw "Target action mismatch."
}
if ($data.source.frame_count -ne 49) {
    throw "Expected 49 authored source frames."
}
if (-not $data.retarget.forward_root_translation_removed) {
    throw "Forward root translation must remain gameplay-owned."
}

Write-Host ""
Write-Host "PHASE 11.3 AUTHORED RETARGET PASS"
Write-Host "Frames:  $($data.source.frame_start)..$($data.source.frame_end)"
Write-Host "FPS:     $($data.source.fps)"
Write-Host "Scale:   $($data.target.leg_scale_ratio)"
Write-Host "Blend:   $outputBlend"
Write-Host "Preview: $preview"
Write-Host "Report:  $report"
