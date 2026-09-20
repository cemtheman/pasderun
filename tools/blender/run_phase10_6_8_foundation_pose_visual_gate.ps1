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
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$retarget = Join-Path $Repo "build\phase10_6\low_poly_girl_calibrated_rig_retarget_v1.json"
$retargetAxisContract = Join-Path $Repo "assets\ballet_motion\retarget_axis_contract_v1.json"
$poseProfile = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json"
$intents = Join-Path $Repo "assets\ballet_motion\foundation_pose_intents_v1.json"
$staticContract = Join-Path $Repo "assets\ballet_motion\static_rig_application_contract_v1.json"
$visualContract = Join-Path $Repo "assets\ballet_motion\foundation_pose_visual_gate_v1.json"
$output = Join-Path $Repo "build\phase10_8\foundation_pose_visual_gate_v1_contact.png"
$report = Join-Path $Repo "build\phase10_8\foundation_pose_visual_gate_v1_report.json"
$script = Join-Path $Repo "tools\blender\render_foundation_pose_visual_gate_v1.py"

$retargetRunner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_6_calibrated_rig_retarget.ps1"
if (-not (Test-Path $retargetRunner)) {
    throw "Phase 10.6.6 runner missing: $retargetRunner"
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
        $retargetNeedsRefresh = $true
    }
}

if ($retargetNeedsRefresh) {
    Write-Host "Refreshing Phase 10.6.6 retarget prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $retargetRunner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

foreach ($required in @(
    $canonical,
    $constraints,
    $retarget,
    $retargetAxisContract,
    $staticContract,
    $visualContract
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.6.8 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.6.8 - FOUNDATION POSE VISUAL GATE V1"
Write-Host "6 poses x 3 views = 18 static renders"
Write-Host "Animation: NO"
Write-Host "GLB export: NO"
Write-Host "Automated aesthetic verdict: NO"
Write-Host ""

$cellDir = Join-Path (Split-Path $output -Parent) "foundation_pose_cells"
foreach ($stale in @($output, $report)) {
    if (Test-Path $stale) {
        Remove-Item -Force $stale
    }
}
if (Test-Path $cellDir) {
    Remove-Item -Recurse -Force $cellDir
}

& $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $retargetAxisContract --static-contract $staticContract --visual-contract $visualContract --output $output --report $report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($path in @($output, $report)) {
    if (-not (Test-Path $path)) {
        throw "Expected Phase 10.6.8 output missing: $path"
    }
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.8") { throw "Visual gate phase mismatch." }
if ($data.render_count -ne 18) { throw "Expected exactly 18 renders." }
if (-not $data.automated_gate.static_realization_pass) {
    throw "Static realization gate failed."
}
if (-not $data.automated_gate.mesh_contact_pass) {
    throw "Mesh contact gate failed."
}
if (-not $data.automated_gate.upper_body_hand_axial_continuity_pass) {
    throw "Hand axial continuity gate failed."
}
if (-not $data.automated_gate.fingertip_centerline_spacing_pass) {
    throw "Fingertip centerline spacing gate failed."
}
if ($data.automated_gate.animation_rendered) {
    throw "Animation is forbidden in Phase 10.6.8."
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.6.8."
}
if (-not $data.human_visual_gate.required) {
    throw "Human visual acceptance must remain required."
}
if ($data.human_visual_gate.status -ne "PENDING_REVIEW") {
    throw "Machine may not decide the visual verdict."
}

Write-Host ""
Write-Host "PHASE 10.6.8 FOUNDATION POSE VISUAL GATE READY"
Write-Host "Renders:          18/18"
Write-Host "Hand continuity:  PASS"
Write-Host "Fingertip spacing: PASS"
Write-Host "Static contact:   PASS"
Write-Host "Human review:     PENDING"
Write-Host "Contact sheet:    $output"
Write-Host "Report:           $report"
