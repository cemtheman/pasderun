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
$armA=Join-Path $Repo "assets\ballet_motion\foundation_motion_contract_v1.json"
$armB=Join-Path $Repo "assets\ballet_motion\foundation_motion_en_avant_to_second_v1.json"
$lowerA=Join-Path $Repo "assets\ballet_motion\lower_body_foundation_motion_contract_v1.json"
$lowerB=Join-Path $Repo "assets\ballet_motion\lower_body_releve_motion_contract_v1.json"
$contract=Join-Path $Repo "assets\ballet_motion\coordinated_foundation_motion_contract_v1.json"
$script=Join-Path $Repo "tools\blender\build_coordinated_foundation_motion_v1.py"
$test=Join-Path $Repo "tools\ballet_motion\test_phase10_10_1_coordinated_foundation_motion.py"
$report=Join-Path $Repo "build\phase10_10\coordinated_foundation_motion_v1_report.json"
$previewDir=Join-Path $Repo "build\phase10_10\coordinated_foundation_motion_preview_v1"

foreach ($required in @(
    $canonical,$constraints,$grammar,$retarget,$axis,$intents,
    $staticContract,$visualContract,$armA,$armB,$lowerA,$lowerB,
    $contract,$script,$test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.10.1 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.10.1 - COORDINATED FOUNDATION MOTION"
Write-Host "Arm:   bras_bas -> en_avant -> second"
Write-Host "Lower: fifth -> plie -> releve"
Write-Host "Frames: 1..121; shared coordinated boundary: 61"
Write-Host "Authority: lower semantic drivers + explicit arm-chain overlay"
Write-Host "Contact authority: lower-body solver"
Write-Host "Reverence/run/music/gameplay: NO"
Write-Host "GLB export: NO"
Write-Host ""

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --arm-contract-a $armA --arm-contract-b $armB --lower-contract-a $lowerA --lower-contract-b $lowerB --coordinated-contract $contract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.10.1 artifacts."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.10.1 report missing: $report"
}

$data=Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.10.1") {
    throw "Phase 10.10.1 report phase mismatch."
}

foreach ($gate in @(
    "arm_source_primitives_reused",
    "lower_source_primitives_reused",
    "authority_overlap_explicit",
    "arm_lower_semantic_overlap_absent",
    "overlap_limited_to_lower_hierarchy_followers",
    "arm_explicit_override_policy_applied",
    "root_contact_owned_by_lower_solver",
    "post_overlay_contact_pass",
    "arm_boundary_pass",
    "lower_boundary_pass",
    "root_descent_monotone",
    "root_rise_monotone",
    "heel_lift_monotone_after_boundary",
    "quaternion_flip_free",
    "sampled_every_frame",
    "single_humanoid_motion_authority",
    "primitive_math_reimplementation_absent"
)) {
    if (-not $data.automated_gate.$gate) {
        throw "Phase 10.10.1 automated gate failed: $gate"
    }
}

if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.10.1."
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
Write-Host "PHASE 10.10.1 AUTOMATED PROOF PASS"
Write-Host "Frames:             $($data.diagnostics.sample_count)"
Write-Host "Previews:           $previewCount/3"
Write-Host "Authority overlap:  $(@($data.authority_partition.arm_lower_overlap_rig_bones).Count)"
Write-Host "Semantic overlap:   $(@($data.authority_partition.arm_lower_semantic_overlap_rig_bones).Count)"
Write-Host "Contact max:        $($data.diagnostics.maximum_post_overlay_contact_error)"
Write-Host "Root descent:       $($data.diagnostics.root_descent)"
Write-Host "Root rise:          $($data.diagnostics.root_rise)"
Write-Host "Heel lift L/R:      $($data.diagnostics.heel_lift_end.left) / $($data.diagnostics.heel_lift_end.right)"
Write-Host "Human review:       PENDING"
Write-Host "GLB export:         NOT PERFORMED"
Write-Host "Report:             $report"
Write-Host "Preview dir:        $previewDir"
