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

$inputGlb = Join-Path $Repo "assets\characters\low_poly_girl\low_poly_girl .glb"
$buildDir = Join-Path $Repo "build\phase10_5"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

$labScript = Join-Path $Repo "tools\blender\build_ballet_pose_lab_v1.py"
$contact = Join-Path $buildDir "attempt2_final_pose_contact.png"
$labReport = Join-Path $buildDir "attempt2_final_pose_report.json"

$coreScript = Join-Path $Repo "tools\blender\build_opening_reverence_v1.py"
$glb = Join-Path $buildDir "low_poly_girl_final_reverence_attempt2.glb"
$report = Join-Path $buildDir "final_reverence_attempt2_report.json"
$blend = Join-Path $buildDir "final_reverence_attempt2.blend"
$preview = Join-Path $buildDir "final_reverence_attempt2_preview.mp4"

Write-Host "============================================"
Write-Host "PAS DE RUN — FINAL REVERENCE — ATTEMPT 2/2"
Write-Host "============================================"
Write-Host ""

Write-Host "[1/2] Rendering static pose evidence..."
& $Blender --background --python $labScript -- --input $inputGlb --output $contact --report $labReport
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$lab = Get-Content $labReport -Raw | ConvertFrom-Json
if ($lab.phase -ne "10.5") { throw "Pose-lab phase mismatch." }
if ($lab.attempt -ne "2/2") { throw "Expected final attempt 2/2 pose lab." }
if ($lab.renders.Count -ne 15) { throw "Expected 15 static evidence views." }

Write-Host ""
Write-Host "[2/2] Rendering final reverence..."
& $Blender --background --python $coreScript -- --input $inputGlb --output $glb --report $report --blend-output $blend --preview $preview
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.5.2") { throw "Final reverence phase mismatch." }
if (-not $data.leg_native_ik_baked) { throw "Leg IK bake missing." }
if (-not $data.arm_roll_stable_frames_baked) { throw "Arm frame bake missing." }
if ($data.constraints_after_bake -ne 0) { throw "Constraints survived final bake." }
if ($data.temporary_controls_after_bake.Count -ne 0) { throw "Temporary controls survived final bake." }

foreach ($path in @($contact, $labReport, $glb, $report, $blend, $preview)) {
    if (-not (Test-Path $path)) { throw "Expected final-attempt output missing: $path" }
}

Write-Host ""
Write-Host "FINAL ATTEMPT 2/2 COMPLETE"
Write-Host "Pose sheet: $contact"
Write-Host "Preview:    $preview"
Write-Host "GLB:        $glb"
Write-Host "Duration:   $($data.duration_seconds)s"
