param(
    [string]$Blender = "",
    [string]$Repo = "",
    [switch]$UseExistingArtifacts
)

$ErrorActionPreference="Stop"

if (-not $Repo) {
    $Repo=(Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if (-not $Blender) {
    $candidate="$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
    if (Test-Path $candidate) { $Blender=$candidate }
}
if (-not $Blender -or -not (Test-Path $Blender)) {
    throw "Blender 5.2 executable not found. Pass -Blender explicitly."
}

$canonical=Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$constraints=Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$grammar=Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_pose_grammar_profile_v1.json"
$retarget=Join-Path $Repo "build\phase10_6\low_poly_girl_calibrated_rig_retarget_v1.json"
$axis=Join-Path $Repo "assets\ballet_motion\retarget_axis_contract_v1.json"
$intents=Join-Path $Repo "assets\ballet_motion\foundation_pose_intents_v1.json"
$staticContract=Join-Path $Repo "assets\ballet_motion\static_rig_application_contract_v1.json"
$visualContract=Join-Path $Repo "assets\ballet_motion\foundation_pose_visual_gate_v1.json"
$reverenceContract=Join-Path $Repo "assets\ballet_motion\opening_reverence_pose_contract_v1.json"
$lowerMotionContract=Join-Path $Repo "assets\ballet_motion\lower_body_foundation_motion_contract_v1.json"
$armMotionContract=Join-Path $Repo "assets\ballet_motion\foundation_motion_contract_v1.json"
$script=Join-Path $Repo "tools\blender\build_opening_reverence_acknowledgement_pose_v1.py"
$test=Join-Path $Repo "tools\ballet_motion\test_phase10_11_1_opening_reverence_pose.py"
$report=Join-Path $Repo "build\phase10_11\opening_reverence_acknowledgement_pose_v1_report.json"
$previewDir=Join-Path $Repo "build\phase10_11\opening_reverence_acknowledgement_pose_preview_v1"

foreach ($required in @(
    $canonical,$constraints,$grammar,$retarget,$axis,$intents,
    $staticContract,$visualContract,$reverenceContract,$lowerMotionContract,$armMotionContract,$script,$test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.11.1 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.11.1 - OPENING REVERENCE ACKNOWLEDGEMENT POSE"
Write-Host "Lower authority: accepted fifth->plie frame 31 demi-plie"
Write-Host "Arm authority:   accepted bras_bas"
Write-Host "New authoring:   canonical-X trunk/head inclination only"
Write-Host "Animation:       NO"
Write-Host "Turn/run/music:  NO"
Write-Host "GLB export:      NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --reverence-contract $reverenceContract --lower-motion-contract $lowerMotionContract --arm-motion-contract $armMotionContract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.11.1 artifacts."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.11.1 report missing: $report"
}

$data=Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.11.1") {
    throw "Phase 10.11.1 report phase mismatch."
}

foreach ($gate in @(
    "accepted_fifth_to_plie_motion_reused",
    "accepted_bras_bas_reused",
    "independent_arm_authoring_absent",
    "independent_leg_authoring_absent",
    "axial_plus_bounded_shoulder_clearance_only",
    "lower_chain_exact",
    "arm_nonshoulder_chain_exact",
    "shoulder_clearance_bounded",
    "full_foot_contact_pass",
    "hand_centerline_pass",
    "imported_action_cleared"
)) {
    if (-not $data.automated_gate.$gate) {
        throw "Phase 10.11.1 automated gate failed: $gate"
    }
}
if ($data.automated_gate.animation_authored) {
    throw "Animation is forbidden in Phase 10.11.1."
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.11.1."
}
if ($data.human_visual_gate.status -ne "PENDING_REVIEW") {
    throw "Machine must not decide the human visual gate."
}

$previewCount=@($data.preview.files).Count
if ($previewCount -ne 3) {
    throw "Expected 3 static previews, got $previewCount."
}
foreach ($preview in $data.preview.files) {
    if (-not (Test-Path $preview)) {
        throw "Preview missing: $preview"
    }
}

Write-Host ""
Write-Host "PHASE 10.11.1 AUTOMATED PROOF PASS"
Write-Host "Previews:       $previewCount/3"
Write-Host "Contact max:    $($data.diagnostics.full_foot_contact_max_abs_error)"
Write-Host "Hand L/R:       $($data.diagnostics.hand_side_offsets.left) / $($data.diagnostics.hand_side_offsets.right)"
Write-Host "Lower error:    $($data.diagnostics.lower_contact_chain_local_matrix_error)"
Write-Host "Arm nonshoulder:$($data.diagnostics.arm_nonshoulder_chain_local_matrix_error)"
Write-Host "Shoulder corr:  $($data.diagnostics.maximum_shoulder_clearance_correction_deg) deg"
Write-Host "Human review:   PENDING"
Write-Host "Animation:      NOT AUTHORED"
Write-Host "GLB export:     NOT PERFORMED"
Write-Host "Report:         $report"
Write-Host "Preview dir:    $previewDir"
