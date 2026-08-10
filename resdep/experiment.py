#!/usr/bin/env python3
"""
Resonant depolarisation experiment (class).
Designed to called through one of the GUIs (
[`resdepGUI`][resdep.resdepGUI], [`simpleGUI`][resdep.simpleGUI]).
Can also be instanced and run natively in command line.
"""
"""
██████╗ ███████╗███████╗ ██████╗ ███╗   ██╗ █████╗ ███╗   ██╗████████╗  
██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗████╗  ██║╚══██╔══╝  
██████╔╝█████╗  ███████╗██║   ██║██╔██╗ ██║███████║██╔██╗ ██║   ██║     
██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╗██║██╔══██║██║╚██╗██║   ██║     
██║  ██║███████╗███████║╚██████╔╝██║ ╚████║██║  ██║██║ ╚████║   ██║     
╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝     
██████╗ ███████╗██████╗  ██████╗ ██╗      █████╗ ██████╗ 
██╔══██╗██╔════╝██╔══██╗██╔═══██╗██║     ██╔══██╗██╔══██╗
██║  ██║█████╗  ██████╔╝██║   ██║██║     ███████║██████╔╝ █████╗
██║  ██║██╔══╝  ██╔═══╝ ██║   ██║██║     ██╔══██║██╔══██╗ ╚════╝
██████╔╝███████╗██║     ╚██████╔╝███████╗██║  ██║██║  ██║
╚═════╝ ╚══════╝╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
██╗███████╗ █████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██║██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║███████╗███████║   ██║   ██║██║   ██║██╔██╗ ██║
██║╚════██║██╔══██║   ██║   ██║██║   ██║██║╚██╗██║
██║███████║██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║
╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝                                                                       
"""                         

import itertools
import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum
import platform
import builtins
from typing import Union, Callable, Optional, Literal
import logging
import traceback
import epics
import time
import datetime
from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from math import ceil
from scipy.ndimage import gaussian_filter1d

from resdep.epicsBLMs import BLMs, CountingMode # Libera BLM instuments
from resdep.epicsBPMs import SR_BPMs, MX3_BPMs, TBPMs  # BPM subclasses
from resdep._plotting import Plotter, StandaloneGraph
from resdep._fitting import Fitter
import resdep._constants as const
from resdep._calculations import energy_calc
from resdep._progressBars import printProgressBar
from resdep._archiver import bioSAXSRampStatus, IMBLRampStatus, ADSRampStatus

class ScanType(Enum):
    NONE = 0
    AUTOMATIC = 1
    NORMAL = 2
    WIDE = 3

class State(IntEnum):
    READY = 0
    ABORTED = 1
    INITIALISING = 2 
    RUNNING = 3
    FINISHED = 4

class SweepDirection(IntEnum):
    """
    Direction of frequency sweep for experiment.
    """
    BACKWARD = -1
    FORWARD = 1

class InjectionMode(IntEnum):
    UNDEFINED = 0
    FAKE_INJECTION = 1 
    GUN_INJECTION = 2
    UNKNOWN = 3

class ResonantDepolarisation:
    """
    Resdep class that stores key variables to and functions to run the experiment.
    Is written to (optionally) take in additional Qt callback functionality, 
    but is not required.
    Therefore, it can be run in the terminal, or through `resdepGUI`|`simpleGUI`.

    Attributes
    ----------
    res_freq: float
        Resonant frequency of the spin tune.

    harmonic: int
        Harmonic of the resonant frequency.
        
    bounds: float
        The energy bounds (plus minus, as a decimal) over which to scan.
        Usually on the order of 0.05%

    set_kicker_amp: float
        Kicker amplifier (percentage as decimal).
        Defaults to 0.5 (50%).

    set_drive_pattern: str
        The bunches to be driven.
        Takes form `"start_bunch:end_bunch"`.

    sweep_rate: float
        The rate at which the kicker frequencies are swept over.
        Defaults to 5 Hz/s.

    set_adc_counter_offset_1, set_adc_counter_window_1: int
        One set of the ADC (analog to digital converter) offset / window 
        applied to the beam loss monitors.
        Used to separate the beam into two charge equivalent halves, 
        only one of which is _depolarised.
        The ratio of the losses between the polarised and _depolarised halves 
        are used to indicate the spin tune.

    freqs: list[float]
        Readback of BbB kicker frequency (slow ~ 0.5 Hz)

    set_freqs: list[float]
        Frequency values during the experiment sweep

    beam_loss_window_1, beam_loss_window_2: dict[str, list[float]]
        Beam loss from the corresponding ADC window.
        Keys of the form ``"{sector}{section}"``.
        where section is either A = straight, or B = bend. e.g. `"4A"`

    data_path: pathlib.Path
        Directory where data is saved as simple binaries (txt, json)

    Warning
    -------
    `sweep_rate` values over 10 Hz/s may be too fast to effectively _depolarise.

    Note
    ----
    This Class is passed by reference when instancing the 
    [processed data][resdep.experiment.ProcessedData] class,
    and helper classes for [fitter][resdep._fitting.Fitter] and 
    [plotting][resdep._plotting.Plotter].
    This is to access exact experiment parameters that change slightly between 
    each sweep, such as revolution frequency.
    """                                                                     
    def __init__(
        self,
        progress_callback: Optional[Callable] = None,
        plot_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        data_path_callback: Optional[Callable] = None,
        timer_callback: Optional[Callable] = None,
        ADC_windows_callback: Optional[Callable] = None,
        results_callback: Optional[Callable] = None,
        state_callback: Optional[Callable] = None,
        processed_data_callback: Optional[Callable] = None,
    ) -> None:
        """
        Initialise default scan values.

        Parameters
        ----------
        progress_callback:
            Passed progress update (`step`: [`int`][]) emitted by worker 
            function spawned by GUI.
            Links to progress bar in either 
            [`resdepGUI`][resdep.resdepGUI.MainWindow.on_progress_update] 
            or
            [`simpleGUI`][resdep.simpleGUI.MainWindow.on_progress_update]
        plot_callback:
            Live plotting data (
            `freqs`, `beam_loss_window_1`, `beam_loss_window_2`
            )
            plotted to 
            [`resdepGUI`][resdep.resdepGUI.MainWindow.on_new_plot_info].
        status_callback:
            Experiment status ([`str`][]) to displayed on either
            [`resdepGUI`][resdep.resdepGUI.MainWindow.on_status_update] 
            or
            [`simpleGUI`][resdep.simpleGUI.MainWindow.on_status_update]
        data_path_callback:
            data path ([`pathlib.Path`][]) to passed to GUI for 
            saving GUI config / settings.
        timer_callback:
            An emitted signal of when to start / stop the experiment timer.
            Links to [`resdepGUI`][resdep.resdepGUI.MainWindow.on_start_timer]
        ADC_windows_callback:
            Pass back ADC windows applied to BLMs,
            specifically for [`resdepGUI`][resdep.resdepGUI].

        Examples
        --------
        Example usage / implementation in the `Class` scope.

        ```py
        self.status_callback("Finished!")

        path = Path("usr/data/example")
        self.data_path_callback(path)

        self.timer_callback()
        ```

        Notes
        -----
        See configuration of callbacks in
        [`QtWorkerDecorator`][resdep.resdepGUI.QtWorkerDecorator] 
        and the [GUI][resdep.resdepGUI.MainWindow.__init__].

        Calls [`_calculate_range`][resdep.experiment.ResonantDepolarisation._calculate_range] 
        on default values.
        """                                               
        self._config_logger()

        self.progress_callback = progress_callback
        self.plot_callback = plot_callback
        if status_callback is not None:
            self.status_callback = status_callback
        else:
            self.status_callback = self.logger.info
        self.data_path_callback = data_path_callback
        self.timer_callback = timer_callback
        self.ADC_windows_callback = ADC_windows_callback
        self.results_callback = results_callback
        self.state_callback = state_callback
        self.processed_data_callback = processed_data_callback

        # --- init states
        self._abort_requested = False
        self._injecting: bool = False
        self._measuring_SR_BPMs: bool = False
        self._measuring_TBPMs: bool = False
        self._measuring_MX3_BPMs: bool = False

        # default f_rev. Will calculate f_rev from masterRF on experiment start
        # (so to avoid any epics connection on init)
        self.f_rev: float = const.f_rev  # kHz

        # --- experimental variables
        self.direction: Literal["X", "Y"] = "Y"  # 'X' or 'Y'
        self.tune: float = const.v_s303GeV  # v_s, or v_s303GeV
        self.harmonic: int = 1  # int >= 0
        self.bounds: float = 0.05 / 100  # input %, output decimal
        self.freq_shift: float = 0  # shifting off calculated resonance, KHz
        self.set_kicker_amp: float = 0.5  # % (0-1)
        self.set_drive_pattern: str = (
            "36:215"  # 'start:stop' or '!' for all. Start at '1' not '0'
        )
        self.set_sweep_direction: SweepDirection = SweepDirection.FORWARD
        self.set_sweep_span: float = 0  # kHz
        self.set_sweep_period: float = 0  # us
        self.sweep_rate: float = 5  # Hz/s
        self.sweep_step_size: float = 0.5  # Hz - minimum allowable = 0.5
        self.log_frequency: int = (
            10  # data logging frequency, Hz
        )
        # ADC masks (defaults)
        self.set_adc_counter_offset_1: int = 0
        self.set_adc_counter_window_1: int = 42
        self.set_adc_counter_offset_2: int = 42
        self.set_adc_counter_window_2: int = 44
        self.set_counting_mode: CountingMode = (
                CountingMode.DIFFERENTIAL
        )

        # initialise some data storage early for GUI plot purposes
        self.freqs: list[float] = []
        self.set_freqs: list[float] = []
        self.beam_loss_window_1: dict[str, list[float]] = {}
        self.beam_loss_window_2: dict[str, list[float]] = {}
        self.res_freq: float = 1225
        self.data_path: Path

        self._calculate_range()

        self.state = State.READY
        if self.state_callback is not None:
            self.state_callback(state=self.state)

        return None
    # *--------------------------------* #
    # *---------- Experiment ----------* #
    # *--------------------------------* #
    def start_experiment(
        self,
    ) -> None:
        """
        Resonant depolarisation experiment, uses bunch-by-bunch kicker to 
        _depolarise bunches, and measures the corresponding beam loss.
        
        Attributes
        ----------
        set_kicker_amp: float
            Kicker amplifier setpoint, as decimal (0--1)
        set_sweep_freq: float
            Kicker frequency setpoint, kHz
        beam_loss_window_1, beam_loss_window_2: dict[str, list[float]]
            Beam loss from each ADC window across every sector

        Raises
        ------
        KeyboardInterrupt:
            On abort request, or from terminal

        Notes: Workflow
        -----
        - Initialises the experiment (calculates f_rev, frequency range for 
            sweep, loads PVs, configs save files)
        - Takes 10s of baseline data (with the kicker turned off)
        - Initialises kicker (drive) panel with set amplitude and frequency
        - Slowly steps through the requested energy (frequency) range 
            (typically at 5 Hz/s, physically updates drive frequency in 0.5 Hz steps)
        - Configures the `adc_counts_offset` and `_window` to record beam loss 
            on the polarised and _depolarised parts of the beam separately
        - The ratio of the _depolarised/polarised beam losses will then 
            normalise out spurrious depolarisation events, 
            e.g. ID gap changes, magnet instabilities, etc.
        - Reads the beam loss for every monitor (readback at 10 Hz). 
            See [`_log_data`][resdep.experiment.ResonantDepolarisation._log_data].
        - When finished
            - Turns off kicker drive and resets BLM decimation / ADC windows.
            - Saves and plots data on experiment end or [`KeyboardInterrupt`][]
        - Listens for injections -> turns off kicker and sleeps for 10 s (
            through PV callback 
            [`__on_value_change`][resdep.experiment.ResonantDepolarisation.__on_value_change]
        )
        - Listens for abort requests from the optional GUIs
        - Updates experiment progress to progress bar on GUI or console
        """                                         

        self.state = State.INITIALISING
        self._has_stored_data: bool = False

        try:  # if any of this fails then the experiment should shutdown

            # --- start-up
            self._config_data_path()
            self._calc_revolution_frequency_from_master_RF()
            self._calculate_range()
            self.status_callback("Setting up PVs...")
            self._load_PVs()
            self._config_save_objects()
            self.calculate_adc_counter_windows(sector=1)

            self.injection_trigger.add_callback(callback=self.__on_value_change)

            self.blm.apply_full_decimation()
            self.blm.apply_adc_counter_masks(
                offset_1=self.set_adc_counter_offset_1,
                window_1=self.set_adc_counter_window_1,
                offset_2=self.set_adc_counter_offset_2,
                window_2=self.set_adc_counter_window_2,
                counting_mode=self.set_counting_mode,
            )

            self.logger.info("|--------------------------------------------|")
            self.logger.info("|----------- BEGINNING EXPERIMENT -----------|")
            self.logger.info("|---------- Resonant Depolarisation ---------|")
            self.logger.info("|--------------------------------------------|")
            
            self._collect_baseline_data(duration_seconds=10)
            self._has_stored_data = True

            self.state = State.RUNNING
            if self.state_callback is not None:
                self.state_callback(state=self.state)
            self._depolarise()

        except Exception:
            self.logger.error(traceback.format_exc())

        finally:
            self.logger.info("|--------------------------------------------|")
            self.logger.info("|------------- EXPERIMENT DONE ! ------------|")
            self.logger.info("|--------------------------------------------|")

            self.status_callback("Cleaning up...")

            self._abort_requested = False

            if self.progress_callback is not None:
                self.progress_callback(
                        step = self.sweep_steps,
                        max_steps = self.sweep_steps
                )

            if self._has_stored_data:
                self.save_data()
            else:
                self.logger.warning("No data collected, files will not be saved.")

            self.logger.info("Turning kicker off...")
            try:
                self.kicker_amp_PV.put(0, use_complete=True)
                while not self.kicker_amp_PV.put_complete:
                    time.sleep(0.05)
                self.logger.info("Kicker OFF!")
            except AttributeError:
                self.logger.critical(
                    "Kicker PV not loaded, not able to turn off."
                    + "If PV not loaded, the kicker shouldn't be on anyway. "
                    + "Check the BbB Y DRIVE just in case: \n"
                    + "IGPF:Y:DRIVE:AMPL"
                )
            except Exception:
                error = traceback.format_exc()
                self.logger.error(error)

            try:
                self.injection_trigger.clear_callbacks()
            except AttributeError:
                self.logger.warning(
                    "Tried to remove epics.pv callback but " 
                    + "injection trigger PV not loaded."
                )
            except Exception:
                error = traceback.format_exc()
                self.logger.error(error)


            # restore epicsBLM window settings
            self.logger.info("Attempting to restore BLM inits...")
            try:
                self.blm.restore_inits(mode="adc_counter_masks")
                self.blm.restore_inits(mode="decimation")
            except Exception:
                error = traceback.format_exc()
                self.logger.error(error)

            if self.plot_callback is None:
                self.logger.info(
                    "To manually plot data from the terminal, "
                     + "run class method `plot_data()`, "
                     + "or edit and run scripts\\plotdata.py"
                )

            if not self._abort_requested and self._has_stored_data:
                self.status_callback("Analysing data...")
                (
                    E0_mean_sigfig, 
                    E0_stddev_sigfig, 
                    formatted_beam_energy, 
                    error
                ) = self._post_processing()

                if error is not None:
                    self.logger.error(error)
                else:
                    self.logger.info("Beam energy = {formatted_beam_energy}")
                if self.results_callback is not None:
                    self.results_callback(formatted_beam_energy, error)

            self.logger.info("Done everything :)")

            self.state = State.FINISHED
            if self.state_callback is not None:
                self.state_callback(state=self.state)

        return None
    # -------------------------------------------------------------------------
    def _collect_baseline_data(self, duration_seconds: int) -> None:
        """
        Collect baseline BLM / BPM / whatever save data with kicker OFF

        Parameters
        ----------
        duration_seconds: int
            Length of time to collect data in seconds
        """
        self.status_callback("Collecting baseline BPM data (10 s)...")
        if not self.status_callback == self.logger.info:
            self.logger.info("Collecting baseline BPM data (10 s)...")

        # init kicker drive (except amp) here so that save_data() 
        # collects values that are set to the start of the sweep range, 
        # rather than the end of the previous sweep/experiment.
        self.sweep_freq_PV.put(
            self.set_sweep_freq, use_complete=True
        )  # kHz
        self.sweep_span_PV.put(
            self.set_sweep_span, use_complete=True
        )  # kHz
        self.sweep_period_PV.put(
            self.set_sweep_period, use_complete=True
        )  # us
        self.pattern_PV.put(
                self.set_drive_pattern, use_complete=True
        ) # str
        while not all(
            [
                self.sweep_freq_PV.put_complete,
                self.sweep_span_PV.put_complete,
                self.sweep_period_PV.put_complete,
                self.pattern_PV.put_complete
            ]
        ):
            time.sleep(0.05)


        end_time: float = time.time() + duration_seconds

        while time.time() <= end_time:
            self._log_data()
            if self._abort_requested:
                self.status_callback("Experiment interrupted!")
                raise InterruptedError(
                        "Experiement aborted during baseline data acquisition."
                )

            time.sleep(1/self.log_frequency)

        self.logger.info("Baseline data acquired.")


        return None
    # -------------------------------------------------------------------------
    def _depolarise(self, ) -> None:
        """
        The resonant depolarisation experiment loop.
        The details of the experiment workflow are under 
        [`start_experiment`][resdep.experiment.ResonantDepolarisation.start_experiment]
        """
        self.logger.info("Starting depolarisation scan...")

        self.kicker_amp_PV.put(self.set_kicker_amp, use_complete=True) # %
        while not self.kicker_amp_PV.put_complete:
            time.sleep(0.05)
            
        step: int = 0
        self.status_callback("Running")
        if self.timer_callback is not None:
            self.timer_callback()

        next_kicker_call: float = time.time() + self.dwell_time
        next_log_call: float = time.time() + 1/self.log_frequency
        PROGRESS_UPDATE_FREQUENCY: int = 1 # Hz
        next_progress_update_call: float = (
            time.time() + 1/PROGRESS_UPDATE_FREQUENCY
        )
        
        while step <= self.sweep_steps:
            now: float = time.time()

            if now >= next_kicker_call:
                self.set_sweep_freq += (
                    self.set_sweep_direction * self.sweep_step_size * 1e-3
                )  # kHz
                self.sweep_freq_PV.put(self.set_sweep_freq)  # kHz
                step += 1
                next_kicker_call: float = time.time() + self.dwell_time

            if now >= next_log_call:
                self._log_data()
                next_log_call: float = time.time() + 1/self.log_frequency

            if now >= next_progress_update_call:
                if self.progress_callback is not None:
                    self.progress_callback(
                            step=step,
                            max_steps=self.sweep_steps
                    )
                else:
                    printProgressBar(
                        iteration=step,
                        total=self.sweep_steps,
                        decimals=2,
                    )
                if self.plot_callback is not None:
                    self.plot_callback(
                        self.freqs,
                        self.beam_loss_window_1,
                        self.beam_loss_window_2,
                    )
                next_progress_update_call: float = (
                    time.time() + 1/PROGRESS_UPDATE_FREQUENCY                    
                )

            if self._injecting:
                self.kicker_amp_PV.put(0)
                self.status_callback("Sleeping (injection), kicker => OFF")

                self.__interruptible_sleep(10)

                self.kicker_amp_PV.put(
                    self.set_kicker_amp, use_complete=True
                )
                while not self.kicker_amp_PV.put_complete:
                    time.sleep(0.05)
                self.status_callback("Running")
                self._injecting = False

            if self._abort_requested:
                self.status_callback("Experiment aborted!")
                raise InterruptedError(
                        "Experiment aborted during depolarisation scan."
                )

            time.sleep(0.01)

        self.logger.info("Depolarisation scan complete.")

        return None
    # -------------------------------------------------------------------------
    def _post_processing(self) -> tuple[
            Optional[float], Optional[float], Optional[str], Optional[str]]:
        """
        Post processing data analysis pipeline.
        Create ProcessedData object, calculate ratio_loss().
        Perform fit, calculate stats, return formatted result.
        """
        E0_mean_sigfig: Optional[float] = None
        E0_stddev_sigfig: Optional[float] = None
        formatted_beam_energy: Optional[str] = None
        error: Optional[str] = None

        try:  
            processed_data = ProcessedData(resdep=self)
            fitter = Fitter(processed_data, self)
            processed_data.calculate_ratio_loss()

            (
                E0_mean_sigfig, 
                E0_stddev_sigfig, 
                formatted_beam_energy, 
                error
            ) = fitter.automagic_fit()
            
            processed_data.save_data()

            if self.processed_data_callback is not None:
                energy_array = energy_calc(
                        freq=processed_data.freqs_array,
                        f_rev=self.f_rev,
                        harmonic=self.harmonic
                )
                self.processed_data_callback(
                        freqs_array=processed_data.freqs_array,
                        energy_array=energy_array,
                        ratio_loss=processed_data.ratio_loss
                )

        # Catch something critical that `automagic_fit()` does not handle
        except Exception:
            error: str = traceback.format_exc()
            self.logger.error(error)

        finally:
            # update GUI
            if error is not None:
                formatted_beam_energy = "Error with fit."
                return (
                    E0_mean_sigfig, 
                    E0_stddev_sigfig, 
                    formatted_beam_energy, 
                    error
                )


            if formatted_beam_energy is not None:
                with open(self.data_path / "beam_energy.txt", "w") as f:
                    f.write(formatted_beam_energy)
                if (self.data_path / "beam_energy.txt").exists():
                    logging.debug(
                            "beam energy txt file saved successfully."
                    )
                else:
                    logging.debug("beam energy txt file not saved.")

        return (
                E0_mean_sigfig, 
                E0_stddev_sigfig, 
                formatted_beam_energy, 
                error
            )
    # -------------------------------------------------------------------------
    def _calculate_range(
        self,
    ) -> None:
        """
        Calculates the frequency and energy range over which the experiment sweeps.

        Attributes
        ----------
        res_freq: float
                Expected resonant frequency of the spin tune
        sweep_limits: list[float]
                Frequency limits of the sweep
        dwell_time: float
                Time (in seconds) spent kicking at each frequency
        estimated_sweep_time: str
                Estimated time of the experiment sweep, in seconds
        """             
        # --- calcs
        self.intrinsic_res_freq: float = (
            self.f_rev * (self.tune + 0) + self.freq_shift
        )  # 0th order, kHz
        self.res_freq: float = (
            self.f_rev * (self.tune + self.harmonic) + self.freq_shift
        )  # harmoinc order, kHz
        self.expected_energy: float = (
            (self.tune + 6) * const.m_e * const.c**2 / (const.a_g * const.e)
        )  # eV
        self.expected_energy_bounds: float = (
            self.expected_energy * self.bounds
        )  # eV
        self.expected_energy_limits: list[float] = [
            self.expected_energy - self.expected_energy_bounds,
            self.expected_energy + self.expected_energy_bounds,
        ]  # eV
        self.freq_bounds: float = self.f_rev * (
            (self.tune + 6) * self.bounds
        )  # kHz
        self.sweep_limits: list[float] = [
            self.res_freq - self.freq_bounds,
            self.res_freq + self.freq_bounds,
        ]  # kHz
        self.sweep_range: float = self.freq_bounds * 2  # kHz
        self.sweep_steps: int = int(
            self.sweep_range * 1e3 // self.sweep_step_size
        )
        self.sweep_time: float = self.sweep_range * 1e3 / self.sweep_rate  # s
        self.dwell_time: float = self.sweep_step_size / self.sweep_rate  # s
        if self.set_sweep_direction == SweepDirection.FORWARD:
            # sweep start (lowest frequency for forward scan), kHz
            self.set_sweep_freq: float = self.sweep_limits[0]  
            self.sweep_end: float = self.sweep_limits[-1]
        elif self.set_sweep_direction == SweepDirection.BACKWARD:
            # sweep start (higest frequency for backward scan), kHz
            self.set_sweep_freq: float = self.sweep_limits[-1] 
            self.sweep_end: float = self.sweep_limits[0]
        else:
            raise ValueError(
                "set_sweep_direction should be one of SweepDirection.FOWARD, "
                + "SweepDirection.BACKWARD (enum)."
            )

        number_of_top_ups = self.sweep_time // 137  # every 2'17"
        self.estimated_sweep_time: str = str(
            datetime.timedelta(
                seconds=int(self.sweep_time + 10 * number_of_top_ups)
            )
        )

        return None
    # -------------------------------------------------------------------------
    def _load_PVs(
        self,
    ) -> None:
        """
        Loads all EPICS process variables (PVs) required to run the experiment
        and those important for experiment metadata (e.g. LCW temp)

        Notes
        -----
        Calls upon extensible Classes [`BLMs`][resdep.epicsBLMs.BLMs] and 
        [`BPMs`][resdep.epicsBPMs].

        Danger
        ------
        Ensure call statements to PVs (like `.get()` and `.put()`) are robust 
        against the PVs possibly **not connecting** 
        (e.g. when they're out of service).
        Code blocks such as waiting for `.put()` to complete with the 
        `put_complete` flag will wait *forever* if the PV is not connected.
        I recommend use of the `.connected` PV attribute to protect such calls.
        """         
        # --- BLMs
        self.blm = BLMs()
        self.blm.get_loss_PVs()
        self.blm.get_adc_counter_mask_PVs()
        self.blm.get_decimation()
        self.blm.get_t2_trigger_delays()

        # --- BPMs
        # Storage ring
        if self._measuring_SR_BPMs:
            self.sr_bpms = SR_BPMs()
            self.sr_bpms.connect()
        # TBPMs
        if self._measuring_TBPMs:
            self.tbpms = TBPMs()
            self.tbpms.connect()
        # MX3
        if self._measuring_MX3_BPMs:
            self.mx3_bpms = MX3_BPMs()
            self.mx3_bpms.connect()

        # --- drive
        self.sweep_freq_act_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:FREQ_ACT", connect=True, timeout=0.5
        )
        self.sweep_freq_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:FREQ", connect=True, timeout=0.5
        )
        self.sweep_span_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:SPAN", connect=True, timeout=0.5
        )
        self.sweep_period_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:PERIOD", connect=True, timeout=0.5
        )
        self.kicker_amp_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:AMPL", connect=True, timeout=0.5
        )
        self.pattern_PV: epics.pv.PV = epics.pv.get_pv(
            f"IGPF:{self.direction}:DRIVE:PATTERN", connect=True, timeout=0.5
        )
        BbB_PVs: list[epics.pv.PV] = [
            self.sweep_freq_act_PV,
            self.sweep_freq_PV,
            self.sweep_span_PV,
            self.sweep_period_PV,
            self.kicker_amp_PV,
            self.pattern_PV,
        ]
        if not all([pv.connected for pv in BbB_PVs]):
            raise ConnectionRefusedError(
                "BbB PVs not connecting. Check Kubili."
            )

        # --- current
        self.dcct: epics.pv.PV = epics.pv.get_pv(
            "SR11BCM01:CURRENT_MONITOR", connect=True, timeout=0.5
        )

        # --- injection trigger
        self.injection_trigger: epics.pv.PV = epics.pv.get_pv(
            "TS01EVG01:INJECTION_MODE_STATUS", connect=True, timeout=0.5
        )
        if not self.injection_trigger.connected:
            raise ConnectionRefusedError(
                "Injection trigger PV wont connect. "
                + "This is required to ignore beam loss spikes on injection."
            )

        # --- Wigglers
        bioSAXS_field_monitor_PV: epics.pv.PV = epics.pv.get_pv(
                pvname="SR02SCU01:FIELD_MONITOR",
                connect=True
        )
        IMBL_field_monitor_PV: epics.pv.PV = epics.pv.get_pv(
                pvname="SR08SCW01:FIELD_MONITOR",
                connect=True
        )
        ADS_field_monitor_PV: epics.pv.PV = epics.pv.get_pv(
                pvname="SR10SCW01:FIELD_MONITOR",
                connect=True
        )
        wiggler_PVs: dict[str, epics.pv.PV] = {
                "bioSAXS": bioSAXS_field_monitor_PV,
                "IMBL": IMBL_field_monitor_PV,
                "ADS": ADS_field_monitor_PV
        }
        self.wiggler_fields: dict[str, float] = {}
        for wiggler, pv in wiggler_PVs.items():
            if pv.connected and pv.value is not None:
                self.wiggler_fields[wiggler] = pv.value
        # NOTE: This check is depreciated due to unreliable RAMP_STATUS
        #       behaviour.
        # wiggler ramp status
        # self.bioSAXS_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
        #         "SR02SCU01:RAMP_STATUS", connect=True, timeout=1
        # )
        # self.IMBL_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
        #         "SR08SCW01:FIELD_RAMPING_STATUS", connect=True, timeout=1
        # )
        # self.ADS_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
        #         "SR10SCW01:RAMP_STATUS", connect=True, timeout=1
        # )
        # self.wiggler_ramp_staus_PVs: dict[str, epics.pv.PV] = {
        #         "bioSAXS": self.bioSAXS_ramp_status_PV,
        #         "IMBL": self.IMBL_ramp_status_PV,
        #         "ADS": self.ADS_ramp_status_PV
        # }
        # for pv in self.wiggler_ramp_staus_PVs.values():
        #     pv.add_callback(self._on_wiggler_ramp)


        # --- SR/LCW/RF temperatures
        # initialise PV dicts
        RF601_LCW_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF602_LCW_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF701_LCW_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF702_LCW_temperature_PVs: dict[str, epics.pv.PV] = {}

        RF601_body_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF602_body_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF701_body_temperature_PVs: dict[str, epics.pv.PV] = {}
        RF702_body_temperature_PVs: dict[str, epics.pv.PV] = {}

        magnet_temperature_PVs: dict[str, epics.pv.PV] = {}
        tunnel_air_temperature_PVs: dict[str, epics.pv.PV] = {}
        beam_pipe_temperature_PVs: dict[str, epics.pv.PV] = {}
        slab_temperature_PVs: dict[str, epics.pv.PV] = {}
        SUBH_temperature_PVs: dict[str, epics.pv.PV] = {}

        self.temperature_PV_dicts: list[dict[str, epics.pv.PV]] = [
            RF601_LCW_temperature_PVs,
            RF602_LCW_temperature_PVs,
            RF701_LCW_temperature_PVs,
            RF702_LCW_temperature_PVs,
            RF601_body_temperature_PVs,
            RF602_body_temperature_PVs,
            RF701_body_temperature_PVs,
            RF702_body_temperature_PVs,
            magnet_temperature_PVs,
            tunnel_air_temperature_PVs,
            beam_pipe_temperature_PVs,
            slab_temperature_PVs,
            SUBH_temperature_PVs,
        ]

        # grab PVs
        sectors: list[int] = [6, 7]
        cavities: list[int]= [1, 2]
        # RF LCW
        RF_LCW_PV_dicts: list[dict[str, epics.pv.PV]] = [
            RF601_LCW_temperature_PVs,
            RF602_LCW_temperature_PVs,
            RF701_LCW_temperature_PVs,
            RF702_LCW_temperature_PVs,
        ]
        for (sector, cavity), PV_dict in zip(
                itertools.product(sectors, cavities), RF_LCW_PV_dicts
            ):
            prefix = f"SR{sector:02d}RF{cavity:02d}"
            pvname = f"{prefix}RLD01:INLET_WATER_TEMP_MONITOR"
            PV_dict[pvname] = (
                epics.pv.get_pv(
                    pvname,
                    connect=True,
                    timeout=0.5,
                )
            )
            pvname: str = f"{prefix}CIR01:INLET_WATER_TEMP_MONITOR"
            PV_dict[pvname] = (
                epics.pv.get_pv(
                    pvname,
                    connect=True,
                    timeout=0.5,
                )
            )
            pvname: str = f"{prefix}KLY01:BODY_INLET_TEMP_MONITOR"
            PV_dict[pvname] = (
                epics.pv.get_pv(
                    pvname,
                    connect=True,
                    timeout=0.5,
                )
            )
            pvname: str = f"{prefix}CAV01:INLET_TEMPERATURE_MONITOR"
            PV_dict[pvname] = (
                epics.pv.get_pv(
                    pvname,
                    connect=True,
                    timeout=0.5,
                )
            )

        # RF body
        RF_bodytemp_PV_dicts: list[dict[str, epics.pv.PV]] = [
            RF601_body_temperature_PVs,
            RF602_body_temperature_PVs,
            RF701_body_temperature_PVs,
            RF702_body_temperature_PVs,
        ]
        for (sector, cavity), PV_dict in zip(
                itertools.product(sectors, cavities), RF_bodytemp_PV_dicts
            ):
            prefix = f"SR{sector:02d}RF{cavity:02d}TES"
            for monitor in range(1, 14 + 1, 1):
                pvname: str = f"{prefix}{monitor:02d}:TEMPERATURE_MONITOR"
                PV_dict[pvname] = (
                    epics.pv.get_pv(
                        pvname,
                        connect=True,
                        timeout=0.5,
                    )
                )
            prefix = f"SR{sector:02d}RF{cavity:02d}CIR01"
            pvname: str = f"{prefix}:RF_TEMP_MONITOR"
            PV_dict[pvname] = epics.pv.get_pv(
                pvname, connect=True, timeout=0.5
            )
            pvname: str = f"{prefix}:REGULATOR_TEMP_MONITOR"
            PV_dict[pvname] = epics.pv.get_pv(
                pvname, connect=True, timeout=0.5
            )
            pvname: str = f"{prefix}:SHUNT_TEMP_MONITOR"
            PV_dict[pvname] = epics.pv.get_pv(
                pvname, connect=True, timeout=0.5
            )

        # magnets
        magnet_temperature_PV_names: list[str] = [
            "SR01TES02:TEMPERATURE_MONITOR",
            "SR01TES05:TEMPERATURE_MONITOR",
            "SR01TES06:TEMPERATURE_MONITOR",
            "SR09TES07:TEMPERATURE_MONITOR",
            "SR09TES08:TEMPERATURE_MONITOR",
            "SR09TES11:TEMPERATURE_MONITOR",
            "SR12TES01:TEMPERATURE_MONITOR",
        ]
        for PV_name in magnet_temperature_PV_names:
            magnet_temperature_PVs[PV_name] = epics.pv.get_pv(
                PV_name, connect=True, timeout=0.5
            )

        # tunnel air temp
        tunnel_air_temperature_PV_names: list[str] = [
            "SR01TES03:TEMPERATURE_MONITOR",
            "SR06TES01:TEMPERATURE_MONITOR",
            "SR07TES01:TEMPERATURE_MONITOR",
        ]
        for PV_name in tunnel_air_temperature_PV_names:
            tunnel_air_temperature_PVs[PV_name] = epics.pv.get_pv(
                PV_name, connect=True, timeout=0.5
            )

        # beam pipe
        beam_pipe_temperature_PV_names: list[str] = [
            "SR08TES11:TEMPERATURE_MONITOR",
            "SR08TES12:TEMPERATURE_MONITOR",
        ]
        for PV_name in beam_pipe_temperature_PV_names:
            beam_pipe_temperature_PVs[PV_name] = epics.pv.get_pv(
                PV_name, connect=True, timeout=0.5
            )

        # slab
        slab_temperature_PVs["SR04TES12:TEMPERATURE_MONITOR"] = (
            epics.pv.get_pv(
                "SR04TES12:TEMPERATURE_MONITOR", connect=True, timeout=0.5
            )
        )

        # SUBH
        for index in range(1, 5+1, 1):
            PV_name = f"TEMP-SUBH{index:02d}-IN:TEMP_MONITOR"
            SUBH_temperature_PVs[PV_name] = epics.pv.get_pv(
                PV_name, connect=True, timeout=0.5
            )

        # initialise temperature dicts
        RF601_LCW_temperatures: dict[str, float] = {}
        RF602_LCW_temperatures: dict[str, float] = {}
        RF701_LCW_temperatures: dict[str, float] = {}
        RF702_LCW_temperatures: dict[str, float] = {}

        RF601_body_temperatures: dict[str, float] = {}
        RF602_body_temperatures: dict[str, float] = {}
        RF701_body_temperatures: dict[str, float] = {}
        RF702_body_temperatures: dict[str, float] = {}

        magnet_temperatures: dict[str, float] = {}
        tunnel_air_temperatures: dict[str, float] = {}
        beam_pipe_temperatures: dict[str, float] = {}
        slab_temperatures: dict[str, float] = {}
        SUBH_temperatures: dict[str, float] = {}

        self.temperature_value_dicts: list[dict[str, float]] = [
            RF601_LCW_temperatures,
            RF602_LCW_temperatures,
            RF701_LCW_temperatures,
            RF702_LCW_temperatures,
            RF601_body_temperatures,
            RF602_body_temperatures,
            RF701_body_temperatures,
            RF702_body_temperatures,
            magnet_temperatures,
            tunnel_air_temperatures,
            beam_pipe_temperatures,
            slab_temperatures,
            SUBH_temperatures,
        ]

        self.temperature_save_file_names: list[str] = [
            "RF601_LCW_temperatures.json",
            "RF602_LCW_temperatures.json",
            "RF701_LCW_temperatures.json",
            "RF702_LCW_temperatures.json",
            "RF601_body_temperatures.json",
            "RF602_body_temperatures.json",
            "RF701_body_temperatures.json",
            "RF702_body_temperatures.json",
            "magnet_temperatures.json",
            "tunnel_air_temperatures.json",
            "beam_pipe_temperatures.json",
            "slab_temperatures.json",
            "SUBH_temperatures.json",
        ]

        # grab PV.value(s) - no need for .get()
        # loop over all PVs and their corresponding value dictionaries
        # have to zip and nest loop due to unique keys for each cavity
        for PV_dict, value_dict in zip(
            self.temperature_PV_dicts, self.temperature_value_dicts
        ):
            for key, pv in PV_dict.items():
                if pv.connected:
                    value_dict[key] = pv.value

        return None
    # -------------------------------------------------------------------------
    def _config_logger(self,) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        # create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        self.logger_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
        )
        # add handler to the logger
        console_handler.setFormatter(self.logger_formatter)
        return None
    # -------------------------------------------------------------------------
    def _config_data_path(
        self,
    ) -> None:
        # --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) 
        # e.g. Data\2025-09-25\0900h\
        self.start_time = datetime.datetime.now()
        date_str = self.start_time.strftime("%Y-%m-%d")
        year_str = self.start_time.strftime("%Y")
        hours_str = self.start_time.strftime("%H%Mh")
        seconds_str = self.start_time.strftime("%Ss")
        hostname = platform.node()
        match_ioc = re.search("ioc", hostname, re.IGNORECASE)
        match_opi = re.search("opi", hostname, re.IGNORECASE)
        if match_ioc is not None and match_opi is not None:
            raise ValueError(
                    f"$HOSTNAME={hostname} matched both 'ioc' and 'opi'. " 
                    +"Cannot decide which logic to implement."
            )
        if match_ioc is not None:
            self.data_path = Path(
                f"/asp/usr/data/resdep/{year_str}/{date_str}/{hours_str}"
            )
        elif match_opi is not None:
            self.data_path = Path(
                f"/asp/usr/data/resdep/{year_str}/{date_str}/{hours_str}"
            )
        else: # no match to opi or ioc
            current_path = Path.cwd()
            self.data_path = (
                current_path / "data" / "resdep" / date_str / hours_str
            )
        try:
            Path.mkdir(self.data_path, parents=True, exist_ok=False)
        except FileExistsError:
            # if you run the script again in the same minute, 
            # it appends seconds to the path name
            self.data_path = self.data_path / seconds_str
            Path.mkdir(self.data_path, parents=True)

        if self.data_path_callback is not None:
            self.data_path_callback(self.data_path)

        handlers = self.logger.handlers.copy()
        for handler in handlers:
            if type(handler) is logging.FileHandler:
                handler.close()
                self.logger.removeHandler(handler)

        file_handler = logging.FileHandler(
            filename=self.data_path/"logfile.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self.logger_formatter)
        self.logger.addHandler(file_handler)

        return None
    # -------------------------------------------------------------------------
    def _config_save_objects(
        self,
    ) -> None:
        """
        Initialises save directory (uniquely timestamped) and python objects
        """
        self.freqs: list[float] = []
        self.set_freqs: list[float] = []
        self.current: list[Union[float, None]] = []
        self.timestamps: list[datetime.datetime] = []
        self.formatted_timestamps: list[str] = []
        self.injections: list[datetime.datetime] = []
        self.injections_str: list[str] = []
        self.beam_loss_window_1: dict[str, list[float]] = {}
        self.beam_loss_window_2: dict[str, list[float]] = {}
        for key in self.blm.loss_PV:
            self.beam_loss_window_1[key] = []
            self.beam_loss_window_2[key] = []
        self.projected_end_time: datetime.datetime = (
            self.start_time + datetime.timedelta(seconds=self.sweep_time)
        )
        duration: str = time.strftime("%H:%M:%S", time.gmtime(self.sweep_time))
        self.metadata: dict[str, Union[float, list[float], str]] = {
            "direction": self.direction,
            "duration": duration, 
            "fractional tune": self.tune,
            "f_rev": self.f_rev,
            "bounds (%)": self.bounds,
            "frequency bounds (kHz)": self.freq_bounds,
            "harmonic": self.harmonic,
            "sweep limits (kHz)": self.sweep_limits,
            "kicker amp (%)": self.set_kicker_amp,
            "drive pattern": self.set_drive_pattern,
            "sweep direction": self.set_sweep_direction,
            "sweep rate (Hz/s)": self.sweep_rate,
            "sweep step size (Hz)": self.sweep_step_size,
            "sweep span (kHz)": self.set_sweep_span,
            "sweep period (us)": self.set_sweep_period,
            "start time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "projected end time": self.projected_end_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
        self.metadata.update(self.wiggler_fields)
    # -------------------------------------------------------------------------
    def _log_data(
        self,
    ) -> None:
        """
        Appends PV values to python lists at fast_log_frequency Hz.
        Stored in memory until 
        [`save_data`][resdep.experiment.ResonantDepolarisation.save_data] 
        is called.

        Saved Values
        ------------
        - ADC window loss
        - Kicker frequency
        - Current
        - timestamps
        - BPM position and intensity (with `resdepGUI` checkbox)
        """                     
        try:
            timestamp: datetime.datetime = datetime.datetime.now()
            formatted_timestamp: str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            self.timestamps.append(timestamp)
            self.formatted_timestamps.append(formatted_timestamp)
            self.set_freqs.append(self.set_sweep_freq)
            freq: Union[float, None] = self.sweep_freq_act_PV.get(timeout=0.5)
            if freq is not None:
                self.freqs.append(freq)  # kHz
            else:
                self.freqs.append(
                    np.nan
                )  # still append something so that the vectors are the same size
            if self.dcct.connected:
                I = self.dcct.get(timeout=0.5)  # noqa: E741
                if I is None:
                    I = np.nan  # noqa: E741
                if I < 150: # Abort if beam dump or drop out of top-up
                    self.request_abort()
                self.current.append(I)  # A

            # BLMs
            for key in self.blm.loss_PV:
                counter_loss_1: Union[float, None] = (
                        self.blm.adc_counter_loss_1_PV[key].get(timeout=0.5)
                )
                if counter_loss_1 is not None:
                    self.beam_loss_window_1[key].append(counter_loss_1)
                else:
                    self.beam_loss_window_1[key].append(np.nan)
                counter_loss_2: Union[float, None] = (
                        self.blm.adc_counter_loss_2_PV[key].get(timeout=0.5)
                )
                if counter_loss_2 is not None:
                    self.beam_loss_window_2[key].append(counter_loss_2)
                else:
                    self.beam_loss_window_2[key].append(np.nan)

            # BPMs
            if self._measuring_SR_BPMs:
                self.sr_bpms.record_data()
            if self._measuring_TBPMs:
                self.tbpms.record_data()
            if self._measuring_MX3_BPMs:
                self.mx3_bpms.record_data()

        except Exception:
            self.logger.error(traceback.format_exc())

        return None
    # -------------------------------------------------------------------------
    def _calc_revolution_frequency_from_master_RF(
        self,
    ) -> None:
        """
        Calculate a more accurate (current-time) revolution frequency 
        (f_rev) based off current Master RF

        Attributes
        ----------
        f_rev: float
            Revolution frequency
        """
        masterRF_PV: epics.pv.PV = epics.pv.get_pv(
            "SR00MOS01:FREQUENCY_MONITOR", connect=True, timeout=0.5
        )
        if masterRF_PV.connected and masterRF_PV.value is not None:
            self.f_rev: float = 1e-3 * masterRF_PV.value / 360  # kHz

        return None
    # -------------------------------------------------------------------------
    def calculate_adc_counter_windows(self, sector: int = 1) -> None:
        """Calculates the offsets and window lengths of the two counter windows 
        for a specific sector.

        Parameters
        ----------
        sector: int, default=1
            The sector to align to, defaults to 1 which has the nicest 
            reconstructed fill/loss pattern.

        Returns
        -------
        adc_counter_windows: list[int]
            list containing counters 1 & 2 window and offset settings for 
            the given sector.
            Values are a list of `[offset_1, window_1, offset_2, window_2]`

        _depolarised_bunches: str
            list containing the start:stop range of bunches to be _depolarised 
            using the BbB.
            This is basically a conversion from the ADC cycles 
            (window length and pos) to bunch number.

        Raises
        ------
        TypeError
            If PVs timeout and return `None`.

        Notes
        -----
        This only works for one sector, since there is no way to make the ADC 
        windows wrap around `T0`. Thus, the 'half' of the beam that the ADC 
        windows capture informs the bunches that should be _depolarised by the 
        BbB, and said half is unlikely to line up with the bunch numbers 
        (*i.e.* unlikely to be bunches 1--180).

        Regardless of the shape / phase of the fill pattern seen by the BLM:

            +---------------+   +---------------+
            | +-----------+ |   |---------+  +--|
            | |           | |   |         |  |  |
            | |           | |   |         |  |  |
            |-+           +-|   |         +--+  |
            +---------------+   +---------------+

            +---------------+   +---------------+
            |-+  +----------|   |------+  +-----|
            | |  |          |   |      |  |     |
            | |  |          |   |      |  |     |
            | +--+          |   |      +--+     |
            +---------------+   +---------------+

        we can simply integrate the fill pattern from the left until we reach 
        exactly half of the area under the curve to split the beam into two 
        *charge equivalent* halves. ADC windows can be calculated directly 
        from the point which divides the beam into the charge eqivalent halves.

        From there, we can calculate the time / phase difference between the 
        BLM and BbB system and calculate the bunches to be _depolarised. 
        Alignment is done by finding the minima of the fill pattern seen by 
        each system and shifting the BbB by the difference between them.

        """                                                                 
        self.logger.info(
            "Status: Time aligning BLM ADC windows and BbB system..."
        )   

        GOOD_ALIGNMENT_SECTORS: list[int] = [
            1, 2, 3, 4, 11, 12
        ]
        if sector not in self.blm.sectors_connected:
            alternative_sectors: list[int] = list(set(
                GOOD_ALIGNMENT_SECTORS
            ).intersection(self.blm.sectors_connected))
            if len(alternative_sectors) == 0:
                raise ConnectionError(
                    "All possible BLMs with good alignment properties to the " 
                    + "bunch-by-bunch system are out-of-service. "
                    + "resdep unable to run without enough active BLMs."
                )
            else:
                sector = alternative_sectors[0]

        # SUM Decimation
        SUM_DEC: int = 86
        SUMDEC_PERIODS: int = 50
        BUCKETS_PER_CYCLE: float = 360 / SUM_DEC

        # --- BbB waveform PVs --- #
        SRAM_x_waveform_PV: epics.pv.PV = epics.pv.get_pv(
            "IGPF:X:SRAM:MEAN", connect=True, timeout=1
        )
        SRAM_y_waveform_PV: epics.pv.PV = epics.pv.get_pv(
            "IGPF:Y:SRAM:MEAN", connect=True, timeout=1
        )
        if not all([
            pv.connected for pv in [SRAM_x_waveform_PV, SRAM_y_waveform_PV]
        ]):
            raise ConnectionRefusedError(
                "SRAM waveform PVs in BbB disconnected."
            )

        SRAM_x_waveform: Union[npt.NDArray[np.floating], None] = (
            SRAM_x_waveform_PV.get(timeout=1)
        )
        SRAM_y_waveform: Union[npt.NDArray[np.floating], None] = (
            SRAM_y_waveform_PV.get(timeout=1)
        )
        if SRAM_x_waveform is None or SRAM_y_waveform is None:
            raise TypeError("SRAM x and/or y waveforms returned None")

        # --- BLM --- #
        # set number of revolutions for integrated buffer
        try:
            current_number_of_sumdec_periods: Union[float, None] = (
                self.blm.init_sumdec_periods[f"{sector}"]
            )
        except KeyError as exc:
            raise ConnectionRefusedError(
                f"BLM sector {sector} is disconnected or out-of-service."
            ) from exc
        if current_number_of_sumdec_periods is None:
            raise TypeError(
                f"sumdec_periods for sector={sector} returned None"
            )
        if current_number_of_sumdec_periods < 20:
            self.blm.sumdec_periods_PV[f"{sector}"].put(
                SUMDEC_PERIODS
            )  
            self.status_callback(
                    "Waiting for injection to update integrated buffer..."
                )
            while not self._injecting:
                self.__interruptible_sleep(1)
            self.status_callback(
                    "Time aligning BLM ADC windows and BbB system..."
                )

        integrated_buffer_loss: Union[npt.NDArray, None] = (
            self.blm.integrated_buffer_loss_PV[f"{sector}B"].get(timeout=0.5)
        )
        if integrated_buffer_loss is None:
            raise TypeError(
                    "Integrated buffer loss returned None"
        )
        time.sleep(0.5)
        # integrated buffer is updside down, need to normalise
        integrated_buffer_loss = (
                integrated_buffer_loss / integrated_buffer_loss.max()        
        )
        # and flip
        integrated_buffer_loss = integrated_buffer_loss * -1 + 1
        # and shift by trigger 2 (T2) delay
        T2_delay: Union[int, float, None] = (
                self.blm.init_t2_trigger_delays[f"{sector}"]
        )
        if T2_delay is not None:
            T2_delay = int(T2_delay) % SUM_DEC
        else:
            raise TypeError(
                f"T2 delay for BLM in sector {sector} returned None"
            )
        integrated_buffer_loss = np.concatenate(
            (
                integrated_buffer_loss[T2_delay:],
                integrated_buffer_loss[:T2_delay],
            )
        )

        # separate the fill pattern into two charge equivalent halves
        integrated_fill_pattern: np.floating = np.sum(integrated_buffer_loss)
        cumsum_fill_pattern: npt.NDArray = np.cumsum(integrated_buffer_loss)
        dividing_line: int = int(np.flatnonzero(
            cumsum_fill_pattern < integrated_fill_pattern/2
            ).max() + 1
        )
        # format: [offset_1, window_1, offset_2, window_2]
        adc_counter_windows: list[int] = [
            0,
            dividing_line,
            dividing_line,
            (SUM_DEC - dividing_line),
        ]
        bucket_offset_1, bucket_window_1, bucket_offset_2, bucket_window_2 = [
            BUCKETS_PER_CYCLE * adc_cycle
            for adc_cycle in adc_counter_windows
        ]

        # Align the BbB and BLM by finding the middle of the empty buckets in 
        # both fill patterns.
        blm_middle_empty_bucket: int = self._find_middle_of_empty_buckets(
            fill_pattern=integrated_buffer_loss
        )
        SRAM_x_middle_empty_bucket: int = self._find_middle_of_empty_buckets(
            fill_pattern=SRAM_x_waveform
        )
        SRAM_y_middle_empty_bucket: int = self._find_middle_of_empty_buckets(
            fill_pattern=SRAM_y_waveform
        )
        # FPM X and Y can be slighly different shapes. I take the average of 
        # the two.
        SRAM_middle_empty_bucket: int = (
            SRAM_x_middle_empty_bucket + SRAM_y_middle_empty_bucket
        )//2

        self.logger.debug(
            f"BbB SRAM middle empty bucket={SRAM_middle_empty_bucket}"
        )
        self.logger.debug(f"BLM middle empty bucket={blm_middle_empty_bucket}")

        # Shift the calculated _depolarised bunches by the time offset between
        # the BLM and BbB system (given by the difference in the empty buckets)
        bucket_offset_1: int = int(
            bucket_offset_1
            + SRAM_middle_empty_bucket
            - (blm_middle_empty_bucket * BUCKETS_PER_CYCLE)
        )
        bucket_offset_2: int = int(
            bucket_offset_2
            + SRAM_middle_empty_bucket
            - (blm_middle_empty_bucket * BUCKETS_PER_CYCLE)
        )
        # After aligning the empty buckets, are the starts of the windows
        # within 1:360? If not, loop in circular buffer.
        if (bucket_offset_1 < 1) or (bucket_offset_1 > 360):
            bucket_offset_1 = (bucket_offset_1 - 1) % 360 + 1
        if (bucket_offset_2 < 1) or (bucket_offset_2 > 360):
            bucket_offset_2 = (bucket_offset_2 - 1) % 360 + 1

        # The start of one window is the end of the other.
        _depolarised_bunch_start: int = bucket_offset_1
        _depolarised_bunch_end: int = bucket_offset_2 - 1
        _depolarised_bunches: str = (
            f"{_depolarised_bunch_start}:{_depolarised_bunch_end}"
        )

        # update experiment settings
        self.set_drive_pattern = _depolarised_bunches
        [
            self.set_adc_counter_offset_1,
            self.set_adc_counter_window_1,
            self.set_adc_counter_offset_2,
            self.set_adc_counter_window_2,
        ] = adc_counter_windows

        # update GUI
        if self.ADC_windows_callback is not None:
            self.ADC_windows_callback(
                adc_counter_windows, _depolarised_bunches
            )

        self.logger.debug(
            "Calculated adc_counter windows, format: [offset_1, window_1, offset_2, window_2]"
        )
        self.logger.debug(adc_counter_windows)
        self.logger.debug("Corresponding _depolarised bunches for BbB:")
        self.logger.debug(_depolarised_bunches)

        return None
    # -------------------------------------------------------------------------
    def _find_middle_of_empty_buckets(
        self, fill_pattern: npt.NDArray[np.floating]
    ) -> int:
        """
        Calculates the middle of the empty buckets in the fill pattern.
        Used in 
        [`calculate_adc_counter_windows`][resdep.experiment.ResonantDepolarisation.calculate_adc_counter_windows].

        Parameters
        ----------
        fill_pattern: npt.NDArray[np.floating]
            Fill pattern / bunch train of the electron beam

        Returns
        -------
        middle_of_empty_buckets: int
            The argument of the middle of the empty buckets with respect to 
            the input shape of `fill_pattern`.
        """             

        boundary: int = len(fill_pattern)
        threshold: float = 0.6 * max(fill_pattern)
        args_under_threshold: npt.NDArray = np.flatnonzero(
                fill_pattern < threshold
        )
        if len(args_under_threshold) == 0:
            raise ArithmeticError(
                "Can't find minimum (empty buckets) in fill pattern "
                + "(args_under_threshold is empty)."
            )
        # Account for empty buckets wraping around T0
        BOUNDARY_BUCKETS = 5
        if any(
                args_under_threshold < BOUNDARY_BUCKETS
            ) and any(
                args_under_threshold > (boundary - BOUNDARY_BUCKETS)
        ):
            difference_in_args = (
                args_under_threshold[1:] - args_under_threshold[:-1]
            )
            jump_in_args = np.argmax(difference_in_args)
            # undo wrap around T0
            args_under_threshold[:(jump_in_args+1)] += boundary

        middle_empty_bucket_arg = int(np.mean(args_under_threshold)) % boundary

        return middle_empty_bucket_arg
    # *--------------------------------* #
    # *-------- Post-processing -------* #
    # *--------------------------------* #
    # -------------------------------------------------------------------------
    def save_data(
        self,
    ) -> None:
        """
        Saves PV data to compressed numpy (`.npz`) and dictionaries to `.json` 
        respectively. Also appends endtime to metadata. 

        Notes
        -----
        Save path is `data_path/{YYYY}/{YYYY-mm-dd}/{HHHH}h`.

        `data_path` is either:

        1. `usr/data/resdep` - on OPIs
        2. `./data` - elsewhere

        *e.g.* `usr/data/2025/2025-10-20/0900h`
        """             

        try:
            self.logger.info("Saving data...")

            del self.metadata["projected end time"]
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.metadata.update(
                {
                    "end time": end_time,
                    "Last sweep frequency": self.set_sweep_freq,
                }
            )
            with open(self.data_path / "metadata.json", "w") as f:
                json.dump(self.metadata, f)

            freqs_np = np.array(self.freqs, dtype=np.float64)
            np.savez_compressed(self.data_path / "freqs.npz", freqs_np)

            set_freqs_np = np.array(self.set_freqs, dtype=np.float64)
            np.savez_compressed(self.data_path / "set_freqs.npz", set_freqs_np)

            current_np = np.array(self.current, dtype=np.float64)
            np.savez_compressed(self.data_path / "current.npz", current_np)

            timetamps_np = np.array(self.timestamps, dtype=np.datetime64)
            np.savez_compressed(self.data_path / "timestamps.npz", timetamps_np)


            # Saving the beam loss data as raw jsons results in large file 
            # sizes (e.g. 3 MB per file). This adds up quickly and the data 
            # folder in resdep for 6 months worth of data is ~ 3 GB. 
            # Now, we cast the list[float] values to numpy arrays and save as 
            # compressed .npz -> 400 kB per file (86% reduction).
            # I have also moved the freqs, set_freqs, current and timestamps
            # to use npz compression
            # To load these files, use:
            # ```py
            # >>> restored_dict: dict[str, npt.NDArray] = {}
            # >>> with np.load("adc_counter_loss_1.npz") as loaded:
            # ...   for key in loaded.files:
            # ...       restored_dict[key] = loaded[key]
            # ```
            beam_loss_window_1_np: dict[str, npt.NDArray[np.floating]] = {}
            beam_loss_window_2_np: dict[str, npt.NDArray[np.floating]] = {}
            for key, list_of_values in self.beam_loss_window_1.items():
                beam_loss_window_1_np[key] = np.array(list_of_values)
            for key, list_of_values in self.beam_loss_window_2.items():
                beam_loss_window_2_np[key] = np.array(list_of_values)
            np.savez_compressed(
                    self.data_path / "adc_counter_loss_1.npz", 
                    **beam_loss_window_1_np
            )
            np.savez_compressed(
                    self.data_path / "adc_counter_loss_2.npz", 
                    **beam_loss_window_2_np
            )

            with open(self.data_path / "injections.txt", "w") as f:
                for value in self.injections_str:
                    f.write(value + "\n")

            temperatures_path = self.data_path / "temperatures"
            Path.mkdir(temperatures_path)
            for temperature_dict, save_file_name in zip(
                self.temperature_value_dicts, self.temperature_save_file_names
            ):
                with open(temperatures_path / save_file_name, "w") as f:
                    json.dump(temperature_dict, f)

            if self._measuring_SR_BPMs:
                sr_bpms_path = self.data_path / "BPMs" / "SR"
                Path.mkdir(sr_bpms_path, parents=True)
                self.sr_bpms.save_data(path=sr_bpms_path)

            if self._measuring_TBPMs:
                tbpms_path = self.data_path / "BPMs" / "TBPMs"
                Path.mkdir(tbpms_path, parents=True)
                self.tbpms.save_data(path=tbpms_path)

            if self._measuring_MX3_BPMs:
                mx3_bpms_path = self.data_path / "BPMs" / "MX3"
                Path.mkdir(mx3_bpms_path, parents=True)
                self.mx3_bpms.save_data(path=mx3_bpms_path)

        except Exception:
            self.logger.error(traceback.format_exc())

        self.logger.info("Data saved!")

        return None
    # -------------------------------------------------------------------------
    def plot_data(
        self,
    ) -> None:
        """
        Plots loss ratio between polarised and _depolarised bunches.
        Fits error function to sectors with compatible timing with BbB / FPM.

        Warning
        -------
        Only called when running [`start_experiment`][resdep.experiment.ResonantDepolarisation.start_experiment]
        from the command line. If running from a GUI, this function is ignored.
        """

        try:
            self.logger.info("Attempting to plot ratio data...")

            processed_data = ProcessedData(resdep=self)
            processed_data.calculate_ratio_loss()

            graph = StandaloneGraph()
            plotting = Plotter(
                resdep=self, processed_data=processed_data, graph=graph 
            ) 
            fitter = Fitter(resdep=self, processed_data=processed_data) 

            E0_mean, E0_mean_sigfig, fitted_beam_energy_string, error = (
                fitter.automagic_fit()
            )
            self.logger.info(fitted_beam_energy_string)
            plotting.plot_ratio_loss()
            plotting.plot_fits()
            graph.show()
            plt.savefig(
                self.data_path / "ratio_loss.png",
                dpi=300,
                bbox_inches="tight",
                facecolor="white",
                transparent=False,
            )

        except Exception:
            self.logger.error(traceback.format_exc())

        return None
    # *--------------------------------* #
    # *---------- PV callbacks --------* #
    # *--------------------------------* #
    # -------------------------------------------------------------------------
    def __on_value_change(self, pvname=None, value=None, host=None, **kws) -> None:
        """
        PV callback that listens for injections and changes `_injecting` state.
        Used to sleep around injections during experimnent loop.
        """
        # Cannot do .put() or .get() inside callback
        # It looks like .get() works but really I think it's simply getting  
        # PV.value which is cached.

        try:
            if not isinstance(value, int):
                raise TypeError(
                        "Gun trigger mode PV failed to return an int/enum"
            )
            mode = InjectionMode(value)
            if mode == InjectionMode.GUN_INJECTION:
                inj_time = datetime.datetime.now()
                inj_time_str = inj_time.strftime("%Y-%m-%d %H:%M:%S")
                self.injections.append(inj_time)
                self.injections_str.append(inj_time_str)

                self._injecting = True

        except Exception:
            self.logger.error(traceback.format_exc())

        return None
    # -------------------------------------------------------------------------
    def _on_wiggler_ramp(self, pvname=None, value=None, host=None, **kws) -> None:
        """
        PV callback that listens for any of the wiggler (bioSAXS, IMBL, ADS) 
        ramp status change. If so, something is ramping, and the diagnostic 
        should abort.
        """
        _is_wiggler_ramping: bool = False

        if value is None:
            self.logger.warning(
                    f"Wiggler {pvname} ramp status returned None. " 
                    +"Cannot determine ramp state."
            )
            return None

        pv_names: dict[str, str] = {
                "bioSAXS": "SR02SCU01:RAMP_STATUS",
                "IMBL": "SR08SCW01:FIELD_RAMPING_STATUS",
                "ADS": "SR10SCW01:RAMP_STATUS"
        }

        if pvname not in pv_names.values():
            self.logger.warning(
                f"Wiggler ramp callback connected to {pvname}, but "
                +"is not configured. See _on_wiggler_ramp definition in "
                +"experiment.py."
            )
            return None

        if pvname == pv_names["bioSAXS"]:
            status = bioSAXSRampStatus(int(value))
            if status == bioSAXSRampStatus.RAMPING:
                _is_wiggler_ramping = True

        elif pvname == pv_names["IMBL"]:
            status = IMBLRampStatus(int(value))
            if any([
                    status == IMBLRampStatus.RAMP_SYNC,
                    status == IMBLRampStatus.RAMP_TO_SYNC
                ]):
                _is_wiggler_ramping = True

        elif pvname == pv_names["ADS"]:
            status = ADSRampStatus(int(value))
            if status == ADSRampStatus.RAMPING:
                _is_wiggler_ramping = True

        need_to_abort: bool = any([
                self.state == State.INITIALISING,
                self.state == State.RUNNING
        ])
        if _is_wiggler_ramping and need_to_abort:
            self.logger.critical(
                "Detected the ramping of a wiggler field. Aborting scan." 
            )
            self.request_abort()

        return None
    # *--------------------------------* #
    # *---------- GUI Signals ---------* #
    # *--------------------------------* #
    # -------------------------------------------------------------------------
    def request_abort(
        self,
    ) -> None:
        """
        Changes the abort state to `True`, which will interrupt the experiment 
        loop on the next iteration.
        """
        self._abort_requested = True
        self.state = State.ABORTED
        if self.state_callback is not None:
            self.state_callback(state=self.state)
        return None
    # *--------------------------------* #
    # *----------- Utilities ----------* #
    # *--------------------------------* #
    # -------------------------------------------------------------------------
    def __interruptible_sleep(self, seconds: int) -> None:
        """
        Sleeps over long periods of time, waking often to check states 
        (for example: `abort`).

        Parameters
        ----------
        seconds: int
                Time to sleep in seconds
        """
        end = time.time() + seconds
        while time.time() < end:
            if self._abort_requested:
                return None
            time.sleep(0.01)

        return None

@dataclass
class ProcessedData:
    """
    Class for storing processed data generated by 
    [`resdep`][resdep.experiment.ResonantDepolarisation] and associated 
    [`_fitting`][resdep._fitting] and [`_plotting`][resdep._plotting] 
    helper classes.


    Attributes
    ----------
    freqs_array: npt.NDArray[np.floating]
        numpy array of the set frequencies during the experiment sweep.
        Often x-axis in plots and fitting.

    ratio_loss: dict[str, npt.NDArray[np.floating]]
        Ratio of the beam loss between the two ADC windows on the beam 
        loss monitors.
        Keys of the form `"{sector}{section}"`, e.g. `"4A"`
            
    mask: Union[npt.NDArray[np.bool_], "builtins.ellipsis"]
        Binary mask, used to constrain the fit to a certain frequency range.
        Value assigned in 
        [`automagic_fit`][resdep._fitting.Fitter.automagic_fit], and
        [`calculate_fitting_mask`][resdep._plotting.Plotter.calculate_fitting_mask].

    y_model: dict[str, npt.NDArray[np.float64]]
        y-axis data generated by the cumulative distribution function fit.
        See [`fit_error_functions`][resdep._fitting.Fitter.fit_error_functions].

    fitted_beam_energies: dict[str, float]
        The mean beam energy extracted from the fit to the loss on each sector.
        See [`fit_error_functions`][resdep._fitting.Fitter.fit_error_functions].

    fitted_beam_energy_stddevs: dict[str, float]
        The standard deviations of the above values.

    E0_mean: Union[float, None]
        Mean beam energy, derived from the average of the fits over all 
        sectors. See 
        [`calculate_fitted_energy_stats`][resdep._fitting.Fitter.calculate_fitted_energy_stats].

    E0_stddev: Union[float, None]
        Two standard deviations of the above value.

    E0_mean_sigfig, E0_stddev_sigfig: Union[float, None]
        The above two values formatted, so that the error is quoted to only 
        one significant figure, and the mean energy is quoted only to the 
        number of significant figures as the error allows.

    Note
    ----
    This Class is passed by reference when instancing the helper classes
    [fitter][resdep._fitting.Fitter] and 
    [plotter][resdep._plotting.Plotter].
    This is to pass the data between the different modules without having to 
    plotter each helper function to take in and return *many* args.

    """                                                         
    resdep: "ResonantDepolarisation"
    # defaults (if data is not passed on initialisation/instancing)
    sectors_to_fit: list[int] = field(
        default_factory=lambda: [1, 3, 8, 14]
    )
    freqs_array: npt.NDArray[np.floating] = field(default=np.array([]))
    ratio_loss: dict[str, npt.NDArray[np.floating]] = field(
        default_factory=dict[str, npt.NDArray]
    )
    # plotting
    mask: Union[npt.NDArray[np.bool_], "builtins.ellipsis"] = field(
        default=...
    )
    # fitting
    y_model: dict[str, npt.NDArray[np.float64]] = field(default_factory=dict)
    fitted_beam_energy_frequencies: dict[str, float] = field(
        default_factory=dict
    )
    fitted_beam_energies: dict[str, float] = field(default_factory=dict)
    fitted_beam_energy_stddevs: dict[str, float] = field(default_factory=dict)
    fit_results: str = field(default="")
    formatted_beam_energy: str = field(default="")
    _poor_fit: dict[str, bool] = field(default_factory=dict)
    # stats
    E0_mean: Optional[float] = field(default=None)
    E0_stddev: Optional[float] = field(default=None)
    E0_mean_sigfig: Optional[float] = field(default=None)
    E0_stddev_sigfig: Optional[float] = field(default=None)
    # -------------------------------------------------------------------------
    def calculate_ratio_loss(
            self,
            smoothing_mode: Literal["binning", "gaussian_filter"] = "binning",
            sigma: Optional[int] = None,
            ) -> None:
        """
        Calculates the ratio of the beam loss between the two ADC windows on 
        the beam loss monitors.

        Attributes
        ----------
        freqs_array: npt.NDArray[np.floating]
            numpy array of the set frequencies during the experiment sweep.
            X-axis in plots and fitting.
        ratio_loss: dict[str, npt.NDArray[np.floating]]
            Ratio of the beam loss between the two ADC windows on the BLMs.
            Keys of the form `"{sector}{section}"`, e.g. `"4A"`

        """         
        window = 1000 # num args of frequency
        # compensate for settings outside standard operation:
        # - kicker amp = 50%
        # - sweep rate = 5 Hz/s
        try:
            window = int(
                    1000 / (self.resdep.sweep_rate/5)
            )
        except NameError: # if resdep attributes not loaded
            pass

        self.freqs_array: npt.NDArray = np.array(self.resdep.set_freqs)
        self.beam_loss_window_1: dict[str, list[float]] = (
            self.resdep.beam_loss_window_1.copy()
        )  
        self.beam_loss_window_2: dict[str, list[float]] = (
                self.resdep.beam_loss_window_2.copy()
        )

        # --- account for desynchronisation during aquisition
        # (different data lengths due to readback timing)
        # list all lengths
        lengths: list[int] = []
        len_data: int = len(self.freqs_array)
        lengths.append(len_data)
        for sector in self.sectors_to_fit:
            key: str = f"{sector:02d}B"
            try:
                lengths.append(len(self.beam_loss_window_1[key]))
                lengths.append(len(self.beam_loss_window_2[key]))
            except KeyError:  # if a paticular sector to fit is OOS
                continue 
        # check if any lengths are different
        if min(lengths) != max(lengths):
            # shorten all vectors to the minimum length
            min_length = min(lengths)
            self.freqs_array = self.freqs_array[0:min_length]
            for sector in self.sectors_to_fit:
                key: str = f"{sector:02d}B"
                try:
                    self.beam_loss_window_1[key] = self.beam_loss_window_1[
                        key
                    ][0:min_length]
                    self.beam_loss_window_2[key] = self.beam_loss_window_2[
                        key
                    ][0:min_length]
                except KeyError:  # if a paticular sector to fit is OOS
                    continue  

        # Calculate beam loss ratio between the two windows
        for sector in self.sectors_to_fit:
            try:
                key: str = f"{sector}B"
                window_1: npt.NDArray = np.array(self.beam_loss_window_1[key])
                window_2: npt.NDArray = np.array(self.beam_loss_window_2[key])
                self.ratio_loss[key] = np.divide(
                        window_1, # numerator
                        window_2, # divisor
                        out=np.ones_like(window_1), # fallback value if false
                        where=window_2 > 0 # true condition
                )
            except KeyError:  # if a paticular sector to fit is OOS
                continue 

        for sector in self.sectors_to_fit:
            try:
                key: str = f"{sector}B"
                if smoothing_mode == "binning":
                    if window % 2 == 0:  # is even
                        window += 1
                    padding: int = ceil(window / 2)
                    number_of_bins: int = len(self.ratio_loss[key]) - padding
                    binned_ratio_loss: npt.NDArray = self.ratio_loss[key].copy()
                    for step in range(number_of_bins):
                        bin_centre: int = window//2 + step
                        start: int = step
                        end: int = start + window
                        binned_ratio_loss[bin_centre] = np.mean(
                            self.ratio_loss[key][start:end]
                        )
                    # pad 
                    binned_ratio_loss[:padding] = binned_ratio_loss[window // 2]
                    binned_ratio_loss[-padding:] = binned_ratio_loss[
                        -window//2 - 1
                    ]
                    self.ratio_loss[key] = binned_ratio_loss
                elif smoothing_mode == "gaussian_filter":
                    if sigma is None:
                        sigma = 10
                    self.ratio_loss[key] = gaussian_filter1d(
                        self.ratio_loss[key], sigma
                    )
                else: 
                    raise ValueError(
                            "smoothing mode must be one of:\n"
                            + "1. binning (default), or "
                            + "2. gaussian_filter."
                    )
                # set zero
                self.ratio_loss[key] += -np.min(self.ratio_loss[key])
                # normalise
                maximum: np.floating = self.ratio_loss[key].max()
                self.ratio_loss[key] = np.divide(
                        self.ratio_loss[key],
                        maximum,
                        out=np.zeros_like(self.ratio_loss[key]),
                        where=maximum != 0
                )

            except KeyError:  # if a paticular sector to fit is OOS
                continue  

        return None

    # -------------------------------------------------------------------------
    def save_data(
        self,
    ) -> None:
        """
        Saves fitting results and data to 
        [`data_path`][resdep.experiment.ResonantDepolarisation.data_path]
        """
        path = self.resdep.data_path / "processed_data"
        Path.mkdir(path)

        np.savez_compressed(path / "freqs_array.npz", self.freqs_array)
        # loss
        np.savez_compressed(path / "ratio_loss.npz", **self.ratio_loss)
        # fit
        np.savez_compressed(path / "fit.npz", **self.y_model)

        # fit results
        self.fit_results += f"\n{self.formatted_beam_energy}"
        with open(path / "fit_results.txt", "w") as f:
            f.write(self.fit_results)

        # stats
        stats: dict[str, Union[float, None]] = {
            "E0_mean": self.E0_mean,
            "E0_stddev": self.E0_stddev,
            "E0_mean_sigfig": self.E0_mean_sigfig,
            "E0_stddev_sigfig": self.E0_stddev_sigfig,
        }
        with open(path / "fit_stats.json", "w") as f:
            json.dump(stats, f)

        self.resdep.logger.info("Processed data saved!")

        return None


if __name__ == "__main__":
    print(
        "resdep.py contains a class file ResonantDepolarisation which ideally "
        + "should be instanced in a top-level script and not directly run."
    )
    response = input("Do you want to run it directly? (y/n): ")

    if response == "y":
        resdep = ResonantDepolarisation()
        response = input("Use default settings? (y/n): ")

        if response == "y":
            print("#--- input experiment settings ---#")
            resdep.set_kicker_amp = float(
                input("Kicker amplitude (% as decimal, 0->1): \n")
            )
            resdep.harmonic = int(input("Harmonic (int): \n"))
            resdep.bounds = float(
                input("Energy Bounds (% as decimal, typically 0.0005): \n")
            )
            requested_sweep_direction = input(
                "Sweep direction (forward or backward, literal str (dont use quotes)): \n"
            ).lower()
            resdep.set_sweep_direction = SweepDirection[requested_sweep_direction]
            resdep.sweep_rate = float(input("Sweep rate (0.5 -- 10 Hz/s): \n"))
            resdep.sweep_step_size = float(
                input("Sweep step size (lower limit = 0.5 Hz): \n")
            )

        resdep.start_experiment()
