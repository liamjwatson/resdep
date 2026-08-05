#!/usr/bin/env python3
import epics
import time
from typing import Union, Optional, Protocol, runtime_checkable, Literal
from enum import IntEnum
import numpy as np
import numpy.typing as npt
import threading

import devsup.db
import devsup.hooks
import devsup.util

from resdep._record_access import RecordAccess
from resdep.experiment import (
        ResonantDepolarisation,
        State,
        ScanType,
)

class BeamMode(IntEnum):
    SHUT_DOWN = 1
    MAINTENANCE = 2
    MACHINE_STUDIES = 3
    USER_BEAM_DECAY = 8
    USER_BEAM_TOP_UP = 9
    USER_BEAM_EXOTIC = 10

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
    BEAM_NOT_POLARISED = 6

@runtime_checkable
class IocApiContract(Protocol):
    """
    Contract to check IocApi class against. Similart to JS interface
    """
    def exec_run_experiment(): ...
    def exec_abort_experiment(): ...
    def emit_progress(self, step: int, max_steps: int): ...
    def emit_state(self, state: State): ...
    def emit_results(
        self, 
        E0_mean_sigfig: Optional[float],
        E0_stddev_sigfig: Optional[float], 
        formatted_beam_energy: str, 
        error: Optional[str]
        ): ...

class IocApi(devsup.util.StoppableThread):
    """
    State machine to run on IOC and manage ResonantDepolarisation() control. 
    """

    def __init__(self) -> None:
        """
        Initiate local PV records. Instance ResonantDepolarisation class.
        """
        super(IocApi, self).__init__()

        self.resdep = ResonantDepolarisation(
                progress_callback=self.emit_progress,
                results_callback=self.emit_results,
                state_callback=self.emit_state,
        )

        # generate record access PVs
        PREFIX: str = "SR00RDP01"
        # ---------------------------------------------- Control
        self.run_cmd_PV = RecordAccess(
                f"{PREFIX}:RUN_CMD"
        ) # Enum
        self.abort_cmd_PV = RecordAccess(
                f"{PREFIX}:ABORT_CMD"
        ) # Enum
        self.scan_type_CMD = RecordAccess(
                f"{PREFIX}:SCAN_TYPE_CMD"
        ) # Enum

        # ---------------------------------------------- Feedback

        # ----- Results
        self.beam_energy_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY"
        ) # float (GeV)
        self.beam_energy_twostd_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY_TWOSTD"
        ) # float (GeV)
        self.beam_energy_formatted_PV = RecordAccess(
                f"{PREFIX}:BEAM_ENERGY_FORMATTED"
        ) # str (E GeV +- error keV)
        self.progress_PV = RecordAccess(
                f"{PREFIX}:PROGRESS"
        ) # int (%)
        self.estimated_polarisation_PV = RecordAccess(
                f"{PREFIX}:ESTIMATED_POLARISATION"
        ) # float (%)

        # ---- Diagnostics
        self.state_PV = RecordAccess(
                f"{PREFIX}:STATE"
        ) # Enum
        self.error_msg_PV = RecordAccess(
                f"{PREFIX}:ERROR_MSG"
        ) # str
        self.run_inhibit_status_PV = RecordAccess(
                f"{PREFIX}:RUN_INHIBIT_STATUS"
        ) # Enum

        # connect to machine state PVs
        self.beam_mode_PV: epics.pv.PV = epics.pv.get_pv(
            pvname="FS01:BEAM_MODE_MONITOR", connect=True, timeout=1
        )
        self.current_history_24h_PV: epics.pv.PV = epics.pv.get_pv(
            pvname="SR11BCM01:24HR_CURRENT_HISTORY", connect=True, timeout=1
        )

        # Default values
        self.run_cmd_PV.value = RunCMD.NONE
        self.abort_cmd_PV.value = AbortCMD.NONE
        
        self.progress_PV.value = 0
        self.estimated_polarisation_PV.value = 100 # %

        self.state_PV.value = State.READY
        self.error_msg_PV.value = "None"
        self.run_inhibit_status_PV.value = RunInhibitState.ABLE_TO_RUN

        devsup.hooks.addHook("AfterIocRunning", self.start)
        devsup.hooks.addHook("AfterIocExit", self.join)

    def run(self) -> None:
        """
        State machine, checking for run/abort commands and experiment status.
        """

        while self.shouldRun():
            # listen for callbacks
            if self.abort_cmd_PV.value == AbortCMD.ABORT:
                self.exec_abort_experiment()
            if self.run_cmd_PV.value == RunCMD.RUN:
                self.exec_run_experiment()
            if self.state_PV.value == State.FINISHED:
                self.exec_finished_experiment()
            
            self.sleep(1)

    def exec_abort_experiment(self) -> None:
        """
        Sends abort request to experiment thread.
        """
        self.abort_cmd_PV.value == AbortCMD.NONE
        self.resdep.request_abort()
        self.state_PV.value == State.ABORTED

        return None
        
    def exec_run_experiment(self) -> None:
        """
        Tries to run experiment if all checks pass.
        Checks commands are appropriate (Scan type etc).
        Checks machine state (User beam mode, enough current etc)
        """

        self.run_cmd_PV.value = RunCMD.NONE
        if self.state_PV.value != State.READY:
            return None
        if self.scan_type_CMD.value == ScanType.NONE:
            self.error_msg_PV.value = "No scan type selected."
            return None
            
        able_to_run, error = self._check_able_to_run(
                scan_type=self.scan_type_CMD.value
        )
        if not able_to_run:
            self.error_msg_PV.value = error
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

    def exec_finished_experiment(self) -> None:
        """
        Cleanup tasks on experiment finish.
        
        To be added
        -----------
        - Coundown timer to next automatic scan
        - Polarisation update every 1 Hz
        """
        # reset state
        self.state_PV.value = State.READY

        # Set progress bar to 100%
        # This is to ensure it visually reads done even when aborted
        # mid experiment
        self.emit_progress(step=100, max_steps=100)
        
        # start automatic timer... needs implementation
        # start polarisation calc
        
        return None

    def _check_able_to_run(
        self, 
        scan_type: ScanType
        ) -> tuple[bool, Optional[str]]:
        """
        Check if the experiment can run based on the state of the Tron.

        Parameters
        ----------
        scan_type: ScanType (enum)
            Automatic scans require the beam mode: "User Beam", 
            while manual scans do not.

        Returns
        -------
        verdict: bool
            Answer to whether the experiment can run

        error: str
            Error message for why (specifically or first offending requirement) 
            the experiment cannot run.
            Displayed on the results panel.
        
        Requirements
        ------------
        1. More that 150 mA of beam current
        2. At least 95% beam polarisation
            1. Considers both time since recent injection 
                and last diagnostic scan
        3. Must be in "User Beam" if automatic scans are enabled
        """                 
        verdict: bool = False
        error: Optional[str] = None

        formatted_beam_modes: str = ""
        for mode in BeamMode:
            formatted_beam_modes += (
                    f"{mode.name} = {mode.value}\n"
            )

        # If not connected/disconnected:
        # give PVs a chance to reconnect before state check logic
        for pv in [self.beam_mode_PV, self.current_history_24h_PV]:
            if not pv.connected:
                pv.connect(timeout=1)
                time.sleep(1)
            # if still not connected, fail
            if not pv.connected:
                self.run_inhibit_status_PV.value = (
                        RunInhibitState.PVS_NOT_CONNECTED
                )
                error = (
                    f"{pv} refused to connect. Cannot determine machine state."
                )
                verdict = False
                return verdict, error

        beam_mode_response: Union[int, None] = (
                self.beam_mode_PV.get(timeout=0.1)
        )
        current_history_24h: Union[
                np.ndarray[tuple[Literal[2880]], np.dtype[np.float64]], None
            ] = self.current_history_24h_PV.get(timeout=0.1)
        time.sleep(0.5)

        # if PVs return None, exit early
        if beam_mode_response is not None:
            beam_mode = BeamMode(beam_mode_response)
        else:
            error = (
                "beam_mode (FS01:BEAM_MODE_MONITOR) returned None." 
                + "Expected any of:\n" 
                + formatted_beam_modes
                + "Aborting request to run resdep."
            )
            verdict = False
            return verdict, error

        if current_history_24h is None:
            error = (
                "24h current hisotry PV (DCCT) returned None.\n" 
                + "Aborting request to run resdep."
            )
            verdict = False
            return verdict, error

        # <---------- Currently not checking wiggler ramp in the archiver 
        # try:
        #     recent_wiggler_ramp: bool = check_recent_wiggler_ramp()
        #     if recent_wiggler_ramp:
        #         error = (
        #                 "Wiggler ramp initiated in the 40 minutes. "
        #                 +"Require more time to repolarise / stabilise."
        #         )
        #         verdict = False
        #         return verdict, error
        # except Exception:
        #     self.logger.error(traceback.format_exc())
        #     error = (
        #             "Unable to check if there was a recent wiggler ramp. "
        #             +"This is probably due to an issue with the archiver. "
        #             +"Check the GUI log (/asp/usr/data/resdep/GUI_log) "
        #             +"for more info."
        #     )
        #     verdict = False
        #     return verdict, error

        is_user_beam: bool = any([
                beam_mode == BeamMode.USER_BEAM_DECAY,
                beam_mode == BeamMode.USER_BEAM_TOP_UP,
                beam_mode == BeamMode.USER_BEAM_EXOTIC
        ])

        if scan_type == ScanType.AUTOMATIC:
            scan_type_allowed: bool = is_user_beam
        elif scan_type == ScanType.NORMAL or scan_type == ScanType.WIDE:
            scan_type_allowed: bool = True # manual scans can run anytime

        # ignore statement here because cant type hint array size / shape
        beam_current: np.float64 = current_history_24h[:-1] #ty: ignore[invalid-assignment]
        if beam_current < 150: # mA
            self.run_inhibit_status_PV.value = (
                    RunInhibitState.NOT_ENOUGH_CURRENT
            )
            error = f"Beam current ({beam_current} mA) is too low (< 150 mA). "
            verdict = False
            return verdict, error

        TIME_STEP_SECONDS: int = 30
        index_40min: int = 40*60//TIME_STEP_SECONDS
        current_history_40min: npt.NDArray[np.float64] = (
                current_history_24h[-index_40min:] 
        )
        if any(current_history_40min < 150):# mA
            self.run_inhibit_status_PV.value = (
                    RunInhibitState.RECENT_BEAM_INJECTION
            )
            error = "Recent beam injection (or low current) detected. "
            verdict = False
            return verdict, error
        else:
            recent_beam_injection: bool = False

        if all([
                scan_type_allowed,
                not recent_beam_injection,
                self.estimated_polarisation_PV.value >= 95, # %
            ]):
            self.run_inhibit_status_PV.value = RunInhibitState.ABLE_TO_RUN
            verdict = True
        elif self.estimated_polarisation_PV.value < 95: # %
            error = (
                "Beam polarisation is less than 95%; not enough resolution. "
                + "Aborting request to run resdep."
            )
            self.run_inhibit_status_PV.value = (
                    RunInhibitState.BEAM_NOT_POLARISED
            )
            verdict = False
            return verdict, error
        elif all([
                scan_type == ScanType.AUTOMATIC,
                not is_user_beam,
            ]):  # tried automatic scan but not user beam
            self.run_inhibit_status_PV = RunInhibitState.NOT_USER_BEAM
            error = ("beam_mode (FS01:BEAM_MODE_MONITOR) returned " 
                     + f"{beam_mode.name}. " 
                     + "Expected any form of 'User Beam'. " 
                     + "Aborting request to run resdep.")
            verdict = False
            return verdict, error


        return verdict, error

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

    def emit_state(self, state: State) -> None:
        self.state_PV.value = state
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


if __name__ == "__main__":
    if not isinstance(IocApi, IocApiContract):
        raise NotImplementedError(
                "IocApi does not adhere to IocApiContract. "
                +"Ensure architecture matches protocol in ioc_api.py"
        )
    # run api
    ioc_api = IocApi()

