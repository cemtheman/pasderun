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
$sourceCrossed=Join-Path $Repo "assets\ballet_motion\opening_reverence_crossed_stance_contract_v1.json"
$contract=Join-Path $Repo "assets\ballet_motion\opening_reverence_expression_refinement_contract_v1.json"
$script=Join-Path $Repo "tools\blender\build_opening_reverence_expression_refinement_v1.py"
$test=Join-Path $Repo "tools\ballet_motion\test_phase10_11_3_reverence_expression_refinement.py"
$report=Join-Path $Repo "build\phase10_11\opening_reverence_expression_refinement_v1_report.json"
$previewDir=Join-Path $Repo "build\phase10_11\opening_reverence_expression_refinement_preview_v1"

foreach ($required in @(
    $canonical,$constraints,$grammar,$retarget,$axis,$intents,
    $staticContract,$visualContract,$sourceCrossed,$contract,
    $script,$test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.11.3 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.11.3 - REVERENCE EXPRESSION REFINEMENT"
Write-Host "Lower: frozen 10.11.2 selected crossed stance"
Write-Host "Upper: 9 bounded bras_bas-to-second endpoint-interpolation candidates"
Write-Host "Bow: canonical-X trunk/head refinement"
Write-Host "Centerline projection: FORBIDDEN"
Write-Host "Animation/turn/run/music: NO"
Write-Host "GLB export: NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --source-crossed-contract $sourceCrossed --refinement-contract $contract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.11.3 artifacts."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.11.3 report missing: $report"
}

$data=Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.11.3") {
    throw "Phase 10.11.3 report phase mismatch."
}

foreach ($gate in @(
    "frozen_10_11_2_parameters_exact",
    "frozen_lower_source_geometry_repassed",
    "accepted_arm_endpoint_bounded_interpolation_pass",
    "low_oval_stays_below_second_guard",
    "hand_gap_pass",
    "hand_symmetry_pass",
    "hand_centerline_pass",
    "elbows_below_shoulder_line_pass",
    "centerline_projection_absent",
    "frozen_lower_chain_exact_after_refinement",
    "frozen_lower_geometry_pass_after_refinement",
    "no_permanent_constraints",
    "imported_action_cleared",
    "report_json_serializable"
)) {
    if (-not $data.automated_gate.$gate) {
        throw "Phase 10.11.3 automated gate failed: $gate"
    }
}
if ($data.automated_gate.animation_authored) {
    throw "Animation is forbidden in Phase 10.11.3."
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.11.3."
}
if ($data.diagnostics.constraint_count -ne 0) {
    throw "Phase 10.11.3 left permanent constraints."
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
Write-Host "PHASE 10.11.3 AUTOMATED PROOF PASS"
Write-Host "Previews:        $previewCount/3"
Write-Host "Arm candidates:  $($data.upper_refinement.passing_count)/$($data.upper_refinement.candidate_count) pass"
Write-Host "Hand gap:        $($data.upper_refinement.selected_hand_geometry.gap_shoulder_width_fraction) shoulder-width"
Write-Host "Hand asymmetry:  $($data.upper_refinement.selected_hand_geometry.midpoint_asymmetry_shoulder_width_fraction) shoulder-width"
Write-Host "Selected arm:    $($data.upper_refinement.selected_parameters | ConvertTo-Json -Compress)"
Write-Host "Lower cross:     $($data.frozen_lower_authority.final_geometry.normalized.gesture_cross_foot_fraction) foot"
Write-Host "Lower back:      $($data.frozen_lower_authority.final_geometry.normalized.gesture_back_foot_fraction) foot"
Write-Host "Report JSON:     VALID"
Write-Host "Human review:    PENDING"
Write-Host "Animation:       NOT AUTHORED"
Write-Host "GLB export:      NOT PERFORMED"
Write-Host "Report:          $report"
Write-Host "Preview dir:     $previewDir"
