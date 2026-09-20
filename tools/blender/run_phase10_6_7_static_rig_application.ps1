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

$canonical = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$retarget = Join-Path $Repo "build\phase10_6\low_poly_girl_calibrated_rig_retarget_v1.json"
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$retargetAxisContract = Join-Path $Repo "assets\ballet_motion\retarget_axis_contract_v1.json"
$poseProfile = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json"
$intents = Join-Path $Repo "assets\ballet_motion\foundation_pose_intents_v1.json"
$contract = Join-Path $Repo "assets\ballet_motion\static_rig_application_contract_v1.json"
$output = Join-Path $Repo "build\phase10_7\static_rig_application_report_v1.json"
$script = Join-Path $Repo "tools\blender\apply_static_foundation_poses_v1.py"

$runner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_6_calibrated_rig_retarget.ps1"
if (-not (Test-Path $runner)) {
    throw "Phase 10.6.6 runner missing: $runner"
}

$retargetNeedsRefresh = -not (Test-Path $retarget)

if (-not (Test-Path $poseProfile)) {
    $retargetNeedsRefresh = $true
} else {
    $existingPose = Get-Content $poseProfile -Raw | ConvertFrom-Json
    $currentIntentSha = (Get-FileHash -Algorithm SHA256 $intents).Hash.ToLowerInvariant()
    $profileIntentSha = [string]$existingPose.inputs.intent_spec_sha256
    if ($profileIntentSha.ToLowerInvariant() -ne $currentIntentSha) {
        Write-Host "Phase 10.6.5 pose profile is stale; intent spec changed."
        $retargetNeedsRefresh = $true
    }
}

if (-not $retargetNeedsRefresh) {
    $existingRetarget = Get-Content $retarget -Raw | ConvertFrom-Json
    $currentAxisSha = (Get-FileHash -Algorithm SHA256 $retargetAxisContract).Hash.ToLowerInvariant()
    $profileAxisSha = [string]$existingRetarget.inputs.axis_contract_sha256
    $currentPoseSha = (Get-FileHash -Algorithm SHA256 $poseProfile).Hash.ToLowerInvariant()
    $profilePoseSha = [string]$existingRetarget.inputs.pose_profile_sha256
    if ($profilePoseSha.ToLowerInvariant() -ne $currentPoseSha) {
        Write-Host "Phase 10.6.6 retarget profile is stale; pose profile changed."
        $retargetNeedsRefresh = $true
    } elseif ($profileAxisSha.ToLowerInvariant() -ne $currentAxisSha) {
        Write-Host "Phase 10.6.6 retarget profile is stale; axis contract changed."
        $retargetNeedsRefresh = $true
    }
}

if ($retargetNeedsRefresh) {
    Write-Host "Generating Phase 10.6.6 retarget prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $runner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

foreach ($required in @($canonical, $retarget, $constraints, $retargetAxisContract, $contract)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.6.7 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.6.7 - STATIC RIG APPLICATION + CONTACT/ROOT PROOF"
Write-Host "Blender pose application: YES"
Write-Host "Render: NO"
Write-Host "Animation: NO"
Write-Host "GLB export: NO"
Write-Host ""

if (Test-Path $output) {
    Remove-Item -Force $output
}

& $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --retarget-profile $retarget --constraint-profile $constraints --retarget-axis-contract $retargetAxisContract --contract $contract --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.7 report missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.7") { throw "Static application phase mismatch." }
if (-not $data.gate.all_24_bone_rotations_applied) {
    throw "24-bone rotation application gate failed."
}
if (-not $data.gate.local_matrix_application_pass) {
    throw "Local matrix application gate failed."
}
if (-not $data.gate.absolute_matrix_application_pass) {
    throw "Absolute matrix application gate failed."
}
if (-not $data.gate.full_foot_orientation_realization_pass) {
    throw "Full-foot orientation realization gate failed."
}
if (-not $data.gate.full_foot_contact_pass) {
    throw "Full-foot contact gate failed."
}
if (-not $data.gate.forefoot_contact_pass) {
    throw "Forefoot contact gate failed."
}
if (-not $data.gate.plie_root_descent_consistency_pass) {
    throw "Plie root-descent gate failed."
}
if (-not $data.gate.releve_plantar_contact_realization_pass) {
    throw "Releve plantar/contact realization gate failed."
}
if (-not $data.gate.releve_plantar_toe_contact_realization_pass) {
    throw "Releve plantar+toe/contact realization gate failed."
}
if (-not $data.gate.releve_heel_lift_consistency_pass) {
    throw "Releve heel-lift gate failed."
}
if (-not $data.gate.fingertip_centerline_spacing_pass) {
    throw "Fingertip centerline spacing gate failed."
}
if (-not $data.gate.blender_application_performed) {
    throw "Blender pose application did not occur."
}
if ($data.gate.render_performed) { throw "Render is forbidden in Phase 10.6.7." }
if ($data.gate.animation_performed) { throw "Animation is forbidden in Phase 10.6.7." }
if ($data.gate.glb_exported) { throw "GLB export is forbidden in Phase 10.6.7." }

$poseCount = @($data.poses.PSObject.Properties).Count
if ($poseCount -ne 6) {
    throw "Expected 6 applied poses, got $poseCount."
}

Write-Host ""
Write-Host "PHASE 10.6.7 STATIC RIG APPLICATION PASS"
Write-Host "Poses:             $poseCount/6"
Write-Host "Rotation apply:    PASS"
Write-Host "Full-foot orient.:  PASS"
Write-Host "Full-foot contact: PASS"
Write-Host "Forefoot contact:  PASS"
Write-Host "Plie root descent: PASS"
Write-Host "Releve plantar:    PASS"
Write-Host "Releve plantar+toe: PASS"
Write-Host "Releve heel lift:  PASS"
Write-Host "Fingertip spacing: PASS"
Write-Host "Render/animation/export: NOT PERFORMED"
Write-Host "Report: $output"
