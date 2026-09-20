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

$seed = Join-Path $Repo "assets\characters\low_poly_girl\ballet_rig_calibration_seed_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_rig_profile_v1.json"
$script = Join-Path $Repo "tools\blender\build_ballet_rig_calibration_v1.py"

Write-Host "PHASE 10.6.1 - RIG CALIBRATION PROFILE"
Write-Host "No render. No animation. No GLB export."
Write-Host "Seed:    $seed"
Write-Host "Profile: $output"
Write-Host ""

& $Blender --background --python $script -- --repo $Repo --seed $seed --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected calibration profile missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.1") { throw "Calibration phase mismatch." }
if (-not $data.frame_policy.body_front_is_declared) {
    throw "BODY_FRONT must be declared."
}
if ($data.frame_policy.body_front_is_inferred_from_toes) {
    throw "BODY_FRONT must never be inferred from toes."
}
if ($data.frame_policy.pose_dependent_frame_allowed) {
    throw "Pose-dependent anatomical frame is forbidden."
}
if (-not $data.validation.passed) {
    throw "Declared anatomical frame validation failed."
}
$canonicalBoneCount = @($data.canonical_bones.PSObject.Properties).Count
if ($canonicalBoneCount -lt 24) {
    throw "Canonical rig profile is incomplete. Expected at least 24 bones, got $canonicalBoneCount."
}

Write-Host ""
Write-Host "PHASE 10.6.1 RIG CALIBRATION PASS"
Write-Host "Profile: $output"
Write-Host "SHA256:  $($data.source.sha256)"
Write-Host "Front:   $($data.declared_anatomical_frame.front -join ', ')"
Write-Host "Up:      $($data.declared_anatomical_frame.up -join ', ')"
Write-Host "Left:    $($data.declared_anatomical_frame.left -join ', ')"
