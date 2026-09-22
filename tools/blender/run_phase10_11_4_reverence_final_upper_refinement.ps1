param(
    [string]$Blender = "",
    [string]$Repo = "",
    [switch]$UseExistingArtifacts,
    [switch]$DiagnosticOnly,
    [switch]$VisualCandidates
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
$contract=Join-Path $Repo "assets\ballet_motion\opening_reverence_final_upper_refinement_contract_v1.json"
$script=Join-Path $Repo "tools\blender\build_opening_reverence_final_upper_refinement_v1.py"
$test=Join-Path $Repo "tools\ballet_motion\test_phase10_11_4_reverence_final_upper_refinement.py"
$report=Join-Path $Repo "build\phase10_11\opening_reverence_final_upper_refinement_v1_report.json"
$diagnosticReport=Join-Path $Repo "build\phase10_11\opening_reverence_final_upper_refinement_arm_diagnostic_v1.json"
$visualCandidateReport=Join-Path $Repo "build\phase10_11\opening_reverence_final_upper_refinement_visual_candidates_v1.json"
$previewDir=Join-Path $Repo "build\phase10_11\opening_reverence_final_upper_refinement_preview_v1"

foreach ($required in @(
    $canonical,$constraints,$grammar,$retarget,$axis,$intents,
    $staticContract,$visualContract,$sourceCrossed,$contract,
    $script,$test
)) {
    if (-not (Test-Path $required)) {
        throw "Phase 10.11.4 prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.11.4 - REVERENCE FINAL UPPER REFINEMENT"
Write-Host "Lower: frozen 10.11.2 selected crossed stance"
Write-Host "Upper: 9 bounded bras_bas-to-en_avant endpoint-interpolation candidates"
Write-Host "Bow: canonical-X trunk/head refinement"
Write-Host "Centerline projection: FORBIDDEN"
Write-Host "Animation/turn/run/music: NO"
Write-Host "GLB export: NO"
if ($DiagnosticOnly) {
    Write-Host "Mode: ARM AUTHORITY DIAGNOSTIC ONLY - no authority selection, no previews"
}
if ($VisualCandidates) {
    Write-Host "Mode: VISUAL CANDIDATES ONLY - 3 fixed candidates x 3 views, no authority selection"
}
Write-Host ""

if ($DiagnosticOnly -and $UseExistingArtifacts) {
    throw "-DiagnosticOnly cannot be combined with -UseExistingArtifacts."
}
if ($VisualCandidates -and $UseExistingArtifacts) {
    throw "-VisualCandidates cannot be combined with -UseExistingArtifacts."
}
if ($DiagnosticOnly -and $VisualCandidates) {
    throw "-DiagnosticOnly and -VisualCandidates are mutually exclusive."
}

if (-not $UseExistingArtifacts) {
    & python -c "import ast,pathlib; ast.parse(pathlib.Path(r'$script').read_text(encoding='utf-8'))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python $test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($DiagnosticOnly) {
        if (Test-Path $diagnosticReport) {
            Remove-Item $diagnosticReport -Force
        }
        & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --source-crossed-contract $sourceCrossed --refinement-contract $contract --report $report --preview-dir $previewDir --diagnostic-only --diagnostic-report $diagnosticReport
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if (-not (Test-Path $diagnosticReport)) {
            throw "Phase 10.11.4 arm diagnostic report missing: $diagnosticReport"
        }
        $diag=Get-Content $diagnosticReport -Raw | ConvertFrom-Json
        if ($diag.mode -ne "ARM_AUTHORITY_DIAGNOSTIC_ONLY") {
            throw "Phase 10.11.4 diagnostic mode mismatch."
        }
        if ($diag.arm_diagnostic.authority_selected) {
            throw "Diagnostic pass must not select a new arm authority."
        }
        if ($diag.arm_diagnostic.optimizer_used) {
            throw "Diagnostic pass must not run an optimizer."
        }
        if ($diag.arm_diagnostic.centerline_projection_used) {
            throw "Diagnostic pass must not use centerline projection."
        }
        if ($diag.policy.animation_authored -or $diag.policy.glb_exported) {
            throw "Diagnostic pass must not author animation or export GLB."
        }

        Write-Host ""
        Write-Host "PHASE 10.11.4 ARM AUTHORITY DIAGNOSTIC PASS"
        Write-Host "Probes:           $($diag.arm_diagnostic.probe_count)"
        Write-Host "Authority:        NOT SELECTED"
        Write-Host "Optimizer:        NOT USED"
        Write-Host "Projection:       NOT USED"
        Write-Host "Animation:        NOT AUTHORED"
        Write-Host "GLB export:       NOT PERFORMED"
        Write-Host "Diagnostic report: $diagnosticReport"
        exit 0
    }

    if ($VisualCandidates) {
        if (Test-Path $visualCandidateReport) {
            Remove-Item $visualCandidateReport -Force
        }
        if (Test-Path $previewDir) {
            Remove-Item $previewDir -Recurse -Force
        }
        & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --source-crossed-contract $sourceCrossed --refinement-contract $contract --report $report --preview-dir $previewDir --visual-candidates-only --visual-candidate-report $visualCandidateReport
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if (-not (Test-Path $visualCandidateReport)) {
            throw "Phase 10.11.4 visual candidate report missing: $visualCandidateReport"
        }
        $visual=Get-Content $visualCandidateReport -Raw | ConvertFrom-Json
        if ($visual.mode -ne "REVERENCE_VISUAL_CANDIDATES_ONLY") {
            throw "Phase 10.11.4 visual candidate mode mismatch."
        }
        if ($visual.visual_candidates.authority_selected) {
            throw "Visual candidate pass must not select an arm authority."
        }
        if ($visual.visual_candidates.automated_aesthetic_verdict) {
            throw "Visual candidate pass must not make an aesthetic verdict."
        }
        if ($visual.policy.optimizer_used -or $visual.policy.adaptive_search_used) {
            throw "Visual candidate pass must not run optimization/search."
        }
        if ($visual.policy.centerline_projection_used) {
            throw "Visual candidate pass must not use centerline projection."
        }
        if ($visual.policy.animation_authored -or $visual.policy.glb_exported) {
            throw "Visual candidate pass must not author animation or export GLB."
        }
        $candidateCount=@($visual.visual_candidates.candidates).Count
        $previewCount=@($visual.visual_candidates.all_preview_files).Count
        if ($candidateCount -ne 3) {
            throw "Expected 3 visual candidates, got $candidateCount."
        }
        if ($previewCount -ne 9) {
            throw "Expected 9 candidate previews, got $previewCount."
        }
        foreach ($preview in $visual.visual_candidates.all_preview_files) {
            if (-not (Test-Path $preview)) {
                throw "Visual candidate preview missing: $preview"
            }
        }

        Write-Host ""
        Write-Host "PHASE 10.11.4 REVERENCE VISUAL CANDIDATES PASS"
        Write-Host "Candidates:       $candidateCount/3"
        Write-Host "Previews:         $previewCount/9"
        Write-Host "Gap target:       0.36 shoulder-width"
        Write-Host "Authority:        NOT SELECTED"
        Write-Host "Aesthetic verdict: HUMAN REVIEW PENDING"
        Write-Host "Optimizer:        NOT USED"
        Write-Host "Projection:       NOT USED"
        Write-Host "Animation:        NOT AUTHORED"
        Write-Host "GLB export:       NOT PERFORMED"
        Write-Host "Visual report:    $visualCandidateReport"
        Write-Host "Preview dir:      $previewDir"
        exit 0
    }

    & $Blender --background --python-exit-code 1 --python $script -- --repo $Repo --canonical-profile $canonical --constraint-profile $constraints --retarget-profile $retarget --retarget-axis-contract $axis --grammar-profile $grammar --intent-spec $intents --static-contract $staticContract --visual-contract $visualContract --source-crossed-contract $sourceCrossed --refinement-contract $contract --report $report --preview-dir $previewDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Reusing existing Phase 10.11.4 artifacts."
}

if (-not (Test-Path $report)) {
    throw "Phase 10.11.4 report missing: $report"
}

$data=Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.11.4") {
    throw "Phase 10.11.4 report phase mismatch."
}

foreach ($gate in @(
    "frozen_10_11_2_parameters_exact",
    "frozen_lower_source_geometry_repassed",
    "accepted_arm_endpoint_bounded_interpolation_pass",
    "low_oval_stays_within_en_avant_guard",
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
        throw "Phase 10.11.4 automated gate failed: $gate"
    }
}
if ($data.automated_gate.animation_authored) {
    throw "Animation is forbidden in Phase 10.11.4."
}
if ($data.automated_gate.glb_exported) {
    throw "GLB export is forbidden in Phase 10.11.4."
}
if ($data.diagnostics.constraint_count -ne 0) {
    throw "Phase 10.11.4 left permanent constraints."
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
Write-Host "PHASE 10.11.4 AUTOMATED PROOF PASS"
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
