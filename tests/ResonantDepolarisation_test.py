import pytest
import epics
import datetime
import logging
from typing import Union, overload

from resdep.experiment import ResonantDepolarisation

class MockPV():
    """
    Mock epics.pv.PV class that is returned from epics.pv.get_pv()
    """
    def __init__(
            self, 
            get_values: Union[int, float, str, list[float]] = 0
        ):
        """
        Parameters
        ----------
        get_values: int | float | str | list[float]
            Value to return on .get() call
        """
        self.get_values = get_values
        if isinstance(get_values, list):
            self.value = get_values[0]
        else:
            self.value = get_values
        
        self.get_call_index = 0

        self.connected = True
        self.put_complete = True

        return None

    def get(self, timeout, *args, **kwargs):
        self.get_call_index += 1
        if isinstance(self.get_values, list):
            self.value = self.get_values[self.get_call_index]

        return self.value
    
    def put(self, value, *args, **kwargs):
        self.value = value
        return None

class MockBLMs():
    """
    Mock beam loss monitor(s)
    """
    loss_PV: dict[str, MockPV] = {"mock_PV": MockPV()}
    adc_counter_loss_1_PV: dict[str, MockPV] = {"mock_PV": MockPV()}
    adc_counter_loss_2_PV: dict[str, MockPV] = {"mock_PV": MockPV()}

@pytest.fixture
def mock_get_pv(*args, **kwargs):
    """
    Mock get_pv() method of epics.pv class
    """
    return MockPV()


@pytest.fixture
def resdep_with_passing_log_data():
    """
    ResonantDepolarisation configured with PVs that will nicely pass through 
    ResonantDepolarisation._log_data(), not throw an error or an abort request.
    """
    resdep = ResonantDepolarisation()
    # pvs
    setattr(resdep, "sweep_freq_act_PV", MockPV(get_values=1225))
    setattr(resdep, "sweep_freq_PV", MockPV(get_values=1225))
    setattr(resdep, "sweep_span_PV", MockPV(get_values=0))
    setattr(resdep, "sweep_period_PV", MockPV(get_values=0))
    setattr(resdep, "pattern_PV", MockPV(get_values="1:360"))
    setattr(resdep, "dcct", MockPV(get_values=200))
    setattr(resdep, "blm", MockBLMs())
    # experiment variables
    setattr(resdep, "log_frequency", 1) # Hz
    setattr(resdep, "set_sweep_freq", 1225)
    setattr(resdep, "set_sweep_span", 0)
    setattr(resdep, "set_sweep_period", 0)
    setattr(resdep, "set_drive_pattern", "1:360")
    # loop variables
    setattr(resdep, "set_sweep_freq", 1225)
    # states
    setattr(resdep, "_abort_requested", False)
    setattr(resdep, "_measuring_SR_BPMs", False)
    setattr(resdep, "_measuring_TBPMs", False)
    setattr(resdep, "_measuring_MX3_BPMs", False)
    # callbacks
    setattr(resdep, "status_callback", logging.info)
    # save objects
    freqs: list[float] = []
    set_freqs: list[float] = []
    current: list[Union[float, None]] = []
    timestamps: list[datetime.datetime] = []
    formatted_timestamps: list[str] = []
    beam_loss_window_1: dict[str, list[float]] = {}
    beam_loss_window_2: dict[str, list[float]] = {}
    for key in resdep.blm.loss_PV:
        beam_loss_window_1[key] = []
        beam_loss_window_2[key] = []
    setattr(resdep, "timestamps", timestamps)
    setattr(resdep, "formatted_timestamps", formatted_timestamps)
    setattr(resdep, "set_freqs", set_freqs)
    setattr(resdep, "freqs", freqs)
    setattr(resdep, "current", current)
    setattr(resdep, "beam_loss_window_1", beam_loss_window_1)

    return resdep

def test_log_data(resdep_with_passing_log_data):
    # arrange
    resdep = resdep_with_passing_log_data
    # act
    resdep._log_data()

    # assert
    print(f"freqs len={len(resdep.freqs)}")
    assert len(resdep.freqs) == 1

def test_collect_baseline_data(resdep_with_passing_log_data):
    # arrange
    resdep = resdep_with_passing_log_data
    # act
    resdep._collect_baseline_data(duration_seconds=10)

    assert len(resdep.freqs) > 0


