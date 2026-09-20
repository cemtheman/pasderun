param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$canonicalProfile = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$canonicalSpec = Join-Path $Repo "assets\ballet_motion\canonical_ballet_skeleton_v1.json"
$constraints = Join-Path $Repo "assets\ballet_motion\anatomical_constraints_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$script = Join-Path $Repo "tools\ballet_motion\build_anatomical_constraint_profile_v1.py"

if (-not (Test-Path $canonicalProfile)) {
    $canonicalRunner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_2_canonical_skeleton.ps1"
    if (-not (Test-Path $canonicalRunner)) {
        throw "Phase 10.6.2 runner missing: $canonicalRunner"
    }

    Write-Host "Phase 10.6.2 canonical profile missing; generating prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $canonicalRunner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $canonicalProfile)) {
        throw "Phase 10.6.2 did not produce expected profile: $canonicalProfile"
    }
}

Write-Host "PHASE 10.6.3 - ANATOMICAL JOINT LIMITS AND CONSTRAINT MODEL"
Write-Host "No Blender runtime. No render. No pose. No animation."
Write-Host "Canonical:  $canonicalProfile"
Write-Host "Constraints:$constraints"
Write-Host "Output:     $output"
Write-Host ""

python $script --canonical-profile $canonicalProfile --canonical-spec $canonicalSpec --constraints $constraints --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.3 output missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.3") { throw "Constraint profile phase mismatch." }
if (-not $data.validation.limit_table_valid) {
    throw "Anatomical limit table validation failed."
}
if (-not $data.validation.all_canonical_rotational_dofs_covered) {
    throw "Canonical DOF coverage failed."
}
if (-not $data.validation.hip_is_primary_turnout_authority) {
    throw "Hip turnout authority contract failed."
}
if (-not $data.validation.knee_axial_rotation_is_derived_only) {
    throw "Knee axial coupling contract failed."
}
if (-not $data.validation.independent_foot_yaw_forbidden) {
    throw "Independent foot yaw contract failed."
}

$boneCount = @($data.bone_constraints.PSObject.Properties).Count
if ($boneCount -ne 24) {
    throw "Expected 24 constrained canonical bones, got $boneCount."
}

Write-Host ""
Write-Host "PHASE 10.6.3 ANATOMICAL CONSTRAINT MODEL PASS"
Write-Host "Profile: $output"
Write-Host "Bones:   $boneCount"
Write-Host "Turnout: HIP primary / KNEE derived / FOOT yaw forbidden"
