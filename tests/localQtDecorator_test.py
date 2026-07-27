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
from resdep.experiment import ScanType

@pytest.fixture
def local_qt_decorator():
    return LocalQtDecorator()

@pytest.mark.parametrize(
    "local_qt_decorator_supported_signal",
    [
        pytest.param(SupportsStatusSignal, id="status"),
        pytest.param(SupportsDataPathSignal, id="data_path"),
    ]
)

def test_handler_supports_additional_signals(
    local_qt_decorator, 
    local_qt_decorator_supported_signal
    ):
    # assert
    assert isinstance(local_qt_decorator, local_qt_decorator_supported_signal)

def test_handler_requests_abort(local_qt_decorator):
    local_qt_decorator.abort()

    assert local_qt_decorator.resdep._abort_requested == True

@pytest.mark.parametrize(
        "scan_type",
        [
            pytest.param(ScanType.AUTOMATIC, id="automatic"),
            pytest.param(ScanType.NORMAL, id="normal"),
            pytest.param(ScanType.WIDE, id="wide"),
        ]
)

def test_handler_applies_scan_settings(
        local_qt_decorator,
        scan_type
    ):
    local_qt_decorator.apply_scan_settings(scan_type)
    if scan_type == ScanType.AUTOMATIC or scan_type == ScanType.NORMAL:
        assert local_qt_decorator.resdep.bounds == 0.05 / 100  # input %, output decimal
        assert local_qt_decorator.resdep.sweep_rate == 5  # Hz/s
    else: # if scan_type == ScanType.WIDE:
        assert local_qt_decorator.resdep.bounds == 0.35 / 100  # 2 hour scan
        assert local_qt_decorator.resdep.sweep_rate == 10  # Hz/s

