param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$calibration = Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_rig_profile_v1.json"
$spec = Join-Path $Repo "assets\ballet_motion\canonical_ballet_skeleton_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$script = Join-Path $Repo "tools\ballet_motion\build_canonical_ballet_profile_v1.py"

if (-not (Test-Path $calibration)) {
    $calibrationRunner = Join-Path $Repo "tools\blender\run_ballet_rig_calibration_v1.ps1"
    if (-not (Test-Path $calibrationRunner)) {
        throw "Phase 10.6.1 calibration runner missing: $calibrationRunner"
    }

    Write-Host "Phase 10.6.1 calibration profile missing; generating prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $calibrationRunner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $calibration)) {
        throw "Phase 10.6.1 calibration did not produce expected profile: $calibration"
    }
}

Write-Host "PHASE 10.6.2 - CANONICAL BALLET SKELETON"
Write-Host "No Blender runtime. No render. No pose. No animation."
Write-Host "Calibration: $calibration"
Write-Host "Spec:        $spec"
Write-Host "Output:      $output"
Write-Host ""

python $script --repo $Repo --calibration $calibration --spec $spec --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.2 output missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.2") { throw "Canonical profile phase mismatch." }
if ($data.body_frame.front_policy -ne "DECLARED_BY_RIG_CALIBRATION_ONLY") {
    throw "Canonical BODY_FRONT policy mismatch."
}
if (-not $data.validator_foundation.source_sha_match) {
    throw "Source SHA binding failed."
}
if (-not $data.validator_foundation.canonical_graph_valid) {
    throw "Canonical graph validation failed."
}
if (-not $data.validator_foundation.all_bind_rotations_right_handed) {
    throw "Bind rotation handedness validation failed."
}
$canonicalBoneCount = @($data.canonical_bones.PSObject.Properties).Count
if ($canonicalBoneCount -ne 24) {
    throw "Expected exactly 24 canonical bones, got $canonicalBoneCount."
}

Write-Host ""
Write-Host "PHASE 10.6.2 CANONICAL BALLET SKELETON PASS"
Write-Host "Profile: $output"
Write-Host "Bones:   $canonicalBoneCount"
Write-Host "Front:   DECLARED_BY_RIG_CALIBRATION_ONLY"
