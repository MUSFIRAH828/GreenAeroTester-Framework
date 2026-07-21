"""
energy_collector.py
--------------------
Collects CPU, memory, runtime and estimated energy/carbon data for a
single scenario run.

The measurement strategy is implemented behind an abstract base class
(`EnergyMeasurementStrategy`) so that the default TDP-based estimator
used in the pilot can later be swapped for a CodeCarbon-backed strategy
without changing any calling code in experiment_runner.py.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class EnergySample:
    """A single point-in-time resource sample."""

    timestamp: float
    cpu_percent: float
    memory_mb: float


@dataclass
class EnergyMeasurement:
    """Final aggregated measurement for one run."""

    avg_cpu_percent: float
    peak_cpu_percent: float
    avg_memory_mb: float
    peak_memory_mb: float
    avg_power_watts: float
    peak_power_watts: float
    energy_joules: float
    energy_wh: float
    idle_energy_joules: float
    net_energy_joules: float
    carbon_intensity_g_per_kwh: float
    estimated_carbon_gco2: float
    measurement_source: str
    measurement_notes: str
    samples_collected: int


class EnergyMeasurementStrategy(ABC):
    """Abstract strategy for converting resource samples into energy figures."""

    @abstractmethod
    def estimate_power_watts(self, cpu_percent: float) -> float:
        """Return an instantaneous power estimate in watts for a CPU% sample."""
        raise NotImplementedError

    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError


class TdpEstimationStrategy(EnergyMeasurementStrategy):
    """Estimate power draw linearly between an idle baseline and a configured TDP.

    power(t) = idle_watts + (tdp_watts - idle_watts) * (cpu_percent(t) / 100)

    This is a coarse but dependency-free estimator suitable for the pilot.
    It is intentionally isolated behind the EnergyMeasurementStrategy
    interface so it can be replaced by a CodeCarbon-based strategy later
    (e.g. `CodeCarbonStrategy`) without touching EnergyCollector itself.
    """

    def __init__(self, idle_watts: float, tdp_watts: float) -> None:
        self.idle_watts = idle_watts
        self.tdp_watts = tdp_watts

    def estimate_power_watts(self, cpu_percent: float) -> float:
        cpu_fraction = max(0.0, min(cpu_percent, 100.0)) / 100.0
        return self.idle_watts + (self.tdp_watts - self.idle_watts) * cpu_fraction

    @property
    def source_name(self) -> str:
        return "cpu_tdp_estimation"


class EnergyCollector:
    """Samples CPU/memory for a target process (or the whole system) on a
    background thread while a scenario run is in progress, then produces
    an aggregated EnergyMeasurement once stopped.
    """

    def __init__(
        self,
        config: Config,
        strategy: Optional[EnergyMeasurementStrategy] = None,
        target_pid: Optional[int] = None,
    ) -> None:
        """
        Args:
            config: Global pipeline configuration.
            strategy: Power-estimation strategy. Defaults to TDP estimation
                using config.estimated_tdp_watts / config.idle_power_watts.
            target_pid: If provided, CPU/memory are sampled for that
                specific process (and its children). If None, system-wide
                CPU/memory are sampled instead, which is a safe fallback
                when the FlightGear process is launched indirectly via
                PowerShell and its PID is not available to Python.
        """
        self._config = config
        self._strategy: EnergyMeasurementStrategy = strategy or TdpEstimationStrategy(
            idle_watts=config.idle_power_watts,
            tdp_watts=config.estimated_tdp_watts,
        )
        self._target_pid = target_pid
        self._samples: List[EnergySample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._process_handle: Optional[psutil.Process] = None

        if target_pid is not None:
            try:
                self._process_handle = psutil.Process(target_pid)
            except psutil.NoSuchProcess:
                logger.warning(
                    "Target PID %s not found; falling back to system-wide sampling.",
                    target_pid,
                )
                self._process_handle = None

    def start(self) -> None:
        """Begin background sampling. Must be called before the scenario process starts."""
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.debug("EnergyCollector sampling started.")

    def stop(self) -> EnergyMeasurement:
        """Stop sampling and compute the final aggregated measurement.

        Must be called after the scenario process has fully exited.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._config.energy_sample_interval_sec * 3)
        self._end_time = time.time()
        return self._aggregate()

    def _sample_loop(self) -> None:
        interval = self._config.energy_sample_interval_sec
        while not self._stop_event.is_set():
            try:
                if self._process_handle is not None and self._process_handle.is_running():
                    cpu_percent = self._process_handle.cpu_percent(interval=None)
                    mem_info = self._process_handle.memory_info()
                    memory_mb = mem_info.rss / (1024 * 1024)
                else:
                    cpu_percent = psutil.cpu_percent(interval=None)
                    vmem = psutil.virtual_memory()
                    memory_mb = (vmem.total - vmem.available) / (1024 * 1024)

                self._samples.append(
                    EnergySample(
                        timestamp=time.time(),
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                    )
                )
            except psutil.NoSuchProcess:
                logger.debug("Target process exited during sampling; stopping loop.")
                break
            except Exception:  # noqa: BLE001 - sampling must never crash the run
                logger.exception("Error while collecting an energy sample; continuing.")

            self._stop_event.wait(timeout=interval)

    def _aggregate(self) -> EnergyMeasurement:
        runtime_sec = 0.0
        if self._start_time is not None and self._end_time is not None:
            runtime_sec = max(0.0, self._end_time - self._start_time)

        if not self._samples:
            logger.warning("No energy samples were collected; recording zeroed measurement.")
            avg_cpu = peak_cpu = 0.0
            avg_mem = peak_mem = 0.0
            avg_power = self._strategy.estimate_power_watts(0.0)
            peak_power = avg_power
        else:
            cpu_values = [s.cpu_percent for s in self._samples]
            mem_values = [s.memory_mb for s in self._samples]
            power_values = [self._strategy.estimate_power_watts(c) for c in cpu_values]

            avg_cpu = statistics.fmean(cpu_values)
            peak_cpu = max(cpu_values)
            avg_mem = statistics.fmean(mem_values)
            peak_mem = max(mem_values)
            avg_power = statistics.fmean(power_values)
            peak_power = max(power_values)

        energy_joules = avg_power * runtime_sec
        energy_wh = energy_joules / 3600.0
        idle_energy_joules = self._config.idle_power_watts * runtime_sec
        net_energy_joules = max(0.0, energy_joules - idle_energy_joules)
        estimated_carbon_gco2 = (energy_wh / 1000.0) * self._config.carbon_intensity_g_per_kwh

        return EnergyMeasurement(
            avg_cpu_percent=round(avg_cpu, 3),
            peak_cpu_percent=round(peak_cpu, 3),
            avg_memory_mb=round(avg_mem, 3),
            peak_memory_mb=round(peak_mem, 3),
            avg_power_watts=round(avg_power, 4),
            peak_power_watts=round(peak_power, 4),
            energy_joules=round(energy_joules, 4),
            energy_wh=round(energy_wh, 6),
            idle_energy_joules=round(idle_energy_joules, 4),
            net_energy_joules=round(net_energy_joules, 4),
            carbon_intensity_g_per_kwh=self._config.carbon_intensity_g_per_kwh,
            estimated_carbon_gco2=round(estimated_carbon_gco2, 6),
            measurement_source=self._strategy.source_name,
            measurement_notes=(
                f"samples={len(self._samples)}; "
                f"target={'pid:' + str(self._target_pid) if self._target_pid else 'system-wide'}"
            ),
            samples_collected=len(self._samples),
        )
