import pytest

from resdep._experiment_handlers import (
        ExperimentHandlerContract,
        LocalQtDecorator,
        IOCInterface,
        ExperimentHandlerFactory,
        ExperimentGuiBinder,
        SupportsStatusSignal,
        SupportsPlotSignal,
        SupportsDataPathSignal,
        SupportsStartTimerSignal,
        SupportsADCWindowsSignal
)
import resdep.simpleGUI as simpleGUI


@pytest.fixture(
    params = [
        pytest.param(LocalQtDecorator, id="local_qt"),
        pytest.param(IOCInterface, id="ioc")
    ]
)

def handler(request):
    return request.param


def test_handlers_obeys_contract(handler):
    # assert
    assert isinstance(handler(), ExperimentHandlerContract)

def test_handlers_bind_to_simpleGUI(handler):
    experiment_handler=handler() 
    gui = simpleGUI.MainWindow(
            experiment_handler=experiment_handler
    )
    ExperimentGuiBinder.bind(
            handler=experiment_handler,
            gui=gui
    )
    assert gui.experiment_handler == experiment_handler
