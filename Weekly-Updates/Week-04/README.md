# GreenAeroTest — 5-Scenario Pilot

A controlled pilot implementation of the GreenAeroTest execution pipeline:
**5 unique scenarios x 10 repetitions = 50 total FlightGear/JSBSim runs**,
with full raw-attempt logging, per-run resource/energy measurement, and
resume-safe execution.

This is intentionally the *pilot* scope described in the specification
(Section 1.1) — not the full 100-scenario dataset. It validates that
FlightGear can be launched sequentially, monitored, stopped safely, and
recorded correctly, using the exact same controller, PowerShell runner,
timeout handling, energy collection, and CSV-writing logic that the full
implementation will reuse.

## Execution order

The outer loop is the **repetition number**, the inner loop is the
**scenario**, so no scenario ever runs 10 times in a row:

```
Run 1: S001, S002, S003, S004, S005
Run 2: S001, S002, S003, S004, S005
...
Run 10: S001, S002, S003, S004, S005
```

## 1. Installing dependencies

Requires Python 3.13 (also tested and working on 3.12) and Windows with
PowerShell, since `run_scenario.ps1` is invoked via `powershell.exe`.

```powershell
cd greenaerotester
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` currently contains only `psutil`. The energy
measurement module is deliberately built around a swappable
`EnergyMeasurementStrategy` interface (see `src/energy_collector.py`) so
`codecarbon` can be added to `requirements.txt` and dropped in later as
a second strategy class without changing `experiment_runner.py`.

## 2. Configuring FlightGear paths

All configuration lives in `src/config.py` as a single `Config`
dataclass, and every value can be overridden with an environment
variable instead of editing code:

| Setting | Env var | Default |
|---|---|---|
| FlightGear executable | `GAT_FLIGHTGEAR_EXE` | `C:\Program Files\FlightGear 2020.3\bin\fgfs.exe` |
| Flight dynamics model | `GAT_FDM` | `jsbsim` |
| Run duration (sec) | `GAT_RUN_DURATION_SEC` | `90` |
| Timeout (sec) | `GAT_TIMEOUT_SEC` | `180` |
| Cooldown between runs (sec) | `GAT_COOLDOWN_SEC` | `10` |
| Estimated TDP (W), for power estimation | `GAT_ESTIMATED_TDP_WATTS` | `65` |
| Idle power baseline (W) | `GAT_IDLE_POWER_WATTS` | `12` |
| Carbon intensity (gCO2/kWh) | `GAT_CARBON_INTENSITY_G_PER_KWH` | `400` |
| Repetitions | `GAT_REPETITIONS` | `10` |
| Environment ID | `GAT_ENVIRONMENT_ID` | `ENV001` |

At minimum, set `GAT_FLIGHTGEAR_EXE` to match your local install, e.g.:

```powershell
$env:GAT_FLIGHTGEAR_EXE = "C:\Program Files\FlightGear 2020.3\bin\fgfs.exe"
```

Each scenario XML in `scenarios/S00X.xml` also specifies the aircraft
(`c172p`), airport (`KSFO`), runway (`28L`), and FDM (`jsbsim`) used for
that run — adjust these to match aircraft/scenery you have installed
locally if `c172p`/`KSFO` aren't available.

## 3. Running the project

```powershell
python run_pipeline.py
```

This will:

1. Load `scenarios/scenario_catalog.csv` (5 rows).
2. Loop 10 repetitions x 5 scenarios (50 planned executions).
3. For each execution: launch FlightGear via
   `scripts/run_scenario.ps1`, sample CPU/memory/power with
   `psutil` for the run's duration, and classify the outcome as
   `pass`, `fail`, `timeout`, `crash`, or `incomplete`.
4. Immediately append one row to `data/test_runs_raw.csv` and one
   matching row to `data/energy_metrics_raw.csv` per attempt.
5. Automatically **rerun** any `timeout` / `crash` / `incomplete`
   attempt (up to 10 attempts per slot) until a usable `pass`/`fail`
   outcome is recorded for that `(scenario, run_no)` pair.
6. Apply a configurable cooldown between executions.

**Interrupting is safe.** If you stop the pipeline (Ctrl+C, power
loss, etc.) and re-run `python run_pipeline.py`, it reads
`data/test_runs_raw.csv`, determines which `(scenario_id, run_no)`
pairs already have a `pass`/`fail` outcome, and resumes from the next
incomplete slot instead of restarting all 50 runs. Run IDs (`R000001`,
`R000002`, ...) also continue from the highest ID already recorded, so
reruns never collide with previous attempts.

## 4. Expected output after successful execution

- `data/test_runs_raw.csv` — one row per execution *attempt*. Because
  rerun attempts are also logged, this file can have **more than 50
  rows** if any timeouts/crashes occurred; it will have **exactly 50
  rows** if every scenario passed or failed cleanly on the first try.
- `data/energy_metrics_raw.csv` — exactly one energy row per row in
  `test_runs_raw.csv` (same `run_id`).
- `outputs/logs/T0XX_R0000XX.log` — one PowerShell/FlightGear log per
  attempt.
- `outputs/flight_csv/T0XX_R0000XX.csv` — one flight telemetry CSV per
  attempt (path is always created, even if FlightGear's own protocol
  output isn't configured on your machine).
- `outputs/raw_power_traces/` — reserved for external power-meter
  traces if you later swap in a physical/measured energy source
  instead of the default TDP estimator; unused by the TDP strategy
  itself since power is estimated per-sample rather than logged as a
  separate trace file.
- `outputs/logs/pipeline.log` — overall run log for the whole pipeline
  execution (both console and file logging are configured in
  `run_pipeline.py`).

At the end of a clean run, `data/test_runs_raw.csv` will contain 50
rows with `result=pass` or `result=fail`, `run_no` values 1–10 for each
of the 5 scenarios, and monotonically increasing `run_id` values from
`R000001` to `R000050`.

## 5. Assumptions made

- **`c172p` / `KSFO` / `28L`** were used as placeholder
  aircraft/airport/runway values in all 5 scenario XML files since the
  specification does not pin down a specific aircraft or airfield for
  the pilot. Update the `<initial_conditions>` block in each
  `scenarios/S00X.xml` to match your installed FlightGear scenery and
  aircraft package.
- **Scenario XML schema** is a simplified, self-defined format (see
  the `<scenario>` root element in each `S00X.xml`) rather than a
  literal FlightGear/JSBSim scenario schema, since the exact schema
  depends on your FlightGear version and installed protocol/property
  files. Only fields that map directly to real `fgfs.exe` command-line
  flags are ever passed to FlightGear:
  `--aircraft`, `--airport`, `--runway`, `--fdm`, `--wind=DIR@SPEED`
  (from `wind_dir_deg`/`wind_speed_kt`), and `--visibility=METERS`
  (from `visibility_m`). The scenario XML file itself is **not** passed
  to FlightGear as `--config` — FlightGear's `--config` flag expects a
  PropertyList-format file, and our custom schema is not one; passing
  it there causes `fgfs.exe` to reject it and exit immediately. The
  richer `<fault_injection>` block is captured in the file for
  traceability and is ready to be wired into your specific FlightGear
  property-set or JSBSim script/Nasal mechanism for fault injection —
  it is not yet translated into a command-line flag.
- **PID-based process sampling**: because FlightGear is launched
  indirectly through `powershell.exe` → `fgfs.exe`, `energy_collector.py`
  defaults to **system-wide** CPU/memory sampling rather than sampling
  a specific FlightGear PID (Python doesn't have a direct handle on the
  child `fgfs.exe` process). `EnergyCollector` accepts an optional
  `target_pid` if you extend `run_scenario.ps1` to report FlightGear's
  PID back to Python and want to sample it directly instead.
- **Power/energy values are estimated**, not measured, using a linear
  CPU%-to-watts model between a configurable idle baseline and TDP
  (see `TdpEstimationStrategy` in `energy_collector.py`). This mirrors
  the specification's `energy_joules = avg_power_watts * runtime_sec`
  formula and is explicitly isolated behind an
  `EnergyMeasurementStrategy` interface so a `CodeCarbon`-backed
  strategy can be substituted later without touching
  `experiment_runner.py` or `data_store.py`.
- **Carbon intensity** defaults to a generic grid-average value
  (400 gCO2/kWh) via `GAT_CARBON_INTENSITY_G_PER_KWH`; set this to your
  actual grid region's value for meaningful carbon estimates.
- **Rerun cap**: rerunning a `timeout`/`crash`/`incomplete` slot is
  capped at 10 attempts per `(scenario, run_no)` to avoid an infinite
  retry loop on a persistently broken scenario/environment; every
  attempt (including failed reruns) is still preserved in
  `test_runs_raw.csv`.
- **This pilot deliberately omits** the full-scale-only modules named
  in the parent specification (`scenario_generator.py`,
  `aggregate_runs.py`, `assurance_scorer.py`, `prioritizer.py`,
  `baselines.py`, `knapsack_selector.py`, `reporting.py`, the
  Streamlit `web/` dashboard, etc.), since those operate on the full
  100-scenario / 1,000-run dataset and are out of scope for this
  5-scenario x 10-repetition pilot.

## Troubleshooting

If every attempt for a scenario comes back as `crash` (especially if it
happens in just a second or two — too fast for FlightGear to actually
have started flying), FlightGear is exiting immediately on launch. To
diagnose:

1. Open the corresponding log file, e.g. `outputs/logs/T001_R000001.log`.
   It contains the exact `fgfs.exe` command line that was run, plus
   FlightGear's own stdout/stderr, which will usually say exactly why
   it exited (bad aircraft id, bad airport/runway combination, missing
   scenery, invalid flag, etc.).
2. Try running that same command manually in a PowerShell window to
   see FlightGear's output live, e.g.:
   ```powershell
   & "C:\Program Files\FlightGear 2020.3\bin\fgfs.exe" --aircraft=c172p --airport=KSFO --runway=28L --fdm=jsbsim --wind=0@0 --visibility=10000
   ```
3. Common causes: the aircraft id (`c172p`) or airport/runway
   (`KSFO`/`28L`) isn't installed locally — edit the
   `<aircraft>`/`<initial_conditions>` blocks in the relevant
   `scenarios/S00X.xml` to match aircraft/scenery you actually have.
4. If FlightGear opens but the pipeline still marks the run `timeout`,
   increase `GAT_TIMEOUT_SEC` — first-launch FlightGear scenery/shader
   compilation can take well over the default 180 seconds on some
   machines.

## Project layout

```
greenaerotester/
├── scenarios/
│   ├── scenario_catalog.csv     # 5 scenarios: id, test_id, phase, weather, mode, file
│   ├── S001.xml ... S005.xml    # per-scenario config (aircraft, airport, environment, faults)
├── src/
│   ├── config.py                # single source of truth for all configurable constants
│   ├── executor.py              # launches FlightGear via PowerShell, classifies outcomes
│   ├── energy_collector.py      # psutil-based CPU/memory/power/energy/carbon sampling
│   ├── data_store.py            # append-only CSV writer + resume helpers
│   └── experiment_runner.py     # nested repetition/scenario loop, run-id generation, reruns
├── scripts/
│   └── run_scenario.ps1         # single-run PowerShell launcher for fgfs.exe
├── data/
│   ├── test_runs_raw.csv        # one row per execution attempt
│   └── energy_metrics_raw.csv   # one row per execution attempt (matches test_runs_raw)
├── outputs/
│   ├── logs/                    # per-run + pipeline logs
│   ├── flight_csv/              # per-run flight telemetry CSVs
│   └── raw_power_traces/        # reserved for external power-meter traces
├── run_pipeline.py              # entry point
├── requirements.txt
└── README.md
```
