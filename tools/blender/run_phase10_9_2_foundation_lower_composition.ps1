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
$sourceA=Join-Path $Repo "assets\ballet_motion\lower_body_foundation_motion_contract_v1.json"
$sourceB=Join-Path $Repo "assets\ballet_motion\lower_body_releve_motion_contract_v1.json"
$compositionContract=Join-Path $Repo "assets\ballet_motion\lower_body_motion_composition_contract_v1.json"
$script=Join-Path $Repo "tools\blender\build_foundation_lower_composition_v1.py"
$test=Join-Path $Repo "tools\ballet_motion\test_phase10_9_2_lower_body_motion_composition.py"
$report=Join-Path $Repo "build\phase10_9\foundation_lower_composition_v1_report.json"
$previewDir=Join-Path $Repo "build\phase10_9\foundation_lower_composition_preview_v1"

foreach ($required in @(
    $canonical,$constraints,$grammar,$retarget,$axis,$intents,
    $staticContract,$visualContract,$sourceA,$sourceB,
    $compositionContract,$script,$test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.9.2 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.9.2 - ACCEPTED LOWER-BODY PRIMITIVE COMPOSITION"
Write-Host "Chain: fifth -> plie -> releve"
Write-Host "Frames: 1..121; shared plie boundary: 61"
Write-Host "Contact: full-foot through 61, forefoot from 62"
Write-Host "Primitive math: accepted 10.8.1 + 10.8.2 modules"
Write-Host "GLB export: NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --source-contract-a $sourceA --source-contract-b $sourceB --composition-contract $compositionContract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.9.2 artifacts."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.9.2 report missing: $report"
}
$data=Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.9.2") {
    throw "Phase 10.9.2 report phase mismatch."
}

foreach ($gate in @(
    "source_10_8_1_reused",
    "source_10_8_2_reused",
    "shared_plie_matrix_identity",
    "single_boundary_key_authority",
    "no_inserted_hold_frames",
    "full_foot_then_forefoot_contact",
    "root_descent_monotone",
    "root_rise_monotone",
    "heel_lift_monotone_after_boundary",
    "root_horizontal_drift_blocked",
    "quaternion_flip_free",
    "sampled_every_frame",
    "single_humanoid_motion_authority",
    "accepted_trunk_hierarchy_motion_preserved",
    "primitive_math_reimplementation_absent"
)) {
    if (-not $data.automated_gate.$gate) {
        throw "Phase 10.9.2 automated gate failed: $gate"
    }
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.9.2."
}
if ($data.human_visual_gate.status -ne "PENDING_REVIEW") {
    throw "Machine must not decide the human visual gate."
}
if ($data.diagnostics.sample_count -ne 121) {
    throw "Expected 121 sampled frames."
}
$previewCount=@($data.preview.files).Count
if ($previewCount -ne 3) {
    throw "Expected 3 previews, got $previewCount."
}
foreach ($preview in $data.preview.files) {
    if (-not (Test-Path $preview)) {
        throw "Preview missing: $preview"
    }
}

Write-Host ""
Write-Host "PHASE 10.9.2 AUTOMATED PROOF PASS"
Write-Host "Frames:          $($data.diagnostics.sample_count)"
Write-Host "Previews:        $previewCount/3"
Write-Host "Boundary error:  $($data.diagnostics.boundary_output_local_matrix_error)"
Write-Host "Root descent:    $($data.diagnostics.root_descent)"
Write-Host "Root rise:       $($data.diagnostics.root_rise)"
Write-Host "Heel lift L/R:   $($data.diagnostics.heel_lift_end.left) / $($data.diagnostics.heel_lift_end.right)"
Write-Host "Human review:    PENDING"
Write-Host "GLB export:      NOT PERFORMED"
Write-Host "Report:          $report"
Write-Host "Preview dir:     $previewDir"
