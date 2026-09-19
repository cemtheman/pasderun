param(
    [string]$Blender = "",
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

if (-not $Blender) {
    $cmd = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($cmd) { $Blender = $cmd.Source }
}

if (-not $Blender) {
    $candidates = @(
        "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 5.2 LTS\blender.exe",
        "$env:LOCALAPPDATA\Programs\Blender Foundation\Blender 5.2\blender.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $Blender = $candidate
            break
        }
    }
}

if (-not $Blender -and (Test-Path "$env:ProgramFiles\Blender Foundation")) {
    $found = Get-ChildItem "$env:ProgramFiles\Blender Foundation" -Filter blender.exe -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($found) { $Blender = $found.FullName }
}

if (-not $Blender -or -not (Test-Path $Blender)) {
    throw "Blender executable not found. Re-run with -Blender 'C:\path\to\blender.exe'."
}

$inputGlb = Join-Path $Repo "assets\characters\low_poly_girl\low_poly_girl .glb"
$outputGlb = Join-Path $Repo "build\phase10_4\low_poly_girl_native_ik_v4.glb"
$report = Join-Path $Repo "build\phase10_4\opening_reverence_native_ik_v4_report.json"
$blendOutput = Join-Path $Repo "build\phase10_4\opening_reverence_native_ik_v4.blend"
$preview = Join-Path $Repo "build\phase10_4\opening_reverence_native_ik_v4_preview.mp4"
$script = Join-Path $Repo "tools\blender\build_opening_reverence_v1.py"

Write-Host "Blender: $Blender"
Write-Host "Source:  $inputGlb"
Write-Host "Output:  $outputGlb"
Write-Host "Preview: $preview"

& $Blender --background --python $script -- --input $inputGlb --output $outputGlb --report $report --blend-output $blendOutput --preview $preview
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($path in @($outputGlb, $report, $blendOutput, $preview)) {
    if (-not (Test-Path $path)) {
        throw "Expected Phase 10.4.3 output missing: $path"
    }
}

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.4.3") { throw "Expected Phase 10.4.3 report." }
if ($data.authored_action -ne "Opening_Reverence_v1") {
    throw "Expected authored action was not reported."
}
if (-not $data.required_bones_ok) {
    throw "Audited rig contract did not validate."
}
if (-not $data.native_ik_baked) {
    throw "Native IK was not reported as baked."
}
if ($data.constraints_after_bake -ne 0) {
    throw "Constraints survived the bake."
}
if ($data.temporary_controls_after_bake.Count -ne 0) {
    throw "Temporary IK controls survived the bake."
}

Write-Host ""
Write-Host "PHASE 10.4.3 NATIVE IK PASS"
Write-Host "Action:      $($data.authored_action)"
Write-Host "Rig:         $($data.armature)"
Write-Host "Duration:    $($data.duration_seconds)s"
Write-Host "Native IK:   $($data.native_ik_baked)"
Write-Host "Constraints: $($data.constraints_after_bake)"
Write-Host "Report:      $report"
Write-Host "GLB:         $outputGlb"
Write-Host "Preview:     $preview"
