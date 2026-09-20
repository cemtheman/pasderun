param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$canonical = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$poses = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json"
$contract = Join-Path $Repo "assets\ballet_motion\retarget_axis_contract_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_calibrated_rig_retarget_v1.json"
$script = Join-Path $Repo "tools\ballet_motion\build_calibrated_rig_retarget_v1.py"

if (-not (Test-Path $poses)) {
    $runner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_5_canonical_pose_solver.ps1"
    if (-not (Test-Path $runner)) {
        throw "Phase 10.6.5 runner missing: $runner"
    }

    Write-Host "Phase 10.6.5 pose profile missing; generating prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $runner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $poses)) {
        throw "Phase 10.6.5 did not produce expected profile: $poses"
    }
}

foreach ($required in @($canonical, $constraints)) {
    if (-not (Test-Path $required)) {
        throw "Retarget prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.6.6 - CALIBRATED RIG ORIENTATION RETARGET V1"
Write-Host "No Blender runtime. No pose application. No render. No animation."
Write-Host "Rotation retarget only; contact/root translation realization is deferred."
Write-Host ""

python $script --canonical-profile $canonical --constraint-profile $constraints --pose-profile $poses --axis-contract $contract --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.6 output missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.6") { throw "Retarget phase mismatch." }
if (-not $data.gate.rest_identity_pass) { throw "Rest identity gate failed." }
if (-not $data.gate.canonical_roundtrip_pass) { throw "Canonical roundtrip gate failed." }
if (-not $data.gate.hierarchy_reconstruction_pass) { throw "Hierarchy reconstruction gate failed." }
if (-not $data.gate.arm_length_axis_alignment_pass) { throw "Arm length-axis gate failed." }
if (-not $data.gate.hand_wrist_preferred_envelope_pass) { throw "Hand wrist preferred-envelope gate failed." }
if (-not $data.gate.orientation_retarget_pass) { throw "Orientation retarget gate failed." }
if ($data.gate.root_translation_applied) { throw "Root translation is out of scope." }
if ($data.gate.contact_translation_applied) { throw "Contact translation is out of scope." }
if ($data.gate.blender_application_performed) { throw "Blender application is out of scope." }
if ($data.gate.render_performed) { throw "Render is out of scope." }
if ($data.gate.animation_performed) { throw "Animation is out of scope." }

$poseCount = @($data.poses.PSObject.Properties).Count
if ($poseCount -ne 6) {
    throw "Expected 6 retargeted poses, got $poseCount."
}
if ($data.gate.bones_per_pose -ne 24) {
    throw "Expected 24 bones per retargeted pose."
}

Write-Host ""
Write-Host "PHASE 10.6.6 CALIBRATED RIG RETARGET PASS"
Write-Host "Poses:                  $poseCount/6"
Write-Host "Bones per pose:         24"
Write-Host "Rest identity:          PASS"
Write-Host "Canonical roundtrip:    PASS"
Write-Host "Hierarchy reconstruction: PASS"
Write-Host "Arm length-axis:        PASS"
Write-Host "Hand wrist envelope:    PASS"
Write-Host "Root/contact translation: NOT APPLIED"
Write-Host "Blender/render:         NOT PERFORMED"
