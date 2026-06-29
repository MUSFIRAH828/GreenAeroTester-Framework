# ==============================================================================
# scripts/run_one_scenario.ps1
# GreenAeroTest Prototype - FlightGear Scenario Runner
#
# PARAMETERS:
#   -ScenarioFile  Path to the .txt scenario descriptor (e.g. scenarios\T01_takeoff.txt)
#   -OutputCsv     Path where this run's log/output should be written (e.g. outputs\T01_run1.csv)
#
# USAGE:
#   powershell.exe -ExecutionPolicy Bypass -File scripts\run_one_scenario.ps1 `
#       -ScenarioFile "scenarios\T01_takeoff.txt" -OutputCsv "outputs\T01_run1.csv"
# ==============================================================================

param(
    [Parameter(Mandatory = $true)]
    [string]$ScenarioFile,

    [Parameter(Mandatory = $true)]
    [string]$OutputCsv
)

# ------------------------------------------------------------------------------
# CONFIGURATION
# Update $fgfsPath if your FlightGear is installed to a different location.
# To find it: Get-ChildItem "C:\Program Files" -Recurse -Filter fgfs.exe
# ------------------------------------------------------------------------------
$fgfsPath = "C:\Program Files\FlightGear 2024.1\bin\fgfs.exe"

# ------------------------------------------------------------------------------
# VALIDATE EXECUTABLE
# ------------------------------------------------------------------------------
if (-not (Test-Path $fgfsPath)) {
    Write-Error "FlightGear executable not found at: $fgfsPath"
    Write-Error "Edit the fgfsPath variable in run_one_scenario.ps1 to match your installation."
    exit 99
}

if (-not (Test-Path $ScenarioFile)) {
    Write-Warning "Scenario file not found: $ScenarioFile — launching with default args."
}

# ------------------------------------------------------------------------------
# DERIVE SCENARIO IDENTITY FROM FILENAME
# e.g. "scenarios\T03_landing.txt"  ->  scenarioName = "T03_landing"
#      testId = "T03"
# ------------------------------------------------------------------------------
$scenarioName = [System.IO.Path]::GetFileNameWithoutExtension($ScenarioFile)
$testId       = ($scenarioName -split "_")[0]          # first token before underscore

Write-Host "=================================================="
Write-Host " GreenAeroTest | run_one_scenario.ps1"
Write-Host "=================================================="
Write-Host " Scenario File : $ScenarioFile"
Write-Host " Scenario Name : $scenarioName"
Write-Host " Test ID       : $testId"
Write-Host " Output CSV    : $OutputCsv"
Write-Host " FlightGear    : $fgfsPath"
Write-Host "=================================================="

# ------------------------------------------------------------------------------
# BASE FLIGHTGEAR ARGUMENTS  (common to every run)
# ------------------------------------------------------------------------------
$baseArgs = @(
    "--fdm=jsb",                         # JSBSim flight-dynamics model
    "--aircraft=c172p",                  # Cessna 172P
    "--airport=KSFO",                    # San Francisco International
    "--timeofday=noon",                  # Fixed lighting — reproducible visuals
    "--disable-real-weather-fetch",      # No live weather — reproducible conditions
    "--fog-fastest",                     # Lowest fog quality — reduce GPU load
    "--prop:/sim/rendering/quality=0"    # Lowest render quality — faster CPU cycle
)

# ------------------------------------------------------------------------------
# PER-SCENARIO ARGUMENTS
# Each test ID maps to specific FlightGear init flags.
# ------------------------------------------------------------------------------
switch ($testId) {

    "T01" {
        Write-Host " Mode: T01 — Normal Takeoff (ground start, engines running)"
        $scenarioArgs = @(
            "--altitude=0",
            "--vc=0",
            "--heading=280",
            "--prop:/controls/engines/engine/throttle=0.0",
            "--prop:/controls/flight/elevator-trim=-0.1"
        )
    }

    "T02" {
        Write-Host " Mode: T02 — Normal Cruise (in-air, straight-and-level)"
        $scenarioArgs = @(
            "--in-air",
            "--altitude=2000",
            "--vc=90",
            "--heading=280"
        )
    }

    "T03" {
        Write-Host " Mode: T03 — Landing (final approach, MANDATORY)"
        $scenarioArgs = @(
            "--in-air",
            "--altitude=1500",
            "--vc=65",
            "--heading=280",
            "--prop:/controls/gear/gear-down=true"
        )
    }

    "T04" {
        Write-Host " Mode: T04 — Wind Disturbance (cruise + crosswind injected)"
        $scenarioArgs = @(
            "--in-air",
            "--altitude=2000",
            "--vc=90",
            "--heading=280",
            "--prop:/environment/wind-speed-kt=25",
            "--prop:/environment/wind-from-heading-deg=310"
        )
    }

    "T05" {
        Write-Host " Mode: T05 — Failure Case (engine off at start, MANDATORY)"
        $scenarioArgs = @(
            "--in-air",
            "--altitude=2000",
            "--vc=90",
            "--heading=280",
            "--prop:/engines/engine/running=false",
            "--prop:/engines/engine/cranking=false"
        )
    }

    default {
        Write-Warning " Unknown test ID '$testId'. Using generic in-air defaults."
        $scenarioArgs = @(
            "--in-air",
            "--altitude=2000",
            "--vc=90",
            "--heading=280"
        )
    }
}

# ------------------------------------------------------------------------------
# ENSURE OUTPUT DIRECTORY EXISTS
# ------------------------------------------------------------------------------
$outputDir = [System.IO.Path]::GetDirectoryName($OutputCsv)
if ($outputDir -and -not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    Write-Host " Created output directory: $outputDir"
}

# ------------------------------------------------------------------------------
# BUILD FINAL ARGUMENT LIST AND LAUNCH
# Start-Process -Wait blocks until FlightGear exits, guaranteeing sequential runs.
# -PassThru returns the process object so we can read its ExitCode.
# ------------------------------------------------------------------------------
$allArgs  = $baseArgs + $scenarioArgs
$argLine  = $allArgs -join " "

Write-Host ""
Write-Host " Launching FlightGear..."
Write-Host " Args: $argLine"
Write-Host ""

$startTimestamp = Get-Date

try {
    $process = Start-Process `
        -FilePath    $fgfsPath `
        -ArgumentList $allArgs `
        -PassThru `
        -Wait

    $endTimestamp = Get-Date
    $wallSeconds  = ($endTimestamp - $startTimestamp).TotalSeconds
    $exitCode     = $process.ExitCode

    Write-Host ""
    Write-Host " FlightGear finished."
    Write-Host " Exit Code  : $exitCode"
    Write-Host " Wall Time  : $([math]::Round($wallSeconds, 2)) s"

    # Write a minimal one-line log so Python can confirm the process ran.
    # In the full system this would be replaced by FlightGear telemetry output.
    $logLine = "test_id,scenario_name,exit_code,wall_sec`n" +
               "$testId,$scenarioName,$exitCode,$([math]::Round($wallSeconds,2))"
    Set-Content -Path $OutputCsv -Value $logLine -Encoding UTF8
    Write-Host " Log written: $OutputCsv"

    exit $exitCode

} catch {
    Write-Error "Failed to start FlightGear: $_"
    exit 1
}
