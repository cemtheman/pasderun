param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$canonical = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_ballet_profile_v1.json"
$constraints = Join-Path $Repo "build\phase10_6\low_poly_girl_anatomical_constraint_profile_v1.json"
$grammar = Join-Path $Repo "build\phase10_6\low_poly_girl_ballet_pose_grammar_profile_v1.json"
$grammarSource = Join-Path $Repo "assets\ballet_motion\ballet_pose_grammar_v1.json"
$grammarValidatorSource = Join-Path $Repo "tools\ballet_motion\ballet_pose_validators.py"
$intents = Join-Path $Repo "assets\ballet_motion\foundation_pose_intents_v1.json"
$output = Join-Path $Repo "build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json"
$script = Join-Path $Repo "tools\ballet_motion\build_canonical_pose_solver_v1.py"

$runner = Join-Path $Repo "tools\ballet_motion\run_phase10_6_4_ballet_pose_grammar.ps1"
if (-not (Test-Path $runner)) {
    throw "Phase 10.6.4 runner missing: $runner"
}

$grammarNeedsRefresh = -not (Test-Path $grammar)
if (-not $grammarNeedsRefresh) {
    $existingGrammar = Get-Content $grammar -Raw | ConvertFrom-Json
    $currentGrammarSha = (Get-FileHash -Algorithm SHA256 $grammarSource).Hash.ToLowerInvariant()
    $profileGrammarSha = [string]$existingGrammar.inputs.grammar_sha256
    $currentValidatorSha = (Get-FileHash -Algorithm SHA256 $grammarValidatorSource).Hash.ToLowerInvariant()
    $profileValidatorSha = [string]$existingGrammar.inputs.validator_source_sha256

    if ($profileGrammarSha.ToLowerInvariant() -ne $currentGrammarSha) {
        Write-Host "Phase 10.6.4 grammar profile is stale; grammar source changed."
        $grammarNeedsRefresh = $true
    } elseif (
        [string]::IsNullOrWhiteSpace($profileValidatorSha) -or
        $profileValidatorSha.ToLowerInvariant() -ne $currentValidatorSha
    ) {
        Write-Host "Phase 10.6.4 grammar profile is stale; validator source changed."
        $grammarNeedsRefresh = $true
    }
}

if ($grammarNeedsRefresh) {
    Write-Host "Refreshing Phase 10.6.4 grammar prerequisite..."
    & powershell -ExecutionPolicy Bypass -File $runner -Repo $Repo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $grammar)) {
        throw "Phase 10.6.4 did not produce expected profile: $grammar"
    }
}

foreach ($required in @($canonical, $constraints)) {
    if (-not (Test-Path $required)) {
        throw "Canonical solver prerequisite missing: $required"
    }
}

Write-Host "PHASE 10.6.5 - CANONICAL POSE SOLVER V1"
Write-Host "No Blender runtime. No rig retarget. No render. No animation."
Write-Host ""

python $script --canonical-profile $canonical --constraint-profile $constraints --grammar-profile $grammar --intents $intents --output $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $output)) {
    throw "Expected Phase 10.6.5 output missing: $output"
}

$data = Get-Content $output -Raw | ConvertFrom-Json
if ($data.phase -ne "10.6.5") { throw "Canonical pose solver phase mismatch." }
if (-not $data.foundation_gate.all_pose_geometry_pass) {
    throw "Foundation pose geometry gate failed."
}
if (-not $data.foundation_gate.all_pose_joint_dofs_preferred) {
    throw "Foundation pose preferred joint envelope failed."
}
if (-not $data.foundation_gate.all_invalid_probes_rejected) {
    throw "Invalid pose probe escaped the solver gate."
}
if ($data.foundation_gate.rig_retarget_performed) {
    throw "Rig retarget is forbidden in Phase 10.6.5."
}
if ($data.foundation_gate.render_performed) {
    throw "Render is forbidden in Phase 10.6.5."
}
if ($data.foundation_gate.animation_performed) {
    throw "Animation is forbidden in Phase 10.6.5."
}

$poseCount = @($data.solutions.PSObject.Properties).Count
$probeCount = @($data.rejection_probes.PSObject.Properties).Count
if ($poseCount -ne 6) {
    throw "Expected 6 foundation poses, got $poseCount."
}
if ($probeCount -ne 4) {
    throw "Expected 4 rejection probes, got $probeCount."
}

Write-Host ""
Write-Host "PHASE 10.6.5 CANONICAL POSE SOLVER PASS"
Write-Host "Foundation poses: $poseCount/6"
Write-Host "Invalid probes:   $probeCount/4 REJECTED"
Write-Host "Rig retarget:     NOT PERFORMED"
Write-Host "Render:           NOT PERFORMED"
