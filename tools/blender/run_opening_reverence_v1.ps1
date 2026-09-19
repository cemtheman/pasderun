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
$outputGlb = Join-Path $Repo "build\phase10_4\low_poly_girl_authored_v2.glb"
$report = Join-Path $Repo "build\phase10_4\opening_reverence_v2_report.json"
$blendOutput = Join-Path $Repo "build\phase10_4\opening_reverence_v2.blend"
$script = Join-Path $Repo "tools\blender\build_opening_reverence_v1.py"

Write-Host "Blender: $Blender"
Write-Host "Source:  $inputGlb"
Write-Host "Output:  $outputGlb"

& $Blender --background --python $script -- --input $inputGlb --output $outputGlb --report $report --blend-output $blendOutput
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $outputGlb)) { throw "Authored GLB was not created." }
if (-not (Test-Path $report)) { throw "Rig report was not created." }

$data = Get-Content $report -Raw | ConvertFrom-Json
if ($data.phase -ne "10.4.2") { throw "Expected Phase 10.4.2 report." }
if ($data.authored_action -ne "Opening_Reverence_v1") { throw "Expected authored action was not reported." }
if (-not $data.required_bones_ok) { throw "Audited rig contract did not validate." }

Write-Host ""
Write-Host "PHASE 10.4.2 PIPELINE PASS"
Write-Host "Action:    $($data.authored_action)"
Write-Host "Rig:       $($data.armature)"
Write-Host "Duration:  $($data.duration_seconds)s"
Write-Host "Aim error: $($data.max_aim_error)"
Write-Host "Report:    $report"
Write-Host "GLB:       $outputGlb"
