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
$motionContract = Join-Path $Repo "assets\ballet_motion\lower_body_foundation_motion_contract_v1.json"
$script = Join-Path $Repo "tools\blender\build_lower_body_fifth_to_plie_v1.py"
$test = Join-Path $Repo "tools\ballet_motion\test_phase10_8_1_lower_body_foundation_motion.py"
$report = Join-Path $Repo "build\phase10_8\lower_body_motion_fifth_to_plie_v1_report.json"
$previewDir = Join-Path $Repo "build\phase10_8\lower_body_motion_fifth_to_plie_preview_v1"

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
        throw "Phase 10.8.1 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.8.1 - FIFTH -> PLIE LOWER-BODY FOUNDATION MOTION"
Write-Host "Endpoint authority: accepted Phase 10.6 realized poses"
Write-Host "Motion: accepted fifth/plie endpoint differences + synchronous minimum jerk"
Write-Host "Contact: per-frame deformed-mesh rear+fore full-foot root solve"
Write-Host "Releve/toe pivot: NO"
Write-Host "GLB export: NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --motion-contract $motionContract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.8.1 report and previews; Blender/test execution skipped."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.8.1 report was not generated: $report"
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.8.1") {
    throw "Phase 10.8.1 report phase mismatch."
}

foreach ($gate in @(
    "accepted_static_endpoints_reused",
    "start_endpoint_exact",
    "end_endpoint_exact",
    "phase10_6_endpoint_motion_authority",
    "accepted_trunk_hierarchy_motion",
    "quaternion_shortest_arc",
    "minimum_jerk_timing",
    "full_foot_contact_every_frame",
    "pelvis_descent_monotone",
    "root_horizontal_drift_blocked",
    "nonparticipating_bones_stable",
    "semantic_preferred_envelope_proxy",
    "quaternion_flip_free",
    "releve_scope_absent"
)) {
    if (-not $data.automated_gate.$gate) {
        throw "Phase 10.8.1 automated gate failed: $gate"
    }
}

if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.8.1."
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
Write-Host "PHASE 10.8.1 AUTOMATED PROOF PASS"
Write-Host "Frames:       $($data.diagnostics.sample_count)"
Write-Host "Previews:     $previewCount/3"
Write-Host "Contact max:  $($data.diagnostics.maximum_full_foot_contact_error)"
Write-Host "Root descent: $($data.diagnostics.root_descent)"
Write-Host "Human review: PENDING"
Write-Host "GLB export:   NOT PERFORMED"
Write-Host "Report:       $report"
Write-Host "Preview dir:  $previewDir"
