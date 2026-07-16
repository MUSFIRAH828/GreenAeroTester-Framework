<#
    run_one_scenario.ps1 - GreenAeroTest Aviation Energy Pilot  (v1.1)

    Launches FlightGear (with JSBSim) for a single scenario and waits for it
    to exit before returning, so that run_pilot.py only ever has one
    FlightGear window open at a time.

    v1.1 changes:
      - Disables the Garmin 196 GPS Nasal service, which was crashing fgfs
        with exit code 1 on some aircraft/scenario combinations.
      - Resolves a real scenery path instead of trusting whatever stale
        path is in FlightGear's saved preferences, and disables TerraSync
        so a missing/misconfigured scenery folder can no longer cause a
        startup hang -> 120s timeout.

    Usage:
        powershell.exe -ExecutionPolicy Bypass -File run_one_scenario.ps1 `
            -ScenarioFile scenarios/T01_takeoff.txt -OutputCsv outputs/T01_run1.csv `
            [-SceneryPath "D:\FlightGear\Scenery"]
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ScenarioFile,

    [string]$OutputCsv,

    # Optional explicit override. If not supplied, the script auto-detects
    # a valid scenery folder from a list of common locations.
    [string]$SceneryPath
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# IMPORTANT: update this to the real fgfs.exe path on this machine.
# ---------------------------------------------------------------------------
$fgfsPath = "C:\Program Files\FlightGear 2024.1\bin\fgfs.exe"

if (-not (Test-Path -LiteralPath $fgfsPath)) {
    Write-Error "fgfs.exe not found at '$fgfsPath'. Update `$fgfsPath in run_one_scenario.ps1 to match this machine."
    exit 1
}

if (-not (Test-Path -LiteralPath $ScenarioFile)) {
    Write-Error "Scenario file not found: $ScenarioFile"
    exit 1
}

$scenarioName = [System.IO.Path]::GetFileNameWithoutExtension($ScenarioFile)

# ---------------------------------------------------------------------------
# FIX #2: Scenery path resolution.
#
# The observed error:
#   [WARN]:general scenery path not found: Path "C:/Users/Home 12/Music/geenareo/default"
# means FlightGear picked up a bad path from its saved preferences.xml
# (usually under %USERPROFILE%\AppData\Roaming\flightgear.org\...) rather
# than from the command line, so it silently loads with broken/absent
# terrain and either hangs or runs extremely slowly until Python's
# timeout_sec kills it.
#
# Fix: explicitly resolve a real scenery folder and pass --fg-scenery on
# the command line, which always overrides the saved preference. We also
# pass --disable-terrasync so FlightGear never tries to fetch scenery over
# the network mid-run (a second, very common cause of "stuck on startup").
# ---------------------------------------------------------------------------
$fgRootGuess = Split-Path -Parent (Split-Path -Parent $fgfsPath)   # .../FlightGear 2024.1

$candidateScenery = @(
    $SceneryPath,
    $env:FG_SCENERY,
    (Join-Path $fgRootGuess "data\Scenery"),
    "C:\Program Files\FlightGear 2024.1\data\Scenery",
    "C:\FlightGear\data\Scenery",
    "$env:USERPROFILE\FlightGear\Scenery"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $candidateScenery) {
    Write-Warning ("No valid scenery folder found in any known location. " +
        "FlightGear will run with --disable-terrasync but may show blank/missing terrain. " +
        "Set -SceneryPath explicitly or the FG_SCENERY environment variable to fix this.")
} else {
    Write-Host "[$scenarioName] Using scenery path: $candidateScenery"
}

$baseArgs = @(
    "--fdm=jsb",
    "--aircraft=c172p",
    "--airport=KSFO",
    "--timeofday=noon",
    "--disable-real-weather-fetch",
    "--disable-splash-screen",
    "--disable-sound",
    "--disable-terrasync",                                   # never fetch scenery over the network
    # FIX #1: stop the Garmin196 Nasal service crash (exit code 1).
    "--prop:/instrumentation/garmin196/serviceable=false"
)

if ($candidateScenery) {
    $baseArgs += "--fg-scenery=$candidateScenery"
}

# Map scenario name to FlightGear command-line options.
switch -Wildcard ($scenarioName) {
    "*takeoff*" {
        $scenarioArgs = @("--runway=28L", "--vc=0", "--altitude=13")
    }
    "*cruise*" {
        $scenarioArgs = @("--in-air", "--altitude=6000", "--vc=110", "--heading=280")
    }
    "*landing*" {
        $scenarioArgs = @("--in-air", "--altitude=1200", "--vc=70", "--heading=280", "--glideslope=-3")
    }
    "*wind*" {
        $scenarioArgs = @("--in-air", "--altitude=2500", "--vc=90", "--heading=280", "--wind=270@25")
    }
    "*failure*" {
        $scenarioArgs = @("--in-air", "--altitude=2000", "--vc=90", "--heading=280",
                           "--prop:/controls/engines/engine[0]/magnetos=0")
    }
    default {
        $scenarioArgs = @("--in-air", "--altitude=2000", "--vc=90", "--heading=280")
    }
}

$fgfsArgs = $baseArgs + $scenarioArgs

Write-Host "[$scenarioName] Launching FlightGear..."
Write-Host "[$scenarioName] Args: $($fgfsArgs -join ' ')"

# -Wait ensures only one FlightGear window is open at a time; Python's
# subprocess timeout handles the case where FlightGear itself hangs.
$process = Start-Process -FilePath $fgfsPath -ArgumentList $fgfsArgs -PassThru -Wait

if ($OutputCsv) {
    try {
        "scenario,exit_code,scenery_path,timestamp" | Out-File -FilePath $OutputCsv -Encoding utf8
        "$scenarioName,$($process.ExitCode),$candidateScenery,$(Get-Date -Format o)" |
            Out-File -FilePath $OutputCsv -Append -Encoding utf8
    } catch {
        Write-Warning "Could not write output CSV '$OutputCsv': $_"
    }
}

Write-Host "[$scenarioName] Exited with code $($process.ExitCode)"
exit $process.ExitCode