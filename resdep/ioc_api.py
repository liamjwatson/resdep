#!/usr/bin/env python3
from typing import Optional
from enum import IntEnum
import threading

import devsup.db
import devsup.hooks
import devsup.util

from resdep._record_access import RecordAccess
from resdep.experiment import (
        ResonantDepolarisation,
        ScanType,
)

class State(IntEnum):
    READY = 0
    ABORTED = 1
    INITIALISING = 2
    RUNNING = 3

class RunCMD(IntEnum):
    NONE = 0
    RUN = 1

class AbortCMD(IntEnum):
    NONE = 0
    ABORT = 1

class RunInhibitState(IntEnum):
    ABLE_TO_RUN = 0
    PVS_NOT_CONNECTED = 1
    NOT_USER_BEAM = 2
    NOT_ENOUGH_CURRENT = 3
    RECENT_WIGGLER_RAMP = 4
    RECENT_BEAM_INJECTION = 5

class IocApi(devsup.util.StoppableThread):
    """
    State machine to run on IOC and manage ResonantDepolarisation() control. 
    """

    def __init__(self) -> None:
        super(IocApi, self).__init__()

        # init states
        self._abort_requested: bool = False

        devsup.hooks.addHook("AfterIocRunning", self.start)
        devsup.hooks.addHook("AfterIocExit", self.join)

    def run(self) -> None:
        """
        Threaded application loop (process)
        """

        while self.shouldRun():
            # listen for callbacks
            if self.abort_cmd_PV.value == AbortCMD.ABORT:
                self.exec_abort_experiment()
            if self.run_cmd_PV.value == RunCMD.RUN:
                self.exec_run_experiment()
            
            self.sleep(1)

    def exec_init(self) -> None:
        """
        Initiate local PV records. Instance ResonantDepolarisation class.
        """
        self.resdep = ResonantDepolarisation()

        PREFIX: str = "SR00RDP01"

        # ---------------------------------------------- Control
        self.run_cmd_PV = RecordAccess(
                f"{PREFIX}:RUN_CMD"
        )
        self.abort_cmd_PV = RecordAccess(
                f"{PREFIX}:ABORT_CMD"
        )
        self.scan_type_CMD = RecordAccess(
                f"{PREFIX}:SCAN_TYPE_CMD"
        )

        # ---------------------------------------------- Feedback

        # ----- Results
        self.beam_energy_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY"
        )
        self.beam_energy_twostd_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY_TWOSTD"
        )
        self.beam_energy_formatted_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY_FORMATTED"
        )
        self.progress_PV = RecordAccess(
                f"{PREFIX}:PROGRESS"
        )

        # ---- Diagnostics
        self.state_PV = RecordAccess(
                f"{PREFIX}:STATE"
        )
        self.error_msg_PV = RecordAccess(
                f"{PREFIX}:ERROR_MSG"
        )
        self.run_inhibit_status_PV = RecordAccess(
                f"{PREFIX}:RUN_INHIBIT_STATUS"
        )
        
        return None

    def exec_abort_experiment(self) -> None:

        self.abort_cmd_PV.value == AbortCMD.NONE
        self.resdep.request_abort()
        self.state_PV.value == State.ABORTED

        return None
        
    def exec_run_experiment(self) -> None:

        self.run_cmd_PV.value = RunCMD.NONE
        if self.state_PV.value != State.READY:
            return None
        self.apply_scan_settings(
                scan_type=self.scan_type_CMD.value
        )
        self.experiment_thread = threading.Thread(
                target=self.resdep.start_experiment
        )
        self.experiment_thread.start()
        self.state_PV.value == State.INITIALISING

        return None

    def apply_scan_settings(self, scan_type: ScanType) -> None:
        """
        Configure the initial settings based on the passed scan type.

        Parameters
        ----------
        scan_type: ScanType (enum)
            One of `ScanType.AUTOMATIC`, `.NORMAL`, or `.WIDE`.
        """
        if scan_type == ScanType.NONE:
            return None
        if scan_type == ScanType.AUTOMATIC or scan_type == ScanType.NORMAL:
            self.resdep.bounds = 0.05 / 100  # input %, output decimal
            self.resdep.sweep_rate = 5  # Hz/s
        elif scan_type == ScanType.WIDE:
            self.resdep.bounds = 0.35 / 100  # 2 hour scan
            self.resdep.sweep_rate = 10  # Hz/s
        else:
            raise ValueError(
                    f"scan_type should be one of {ScanType.__members__}"
            )

    # ---------------------------------------- ResonantDepolarisation Callbacks
    def emit_progress(self, step: int, max_steps: int) -> None:
        experiment_progress: int = 100 * step//max_steps
        self.progress_PV.value = experiment_progress
        return None

    def emit_results(
        self, 
        E0_mean_sigfig: Optional[float],
        E0_stddev_sigfig: Optional[float], 
        formatted_beam_energy: str, 
        error: Optional[str]
        ) -> None:
        
        if error is not None:
            self.error_msg_PV.value = error
            return None

        self.beam_energy_PV.value = E0_mean_sigfig
        self.beam_energy_twostd_PV.value = E0_stddev_sigfig
        self.beam_energy_formatted_PV.value = formatted_beam_energy

        return None
