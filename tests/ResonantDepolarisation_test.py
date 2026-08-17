import itertools
import pytest
import epics
import datetime
import logging
import numpy as np
import numpy.typing as npt
from pathlib import Path
from typing import Union, overload, Callable

from resdep.experiment import ResonantDepolarisation
from resdep.epicsBLMs import BLMs, DefaultT2TriggerDelays

class MockPV():
    """
    Mock epics.pv.PV class that is returned from epics.pv.get_pv()
    """
    def __init__(
            self, 
            pvname = None,
            callback = None,
            get_values: Union[int, float, str, list[float], npt.NDArray] = 1,
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

        self.pvname = pvname
        self.connected = True
        self.put_complete = True

        self.callback = callback

        return None

    def get(self, timeout, *args, **kwargs):
        self.get_call_index += 1
        if isinstance(self.get_values, list):
            self.value = self.get_values[self.get_call_index]

        return self.value
    
    def put(self, value, *args, **kwargs):
        self.value = value
        return None

    def add_callback(self, callback: Callable, *args, **kwargs):
        self.callback = callback

    def clear_callbacks(self, *args, **kwargs):
        self.callback = None

class MockBLMs():
    """
    Mock beam loss monitor(s)
    """
    def __init__(self):
        # states
        self.sectors_connected = [sector for sector in range(14)]

    def get_loss_PVs(self):
        # PV
        self.loss_PV: dict[str, MockPV] = {"mock_PV": MockPV()}
        self.adc_counter_loss_1_PV: dict[str, MockPV] = {"mock_PV": MockPV()}
        self.adc_counter_loss_2_PV: dict[str, MockPV] = {"mock_PV": MockPV()}

        integrated_buffer_loss: np.ndarray = np.ones(86)
        # create empty buckets
        integrated_buffer_loss[-7:] = 0
        self.integrated_buffer_loss_PV: dict[str, MockPV] = {}
        for sector, section in itertools.product(range(1, 14+1, 1), ["A", "B"]):
            self.integrated_buffer_loss_PV[f"{sector}{section}"] = ( 
                MockPV(get_values=integrated_buffer_loss)
            )

    def get_t2_trigger_delays(self):
        default_t2_trigger_delays: list[int] = [
                delay.value for delay in DefaultT2TriggerDelays
        ]
        self.t2_trigger_delays_PV: dict[str, MockPV] = {}
        self.init_t2_trigger_delays: dict[str, float] = {}

        for index, sector in enumerate(range(1, 14+1, 1)):
            delay = default_t2_trigger_delays[index]
            self.t2_trigger_delays_PV[f"{sector}"] = MockPV(get_values=delay)
            self.init_t2_trigger_delays[f"{sector}"] = delay
            


@pytest.fixture
def mock_pv(monkeypatch):
    def mock_get_pv(pvname = None, callback = None, *args, **kwargs):
        """
        Mock get_pv() method of epics.pv class
        """
        return MockPV(
                pvname=pvname,
                callback=callback
        )
    monkeypatch.setattr(epics.pv, "get_pv", mock_get_pv)

@pytest.fixture
def resdep_cls():
    return ResonantDepolarisation()

@pytest.fixture
def mock_resdep(resdep_cls):
    """
    ResonantDepolarisation configured with PVs that will nicely pass through 
    ResonantDepolarisation._log_data(), not throw an error or an abort request.
    """
    # -------------------------------------------------------------------- PVs
    setattr(resdep_cls, "sweep_freq_act_PV", MockPV(get_values=1225)) # kHz
    setattr(resdep_cls, "sweep_freq_PV", MockPV(get_values=1225)) # kHz
    setattr(resdep_cls, "sweep_span_PV", MockPV(get_values=0))
    setattr(resdep_cls, "sweep_period_PV", MockPV(get_values=0))
    setattr(resdep_cls, "masterRF_PV", MockPV(get_values=499682224)) # Hz
    setattr(resdep_cls, "pattern_PV", MockPV(get_values="1:360"))
    setattr(resdep_cls, "dcct", MockPV(get_values=200)) # mA
    setattr(resdep_cls, "blm", MockBLMs())
    resdep_cls.blm.get_loss_PVs()
    # --------------------------------------------------- experiment variables
    setattr(resdep_cls, "log_frequency", 1) # Hz
    setattr(resdep_cls, "set_sweep_freq", 1225) # kHz
    setattr(resdep_cls, "set_sweep_span", 0)
    setattr(resdep_cls, "set_sweep_period", 0)
    setattr(resdep_cls, "set_drive_pattern", "1:360")
    setattr(resdep_cls, "f_rev", 1.38799e3) # kHz
    # --------------------------------------------------------- loop variables
    setattr(resdep_cls, "set_sweep_freq", 1225)
    # ----------------------------------------------------------------- states
    setattr(resdep_cls, "_abort_requested", False)
    setattr(resdep_cls, "_measuring_SR_BPMs", False)
    setattr(resdep_cls, "_measuring_TBPMs", False)
    setattr(resdep_cls, "_measuring_MX3_BPMs", False)
    # -------------------------------------------------------------- callbacks
    setattr(resdep_cls, "status_callback", logging.info)
    # ----------------------------------------------------------- save objects
    freqs: list[float] = []
    set_freqs: list[float] = []
    current: list[Union[float, None]] = []
    timestamps: list[datetime.datetime] = []
    formatted_timestamps: list[str] = []
    beam_loss_window_1: dict[str, list[float]] = {}
    beam_loss_window_2: dict[str, list[float]] = {}
    for key in resdep_cls.blm.loss_PV:
        beam_loss_window_1[key] = []
        beam_loss_window_2[key] = []
    setattr(resdep_cls, "timestamps", timestamps)
    setattr(resdep_cls, "formatted_timestamps", formatted_timestamps)
    setattr(resdep_cls, "set_freqs", set_freqs)
    setattr(resdep_cls, "freqs", freqs)
    setattr(resdep_cls, "current", current)
    setattr(resdep_cls, "beam_loss_window_1", beam_loss_window_1)

    return resdep_cls

def test_config_data_path(resdep_cls):
    # arrange
    # act
    resdep_cls._config_data_path()

    # assert
    assert resdep_cls.data_path.exists() == True
    assert resdep_cls.data_path.is_dir() == True

# ---- This test needs extra config, since we load the PV in the function
# ---- Needs a custom PV class with a pvname flag for masterRF
# def test_calc_revolution_frequency_from_master_RF(
#         mock_resdep
#     ):
#     # arange
#     resdep = mock_resdep
#     f_rev_expected: float = (
#         1e-3 * resdep.masterRF_PV.value / 360
#     )
#     f_rev_default: float = resdep.f_rev
# 
#     # act
#     resdep._calc_revolution_frequency_from_master_RF()
#     f_rev_calculated: float = resdep.f_rev
# 
#     # assert
#     assert f_rev_calculated != f_rev_default
#     assert f_rev_calculated == f_rev_expected

def test_load_PVs(
        mock_pv,
        mock_resdep
    ):
    """
    Smoke test for now (no assertions, just making sure it throws no 
    errors.
    Should improve when I understand more about pytest implementation.
    """
    # arange
    resdep = mock_resdep 
    # monkeypatch.setattr(resdep.epicsBLMs, "BLMs", MockBLMs)

    # act
    resdep._load_PVs()

    # assert -> None. Does act throw errors?

def test_calculate_adc_counter_windows(
        monkeypatch,
        mock_pv,
        mock_resdep
        ):
    """
    Force test to look at sector 1, and only populate those attributes.
    """
    # arange
    resdep = mock_resdep
    resdep.blm.init_sumdec_periods = {
        "1": 50
    }
    TIME_ALIGNMENT_PV_NAMES: list[str] = [
            "IGPF:X:SRAM:MEAN",
            "IGPF:Y:SRAM:MEAN",
            "SR01BLM01:signals:adc_integrated.B",
            "SR01BLM01:triggers:t2:delay_sp",
    ]

    def mock_get_pv_with_time_alignment(
            pvname = None, callback = None, *args, **kwargs
        ):
        """
        Mock get_pv() method of epics.pv class
        """
        get_values = 1 # default
        data = 1 # default
        if pvname in TIME_ALIGNMENT_PV_NAMES:
            if any([
                pvname == "IGPF:X:SRAM:MEAN", 
                pvname == "IGPF:Y:SRAM:MEAN"
            ]):
                # create fake fill pattern
                # x & y are the same
                data = np.ones(
                        shape=360,
                        dtype=np.float32
                )
                EMPTY_BUCKETS_START = 100
                EMPTY_BUCKETS_END = 160
                data[EMPTY_BUCKETS_START:EMPTY_BUCKETS_END] = 0
            if pvname == "SR01BLM01:signals:adc_integrated.B":
                # create fake integrated loss / fill pattern
                SUM_DEC = 86
                data = np.ones(
                        shape=SUM_DEC,
                        dtype=np.int32
                )
                N_EMPTY_ADC_CYCLES = 60/360 * SUM_DEC
                EMPTY_ADC_CYCLES_START = 5
                EMPTY_ADC_CYCLES_END = (
                        EMPTY_ADC_CYCLES_START + N_EMPTY_ADC_CYCLES
                )
                data[EMPTY_ADC_CYCLES_START:EMPTY_ADC_CYCLES_END] = 0
            if pvname == "SR01BLM01:triggers:t2:delay_sp":
                data = DefaultT2TriggerDelays.SECTOR_1 # 11 adc cycles
                
            get_values = data

        mock_pv = MockPV(
                pvname=pvname,
                callback=callback,
                get_values=get_values
        )
        return mock_pv

    monkeypatch.setattr(epics.pv, "get_pv", mock_get_pv_with_time_alignment)

    resdep.blm.get_loss_PVs()

    resdep.blm.get_t2_trigger_delays()

    # act 
    resdep.calculate_adc_counter_windows(sector = 1)

    # assert
    assert resdep.set_drive_pattern == "11:308"
    assert resdep.set_adc_counter_offset_1 == 0
    assert resdep.set_adc_counter_window_1 == 71
    assert resdep.set_adc_counter_offset_2 == 71
    assert resdep.set_adc_counter_window_2 == 15
    

def test_log_data(mock_resdep):
    # arrange
    resdep = mock_resdep
    # act
    resdep._log_data()

    # assert
    print(f"freqs len={len(resdep.freqs)}")
    assert len(resdep.freqs) == 1

def test_collect_baseline_data(mock_resdep):
    # arrange
    resdep = mock_resdep
    # act
    resdep._collect_baseline_data(duration_seconds=3)

    assert len(resdep.freqs) > 0


