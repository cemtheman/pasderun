param(
    [string]$Blender = "",
    [string]$Repo = "",
    [switch]$UseExistingArtifacts
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
    throw "Blender 5.2 executable not found. Pass -Blender explicitly."
}

$canonical = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$grammar = Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_pose_grammar_profile_v1.json"
$retarget = Join-Path $Repo "build\phase10_6\low_poly_girl_calibrated_rig_retarget_v1.json"
$axis = Join-Path $Repo "assets\ballet_motion\retarget_axis_contract_v1.json"
$intents = Join-Path $Repo "assets\ballet_motion\foundation_pose_intents_v1.json"
$staticContract = Join-Path $Repo "assets\ballet_motion\static_rig_application_contract_v1.json"
$visualContract = Join-Path $Repo "assets\ballet_motion\foundation_pose_visual_gate_v1.json"
$motionContract = Join-Path $Repo "assets\ballet_motion\foundation_motion_contract_v1.json"
$script = Join-Path $Repo "tools\blender\build_foundation_transition_v1.py"
$test = Join-Path $Repo "tools\ballet_motion\test_phase10_7_1_foundation_motion.py"
$report = Join-Path $Repo "build\phase10_7\foundation_motion_bras_bas_to_en_avant_v1_report.json"
$previewDir = Join-Path $Repo "build\phase10_7\foundation_motion_preview_v1"

foreach ($required in @(
    $canonical,
    $constraints,
    $grammar,
    $retarget,
    $axis,
    $intents,
    $staticContract,
    $visualContract,
    $motionContract,
    $script,
    $test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.7.1 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.7.1 - BRAS BAS -> EN AVANT FOUNDATION MOTION"
Write-Host "Endpoint authority: accepted Phase 10.6 realized poses"
Write-Host "Interpolation: rounded shoulder/elbow waypoint; finger shortest-arc; wrist canonical 2DOF; minimum jerk"
Write-Host "Generated build directories are preserved."
Write-Host "GLB export: NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --motion-contract $motionContract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.7.1 report and previews; Blender/test execution skipped."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.7.1 report was not generated: $report"
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.7.1") {
    throw "Phase 10.7.1 report phase mismatch."
}
if (-not $data.automated_gate.accepted_static_endpoints_reused) {
    throw "Accepted endpoint reuse gate failed."
}
if (-not $data.automated_gate.start_endpoint_exact) {
    throw "Start endpoint gate failed."
}
if (-not $data.automated_gate.end_endpoint_exact) {
    throw "End endpoint gate failed."
}
if (-not $data.automated_gate.rounded_transition_waypoint_path) {
    throw "Rounded transition waypoint gate failed."
}
if (-not $data.automated_gate.finger_quaternion_shortest_arc) {
    throw "Finger quaternion interpolation gate failed."
}
if (-not $data.automated_gate.wrist_canonical_2dof_reconstruction) {
    throw "Wrist canonical 2DOF interpolation gate failed."
}
if (-not $data.automated_gate.minimum_jerk_timing) {
    throw "Minimum-jerk timing gate failed."
}
if (-not $data.automated_gate.proximal_to_distal_windows) {
    throw "Proximal-to-distal timing gate failed."
}
if (-not $data.automated_gate.no_overshoot_timing) {
    throw "No-overshoot timing gate failed."
}
if (-not $data.automated_gate.lower_body_root_stable) {
    throw "Lower-body/root stability gate failed."
}
if (-not $data.automated_gate.hand_centerline_non_crossing) {
    throw "Hand centerline gate failed."
}
if (-not $data.automated_gate.elbow_non_inversion) {
    throw "Elbow inversion gate failed."
}
if (-not $data.automated_gate.wrist_2dof_no_axial_roll) {
    throw "Wrist axial-roll gate failed."
}
if (-not $data.automated_gate.semantic_preferred_envelope_proxy) {
    throw "Semantic preferred-envelope proxy gate failed."
}
if (-not $data.automated_gate.quaternion_flip_free) {
    throw "Quaternion continuity gate failed."
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.7.1."
}
if ($data.human_visual_gate.status -ne "PENDING_REVIEW") {
    throw "Machine must not decide the human visual gate."
}

$previewCount = @($data.preview.files).Count
if ($previewCount -ne 3) {
    throw "Expected FRONT/THREE_QUARTER/SIDE previews, got $previewCount."
}
foreach ($preview in $data.preview.files) {
    if (-not (Test-Path $preview)) {
        throw "Preview missing: $preview"
    }
}

Write-Host ""
Write-Host "PHASE 10.7.1 AUTOMATED PROOF PASS"
Write-Host "Frames:       $($data.diagnostics.sample_count)"
Write-Host "Previews:     $previewCount/3"
Write-Host "Human review: PENDING"
Write-Host "GLB export:   NOT PERFORMED"
Write-Host "Report:       $report"
Write-Host "Preview dir:  $previewDir"
