# GreenAeroTest Backend — Phase 1: Project Architecture & Scenario Generation

This is the Phase 1 deliverable of the GreenAeroTest backend, built against
the *Dataset Implementation Specification*. It contains **only** the
project skeleton and the scenario generation module. No execution, energy
collection, validation, scoring, prioritization, or dashboard code is
included yet — those arrive in later phases.

## What Phase 1 does

Deterministically generates the full **10 flight phases × 5 weather
profiles × 2 system modes = 100 scenario** catalog described in Spec
Section 3, and writes it to:

- `scenarios/scenario_catalog.csv` — one summary row per scenario (100 rows)
- `scenarios/scenario_parameters.csv` — one full-detail row per scenario (100 rows)
- `scenarios/generated/*.xml` — one placeholder scenario definition file per scenario (100 files)

## Requirements

- Python 3.13
- `pip install -r requirements.txt` (Phase 1 itself needs no third-party
  packages; the file also pins what later phases will need)

## Running Phase 1

```bash
cd backend
python main.py
```

This will:
1. Create any missing directories (`scenarios/generated/`, `logs/`, etc.).
2. Generate the 100 `Scenario` objects in deterministic order.
3. Write `scenario_catalog.csv`, `scenario_parameters.csv`, and the 100
   placeholder scenario files.
4. Log progress to the console and to `logs/greenaerotest.log`.

## Folder structure

```
backend/
│
├── config/
│   ├── settings.py       # paths & environment-specific configuration
│   └── constants.py      # spec taxonomy: phases, weather, modes, ID rules
│
├── scenarios/
│   ├── scenario_generator.py     # builds the 100-scenario catalog
│   ├── scenario_catalog.csv      # generated output (100 rows)
│   ├── scenario_parameters.csv   # generated output (100 rows)
│   └── generated/                # generated output (100 placeholder files)
│
├── models/
│   ├── scenario.py       # Scenario dataclass + CSV row serialization
│   └── enums.py          # FlightPhase, WeatherProfile, SystemMode, RunResult
│
├── utils/
│   ├── file_manager.py   # directory creation, CSV writing helpers
│   └── logger.py         # shared logging configuration
│
├── main.py                # Phase 1 CLI entry point
├── requirements.txt
└── README.md
```

## File-by-file guide

### `config/constants.py`
Every value copied straight out of the spec's static tables: the 10 flight
phases (with their faulted-mode fault), the 5 weather profiles, the 2
system modes, the ID formats (`S0001`, `T0001`, `R000001`, ...), and
count-derived constants like `TOTAL_SCENARIOS = 100`. This is the single
source of truth for "what the taxonomy is." It never changes at runtime.

### `config/settings.py`
Everything that *is* allowed to vary by machine/environment: the resolved
`backend/` root path, every input/output directory the project touches
(`scenarios/`, `scenarios/generated/`, `logs/`), and a few default runtime
knobs (log level, simulator name). `Paths.ensure_all()` creates every
directory it knows about, and every other module imports the shared
`settings` singleton instead of hardcoding path strings.

### `models/enums.py`
`FlightPhase`, `WeatherProfile`, `SystemMode` enums matching the spec
codes (`P01`..`P10`, `W01`..`W05`, `M0`/`M1`), plus a `RunResult` enum
(`pass`/`fail`/`timeout`/`crash`/`incomplete`) that isn't used yet in
Phase 1 but is defined now so Phase 2's executor and validators use the
exact same vocabulary from day one.

### `models/scenario.py`
The `Scenario` frozen dataclass — the in-memory shape of one generated
scenario, holding every field the spec's `scenario_catalog.csv` and
`scenario_parameters.csv` require. It knows how to flatten itself into
each of those two row schemas via `to_catalog_row()` and
`to_parameters_row()`, so the generator never has to know about CSV
column layout directly.

### `scenarios/scenario_generator.py`
The core Phase 1 module. `ScenarioGenerator.generate_all()` iterates
flight phase → weather profile → system mode in the exact nested order
given in Spec 3.4, builds 100 `Scenario` objects, and derives a
reproducible per-scenario `random_seed` from a single configured base
seed (default `42`, see `constants.SCENARIO_GENERATION_SEED`) — so
re-running the generator always produces an identical catalog.
`write_outputs()` then persists the catalog CSV, parameters CSV, and one
placeholder scenario definition file per scenario.

### `utils/file_manager.py`
Small stdlib-only helpers: `ensure_dir()` and `write_csv()`. Nothing
fancy — Phase 2's raw/processed/final dataset writers will build on top
of this rather than reimplementing CSV writing.

### `utils/logger.py`
`configure_logging()` sets up one consistent console + file logging
format for the whole process; `get_logger(__name__)` is what every module
calls to get its logger.

### `main.py`
The Phase 1 CLI entry point: configures logging, runs the generator, and
reports success/failure with a proper process exit code. Exceptions from
generation (`ScenarioGenerationError`) or filesystem I/O are caught and
logged rather than crashing with a raw traceback.

## How this plugs into Phase 2

Phase 2 (execution pipeline: `executor.py`, PowerShell runner, timeout
handling, energy collection) will:

- Read `scenarios/scenario_parameters.csv` (or import `ScenarioGenerator`
  directly) to get the 100 scenarios to run.
- Use each scenario's `scenario_file_path` / `output_dir` fields to know
  where to launch FlightGear from and where to write run outputs.
- Replace the placeholder files in `scenarios/generated/` with real,
  executable FlightGear/JSBSim configurations, without changing the
  catalog/parameters schema Phase 1 already produced.
- Reuse `config/settings.py`, `utils/logger.py`, and `utils/file_manager.py`
  as-is, and extend `models/enums.py` (`RunResult`) and a new `models/run.py`
  for the raw/clean run records described in Spec Section 7.

No Phase 1 file should need to change shape for Phase 2 to build on it —
only new files get added alongside it.
