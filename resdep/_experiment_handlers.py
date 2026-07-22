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

from typing import Literal, Protocol, runtime_checkable
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path

from PySide6.QtCore import QObject, Signal, SignalInstance

from resdep.experiment import ResonantDepolarisation
from resdep import simpleGUI

class HostType(Enum):
    LOCAL = "local"
    REMOTE = "remote"

@runtime_checkable
class SupportsStatusSignal(Protocol):
    status: SignalInstance  # status: message
@runtime_checkable
class SupportsPlotSignal(Protocol):
    new_plot_info: SignalInstance
@runtime_checkable
class SupportsDataPathSignal(Protocol):
    data_path: SignalInstance
@runtime_checkable
class SupportsStartTimerSignal(Protocol):
    start_timer: SignalInstance
@runtime_checkable
class SupportsADCWindowsSignal(Protocol):
    ADC_windows: SignalInstance  # ADC windows, depolarised bunches

class ExperimentHandler(ABC, QObject):
    """
    Experiment handler iterface. 
    Contains particular attributes and callbacks for GUI functionality.
    """
    progress = Signal(int, int)  # current step, max steps
    results = Signal(str, str) # formatted_beam_energy (results), error
    finished = Signal() 

    def __init__(self) -> None:
        pass

    @abstractmethod
    def run(self):...

    @abstractmethod
    def abort(self):...

    @abstractmethod
    def emit_progress(self, step: int, max_steps: int):...
        
    @abstractmethod
    def emit_results(self, formatted_beam_energy: str, error: str):...

class LocalQtDecorator(ExperimentHandler):
    """
    Qt wrapper for resonant depolarisation.
    Defines emitted signals and attaches them to the worker.
    The worker must contain these callbacks to emit signals.
    """
    new_plot_info = Signal(list, dict, dict)
    status = Signal(str)  # status: message
    data_path = Signal(Path)
    start_timer = Signal()
    ADC_windows = Signal(list, str)  # ADC windows, depolarised bunches
    #--------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self.worker = ResonantDepolarisation()
        self.worker.progress_callback = self.emit_progress
        self.worker.status_callback = self.emit_status
        self.worker.data_path_callback = self.emit_data_path
        self.worker.results_callback = self.emit_results

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
    #--------------------------------------------------------------------------
    def emit_progress(self, step: int, max_steps: int) -> None:
        self.progress.emit(step, max_steps)
        return None
    #--------------------------------------------------------------------------
    def emit_results(
        self, formatted_beam_energy: str, error: str
    ) -> None:
        self.results.emit(formatted_beam_energy, error)
        return None
    #--------------------------------------------------------------------------
    def emit_new_plot_info(
        self,
        freqs: list[float],
        beam_loss_window_1: dict[str, list[float]],
        beam_loss_window_2: dict[str, list[float]],
    ) -> None:
        self.new_plot_info.emit(freqs, beam_loss_window_1, beam_loss_window_2)
        return None
    #--------------------------------------------------------------------------
    def emit_status(self, message: str) -> None:
        self.status.emit(message)
        return None
    #--------------------------------------------------------------------------
    def emit_data_path(self, data_path: Path) -> None:
        self.data_path.emit(data_path)
        return None
    #--------------------------------------------------------------------------
    def emit_start_timer(
        self,
    ) -> None:
        self.start_timer.emit()
        return None
    #--------------------------------------------------------------------------
    def emit_new_ADC_windows(
        self, ADC_windows: list[int], depolarised_bunches: str
    ) -> None:
        self.ADC_windows.emit(ADC_windows, depolarised_bunches)
        return None

class IOCInterface(ExperimentHandler):
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

    def emit_progress(self, step: int, max_steps: int) -> None:
        # something like
        # progress = some_pv_defined_in_init.get()
        # self.emit_progress(*progress)
        pass 
    
    def emit_results(
        self, formatted_beam_energy: str, error: str
    ) -> None:
        # get some PV values
        # Possibly cast error enum 
        # emit to GUI
        pass


class ExperimentHandlerFactory():
    handler_types: dict[HostType, ExperimentHandler] = {
            HostType.LOCAL: LocalQtDecorator(),
            HostType.REMOTE: IOCInterface(),
    }

    @staticmethod
    def create_handler(host_type: HostType):
        handler = ExperimentHandlerFactory.handler_types.get(host_type)
        if handler is None:
            raise ValueError(
                    f"host_type {host_type} is not one of:\n "
                    f"{ExperimentHandlerFactory.handler_types.keys()}"
            )
        return handler
    
class ExperimentGuiBinder():
    @staticmethod
    def bind(
        handler: ExperimentHandler,
        gui: "simpleGUI.MainWindow"
    ) -> None:
        """ 
        Binds additional singals in concrete ExperimentHandler subclass 
        implementations to appropriately configured Slots in the GUI.
        Binding only occurs if the slot exists, the ExperimentHandler 
        satisfies a specific protocol (contract), and there is an appropriate 
        Slot in the GUI.

        1. Steps to add a new Signal (e.g. colour):

            ```py title=_experiment_handlers.py
                class ColourfulExperimentHandler(ExperimentHandler):
                    colour = Signal(str) # <------------------------ New signal
                    def __init__(self):
                    ...
                    def get_experiment_colour():
                        # logic
                        experiment_colour: str = ...
                        # send colour to GUI
                        self.colour.emit(experiment_colour)# <- emit new signal
            ```

        2. Define new protocol (contract):

            ```py title=_experiment_handlers.py
                class SupportsColorSignal(Protocol):
                    colour: SignalInstance
            ```

        3. Define Slot in GUI that recieves new Signal

            ```py title=simpleGUI.py
                class MainWindow(QWidget):
                    ...
                    @Slot
                    def _on_color(color: str):
                        # update the GUI, for example:
                        self.color_label.setText(color)
            ```

        4. Configure ExperimentGuiBinder (this class) to bind Signal to Slot:

            ```py title=_experiment_handlers.py
                class ExperimentGuiBinder():
                    ...
                    # check handler against Protocol (contract)
                    if isinstance(handler, SupportsColorSignal):
                        handler.color.connect(
                            gui._on_color
                        )
            ```

        """                                             
        # Connect default signals and slots
        handler.progress.connect(gui._on_progress_update)
        handler.results.connect(gui._on_results)
        handler.finished.connect(gui._on_finish)

        # Optional signals
        if isinstance(handler, SupportsStatusSignal):
            handler.status.connect(gui._on_status_update)

        if isinstance(handler, SupportsDataPathSignal):
            handler.data_path.connect(gui._on_data_path_update)
