param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$canonical = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$grammar = Join-Path $Repo "assets\ballet_motion\ballet_pose_grammar_v1.json"
$fixtures = Join-Path $Repo "assets\ballet_motion\ballet_pose_fixtures_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_pose_grammar_profile_v1.json"
$script = Join-Path $Repo "tools\ballet_motion\build_ballet_pose_grammar_profile_v1.py"

if (-not (Test-Path $constraints)) {
    $runner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_3_anatomical_constraints.ps1"
    if (-not (Test-Path $runner)) {
        throw "Phase 10.6.3 runner missing: $runner"
    }

    Write-Host "Phase 10.6.3 constraint profile missing; generating prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $runner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $constraints)) {
        throw "Phase 10.6.3 did not produce expected profile: $constraints"
    }
}

if (-not (Test-Path $canonical)) {
    throw "Phase 10.6.2 canonical profile missing after prerequisite generation."
}

Write-Host "PHASE 10.6.4 - BALLET POSE GRAMMAR AND GEOMETRIC VALIDATORS"
Write-Host "No Blender runtime. No render. No pose synthesis. No animation."
Write-Host ""

python $script --canonical-profile $canonical --constraint-profile $constraints --grammar $grammar --fixtures $fixtures --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.4 output missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.4") { throw "Pose grammar phase mismatch." }
if (-not $data.validation.required_pose_set_complete) {
    throw "Required ballet pose set incomplete."
}
if (-not $data.validation.arms_behind_back_is_blocked) {
    throw "Arms-behind-back regression is not blocked."
}
if (-not $data.validation.render_block_on_geometry_failure) {
    throw "Geometry failure must block render."
}
if (-not $data.validation.animation_block_on_geometry_failure) {
    throw "Geometry failure must block animation."
}

$poseCount = @($data.poses.PSObject.Properties).Count
if ($poseCount -ne 6) {
    throw "Expected 6 ballet pose contracts, got $poseCount."
}

Write-Host ""
Write-Host "PHASE 10.6.4 BALLET POSE GRAMMAR PASS"
Write-Host "Poses:  $poseCount"
Write-Host "Arms behind torso: BLOCKED"
Write-Host "Invalid geometry: BLOCKS RENDER + ANIMATION"
