"""
Define experiment handler interface (abstract base class) for GUI.
This way, we can pass an experiment handler class that is either a locally 
running ResonantDepolarisation() process, or it is a call to an IOC somewhere 
that communicates with PV states instead of local attributes and callbacks.
Either way, each experiment handler should emit appropriate signals to the GUI.
And of course, should be able to run() and abort().

Type of handler that is passed to GUI is handled by Factory.
Decision should be environment based. e.g. 
if __name__ == "__main__":
    host_type="local"
or something a little more elegant.
"""             

from typing import Literal
from abc import ABC, abstractmethod
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from resdep.experiment import ResonantDepolarisation


class ExperimentHandler(ABC):
    """
    Experiment handler iterface. 
    Contains particular attributes and callbacks for GUI functionality.
    """
    progress = Signal(int, int)  # current step, max steps
    new_plot_info = Signal(list, dict, dict)
    status = Signal(str)  # status: message
    data_path = Signal(Path)
    start_timer = Signal()
    ADC_windows = Signal(list, str)  # ADC windows, depolarised bunches
    results = Signal(str, str) # formatted_beam_energy (results), error
    finished = Signal() 

    def __init__(self) -> None:
        pass

    @abstractmethod
    def run(self):...

    @abstractmethod
    def abort(self):...

    #--------------------------------------------------------------------------
    def _emit_progress(self, step: int, max_steps: int) -> None:
        self.progress.emit(step, max_steps)
        return None
    #--------------------------------------------------------------------------
    def _emit_new_plot_info(
        self,
        freqs: list[float],
        beam_loss_window_1: dict[str, list[float]],
        beam_loss_window_2: dict[str, list[float]],
    ) -> None:
        self.new_plot_info.emit(freqs, beam_loss_window_1, beam_loss_window_2)
        return None
    #--------------------------------------------------------------------------
    def _emit_status(self, message: str) -> None:
        self.status.emit(message)
        return None
    #--------------------------------------------------------------------------
    def _emit_data_path(self, data_path: Path) -> None:
        self.data_path.emit(data_path)
        return None
    #--------------------------------------------------------------------------
    def _emit_start_timer(
        self,
    ) -> None:
        self.start_timer.emit()
        return None
    #--------------------------------------------------------------------------
    def _emit_new_ADC_windows(
        self, ADC_windows: list[int], depolarised_bunches: str
    ) -> None:
        self.ADC_windows.emit(ADC_windows, depolarised_bunches)
        return None
    #--------------------------------------------------------------------------
    def _emit_results(
        self, formatted_beam_energy: str, error: str
    ) -> None:
        self.results.emit(formatted_beam_energy, error)
        return None

class LocalQtDecorator(ExperimentHandler, QObject):
    """
    Qt wrapper for resonant depolarisation.
    Defines emitted signals and attaches them to the worker.
    The worker must contain these callbacks to emit signals.
    """

    #--------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self.worker = ResonantDepolarisation()
        self.worker.__progress_callback = self._emit_progress
        self.worker.__status_callback = self._emit_status
        self.worker.__data_path_callback = self._emit_data_path
        self.worker.__results_callback = self._emit_results

        return None
    #--------------------------------------------------------------------------
    def run(
        self,
    ) -> None:
        try:
            self.worker.start_experiment()
        finally:
            self.finished.emit()
        return None
    #--------------------------------------------------------------------------
    def abort(
        self,
    ) -> None:
        self.worker.request_abort()
        return None

class IOCInterface(ExperimentHandler, QObject):
    """
    Communication interface between Qt GUI and IOC running resdep
    """

    def __init__(self) -> None:
        super().__init__()

        self._connect()
        return None

    def _connect(self):
        # connect to IOC through... socket? EpicsPVs?
        try:
            #connecting
            pass
        except ConnectionRefusedError:
            # handling
            pass
        pass

    def _reconnect(self):
        # when connection drops, retry
        pass

    def run(self):
        # something like, send_cmd("run")
        pass

    def abort(self):
        # something like, send_cmd("abort")
        pass

    def _update_progress(self) -> None:
        # something like
        # progress = some_pv_defined_in_init.get()
        # self._emit_progress(*progress)
        pass 

class ExperimentHandlerFactory():
    handler_types: dict[str, type[ExperimentHandler]] = {
            "local": LocalQtDecorator,
            "remote": IOCInterface
    }

    @staticmethod
    def create_handler(host_type: Literal["local", "remote"]):
        handler = ExperimentHandlerFactory.handler_types.get(host_type)
        if handler is None:
            raise ValueError(
                    f"host_type {host_type} is not one of:\n "
                    f"{ExperimentHandlerFactory.handler_types.keys()}"
            )
        return handler
    
