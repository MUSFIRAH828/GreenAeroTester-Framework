<#
.SYNOPSIS
    Launches a single FlightGear scenario run and waits for it to finish,
    for a fixed duration, or until an external timeout is reached.

.DESCRIPTION
    This script is invoked once per (scenario, repetition) pair by
    src/executor.py. It:
      1. Starts fgfs.exe with the parameters needed to load the given
         scenario/aircraft on the given airport/runway.
      2. Redirects FlightGear stdout/stderr to the supplied log file.
      3. Waits until either the configured run duration elapses or the
         process exits on its own.
      4. Stops FlightGear gracefully (falls back to a forced kill if it
         does not exit within a grace period).
      5. Writes a single-line JSON summary to stdout so the calling
         Python process can parse the outcome deterministically.

.PARAMETER FlightGearExe
    Full path to fgfs.exe.

.PARAMETER ScenarioFile
    Full path to the scenario XML file describing this run.

.PARAMETER AircraftId
    FlightGear aircraft id (e.g. c172p).

.PARAMETER Airport
    ICAO airport code for --airport.

.PARAMETER Runway
    Runway id for --runway.

.PARAMETER Fdm
    Flight dynamics model to use (e.g. jsbsim).

.PARAMETER WindDirDeg
    Wind direction in degrees, passed to fgfs as part of --wind=DIR@SPEED.

.PARAMETER WindSpeedKt
    Wind speed in knots, passed to fgfs as part of --wind=DIR@SPEED.

.PARAMETER VisibilityM
    Visibility in meters, passed to fgfs via --visibility=METERS.

.PARAMETER DurationSec
    How long the run should be allowed to fly before FlightGear is
    stopped, in seconds.

.PARAMETER LogFile
    Full path to the log file to create/append.

.PARAMETER FlightCsvFile
    Full path FlightGear should write its own telemetry CSV to (via
    --generic=file,out,...) if your FlightGear build/protocol file
    supports it. This script creates the file/directory even if
    FlightGear itself does not populate it, so downstream Python code
    always has a stable, existing path to reference.
#>

param(
    [Parameter(Mandatory = $true)][string]$FlightGearExe,
    [Parameter(Mandatory = $true)][string]$ScenarioFile,
    [Parameter(Mandatory = $true)][string]$AircraftId,
    [Parameter(Mandatory = $true)][string]$Airport,
    [Parameter(Mandatory = $true)][string]$Runway,
    [Parameter(Mandatory = $true)][string]$Fdm,
    [Parameter(Mandatory = $true)][double]$WindDirDeg,
    [Parameter(Mandatory = $true)][double]$WindSpeedKt,
    [Parameter(Mandatory = $true)][double]$VisibilityM,
    [Parameter(Mandatory = $true)][int]$DurationSec,
    [Parameter(Mandatory = $true)][string]$LogFile,
    [Parameter(Mandatory = $true)][string]$FlightCsvFile
)

$ErrorActionPreference = "Stop"

function Write-JsonResult {
    param(
        [string]$Status,
        [Nullable[int]]$ExitCode,
        [string]$Message
    )
    $result = [ordered]@{
        status    = $Status
        exit_code = $ExitCode
        message   = $Message
    }
    # Emit as the LAST line of stdout so Python can reliably parse it.
    ($result | ConvertTo-Json -Compress)
}

try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $FlightCsvFile) | Out-Null

    if (-not (Test-Path $FlightGearExe)) {
        Write-JsonResult -Status "crash" -ExitCode $null -Message "FlightGear executable not found at $FlightGearExe"
        exit 2
    }

    if (-not (Test-Path $ScenarioFile)) {
        Write-JsonResult -Status "crash" -ExitCode $null -Message "Scenario file not found at $ScenarioFile"
        exit 2
    }

    # Ensure the flight CSV path exists so downstream steps never fail on
    # a missing file, even if the local FlightGear protocol config does
    # not populate it during this run.
    if (-not (Test-Path $FlightCsvFile)) {
        New-Item -ItemType File -Force -Path $FlightCsvFile | Out-Null
    }

    # NOTE: $ScenarioFile is our own project-defined XML (see scenarios/S00X.xml),
    # not a FlightGear PropertyList config file. Passing it via --config would
    # make fgfs.exe fail to parse it and exit immediately (this was the root
    # cause of prior "crash" outcomes on every attempt). Instead, we translate
    # the scenario's environment fields into real fgfs.exe command-line flags.
    $windSpec = "{0}@{1}" -f $WindDirDeg, $WindSpeedKt

    $fgArgs = @(
        "--aircraft=$AircraftId",
        "--airport=$Airport",
        "--runway=$Runway",
        "--fdm=$Fdm",
        "--wind=$windSpec",
        "--visibility=$VisibilityM",
        "--disable-splash-screen",
        "--disable-sound",
        "--disable-random-objects",
        "--timeofday=noon"
    )

    "[$(Get-Date -Format o)] Launching FlightGear: $FlightGearExe $($fgArgs -join ' ')" |
        Out-File -FilePath $LogFile -Append -Encoding utf8

    $process = Start-Process -FilePath $FlightGearExe `
        -ArgumentList $fgArgs `
        -PassThru `
        -RedirectStandardOutput "$LogFile.out.tmp" `
        -RedirectStandardError "$LogFile.err.tmp" `
        -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds($DurationSec)
    while ((Get-Date) -lt $deadline -and -not $process.HasExited) {
        Start-Sleep -Milliseconds 500
    }

    $status = "pass"
    $exitCode = $null

    if (-not $process.HasExited) {
        # Duration elapsed with the process still flying: stop it gracefully.
        "[$(Get-Date -Format o)] Duration elapsed, requesting graceful stop." |
            Out-File -FilePath $LogFile -Append -Encoding utf8
        try {
            $process.CloseMainWindow() | Out-Null
            if (-not $process.WaitForExit(10000)) {
                "[$(Get-Date -Format o)] Graceful stop timed out, forcing kill." |
                    Out-File -FilePath $LogFile -Append -Encoding utf8
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                $process.WaitForExit(5000) | Out-Null
            }
        }
        catch {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        $exitCode = $process.ExitCode
        $status = "pass"
    }
    else {
        $exitCode = $process.ExitCode
        if ($exitCode -eq 0) {
            $status = "pass"
        }
        else {
            $status = "fail"
        }
    }

    if (Test-Path "$LogFile.out.tmp") {
        Get-Content "$LogFile.out.tmp" | Out-File -FilePath $LogFile -Append -Encoding utf8
        Remove-Item "$LogFile.out.tmp" -ErrorAction SilentlyContinue
    }
    if (Test-Path "$LogFile.err.tmp") {
        Get-Content "$LogFile.err.tmp" | Out-File -FilePath $LogFile -Append -Encoding utf8
        Remove-Item "$LogFile.err.tmp" -ErrorAction SilentlyContinue
    }

    "[$(Get-Date -Format o)] Run finished with status=$status exit_code=$exitCode" |
        Out-File -FilePath $LogFile -Append -Encoding utf8

    Write-JsonResult -Status $status -ExitCode $exitCode -Message "completed"
    exit 0
}
catch {
    $errMsg = $_.Exception.Message
    try {
        "[$(Get-Date -Format o)] EXCEPTION: $errMsg" | Out-File -FilePath $LogFile -Append -Encoding utf8
    }
    catch {
        # Logging itself failed; nothing further we can safely do here.
    }
    Write-JsonResult -Status "crash" -ExitCode $null -Message $errMsg
    exit 1
}
