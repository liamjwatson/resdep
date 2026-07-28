from typing import Any
from resdep._archiver import bioSAXSRampStatus, IMBLRampStatus, ADSRampStatus, check_recent_wiggler_ramp
import requests
import pytest

from resdep.experiment import ResonantDepolarisation

# arrange
pv_names: dict[str, str] = {
        "bioSAXS": "SR02SCU01:RAMP_STATUS",
        "IMBL": "SR08SCW01:FIELD_RAMPING_STATUS",
        "ADS": "SR10SCW01:RAMP_STATUS"
}
# -------------------- PV CALLBACK ------------------------
# experiment.py

@pytest.fixture
def resdep() -> ResonantDepolarisation:
    return ResonantDepolarisation()

def test_PV_callback_garbage_name_and_value(resdep):
    # arrange + act
    resdep._on_wiggler_ramp(
            pvname="garbage",
            value=5
    )
    # assert
    assert resdep._abort_requested == False


# arrange
@pytest.fixture(
        params = [
            pytest.param(bioSAXSRampStatus.UNKNOWN, id="unknown"),
            pytest.param(bioSAXSRampStatus.READY, id="ready"),
            pytest.param(bioSAXSRampStatus.INTERLOCKED, id="interlocked")
        ]
)
def bioSAXS_status_not_ramping(request):
    return request.param

def test_PV_callback_bioSAXS_NOT_ramping(resdep, bioSAXS_status_not_ramping):
    # act
    resdep._on_wiggler_ramp(
            pvname="SR02SCU01:RAMP_STATUS",
            value=bioSAXS_status_not_ramping.value
    )
    # assert
    assert resdep._abort_requested == False

def test_PV_callback_bioSAXS_IS_ramping(resdep):
    # act + arrange
    resdep._on_wiggler_ramp(
            pvname="SR02SCU01:RAMP_STATUS",
            value=bioSAXSRampStatus.RAMPING.value
    )
    # assert
    assert resdep._abort_requested == True

# arrange
@pytest.mark.parametrize(
        "status_not_ramping",
        [
            pytest.param(IMBLRampStatus.UNKNOWN, id="unknown"),
            pytest.param(IMBLRampStatus.RAMP_STOPPED, id="ramp_stopped"),
            pytest.param(IMBLRampStatus.RAMP_PAUSED, id="ramp_paused"),
            pytest.param(IMBLRampStatus.RAMP_ERROR, id="ramp_error"),
            pytest.param(IMBLRampStatus.RAMP_END, id="ramp_end"),
        ]
)

def test_PV_callback_IMBL_NOT_ramping(resdep, status_not_ramping):
    # act
    resdep._on_wiggler_ramp(
            pvname="SR08SCW01:FIELD_RAMPING_STATUS",
            value=status_not_ramping.value
    )
    # assert
    assert resdep._abort_requested == False

@pytest.mark.parametrize(
        "status_is_ramping",
        [
            pytest.param(IMBLRampStatus.RAMP_SYNC, id="ramp_sync"),
            pytest.param(IMBLRampStatus.RAMP_TO_SYNC, id="ramp_to_sync"),
        ]
)

def test_PV_callback_IMBL_IS_ramping(resdep, status_is_ramping):
    # act + arrange
    resdep._on_wiggler_ramp(
            pvname="SR08SCW01:FIELD_RAMPING_STATUS",
            value=status_is_ramping.value
    )
    # assert
    assert resdep._abort_requested == True

# arrange
@pytest.mark.parametrize(
        "status_not_ramping",
        [
            pytest.param(ADSRampStatus.UNKNOWN, id="unknown"),
            pytest.param(ADSRampStatus.READY, id="ready"),
            pytest.param(ADSRampStatus.RSD_INTERLOCKED, id="rsd_interlocked"),
            pytest.param(ADSRampStatus.SOFT_INTERLOCKED, id="soft_interlocked")
        ]
)

def test_PV_callback_ADS_NOT_ramping(resdep, status_not_ramping):
    # act
    resdep._on_wiggler_ramp(
            pvname="SR10SCW01:RAMP_STATUS",
            value=status_not_ramping.value
    )
    # assert
    assert resdep._abort_requested == False

def test_PV_callback_ADS_IS_ramping(resdep):
    # act + arrange
    resdep._on_wiggler_ramp(
            pvname="SR10SCW01:RAMP_STATUS",
            value=ADSRampStatus.RAMPING.value
    )
    # assert
    assert resdep._abort_requested == True

# -------------------- CHECK RECENT RAMP ------------------------
# _archiver.py

# arrange
@pytest.mark.parametrize(
        ("status", "expected"),
        [
            (bioSAXSRampStatus.UNKNOWN, False),
            (bioSAXSRampStatus.READY, False),
            (bioSAXSRampStatus.RAMPING, True),
            (bioSAXSRampStatus.INTERLOCKED, False)
        ]
)

# arrange

def test_check_recent_bioSAXS_ramp(monkeypatch, status, expected):

    class MockResponse:
        """
        Mock requests.Response class returned from requests.get
        """
        @staticmethod
        def json():
            mock_data: list[dict[str, Any]] = [
                    {"val": status.value}
            ]
            mock_response_struct: list[dict[str, list[dict[str, Any]]]] = [
                    {"data" : mock_data}
            ]
            return mock_response_struct


    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    # act
    verdict = check_recent_wiggler_ramp()

    # assert
    assert verdict == expected

# arrange
@pytest.mark.parametrize(
        ("status", "expected"),
        [
            (IMBLRampStatus.UNKNOWN, False),
            (IMBLRampStatus.RAMP_STOPPED, False),
            (IMBLRampStatus.RAMP_PAUSED, False),
            (IMBLRampStatus.RAMP_ERROR, False),
            (IMBLRampStatus.RAMP_END, False),
            (IMBLRampStatus.RAMP_SYNC, True),
            (IMBLRampStatus.RAMP_TO_SYNC, True),
        ]
)


def test_check_recent_IMBL_ramp(monkeypatch, status, expected):


    def mock_get(url, *args, **kwargs):
        class MockResponse:
            """
            Mock requests.Response class returned from requests.get
            """
            @staticmethod
            def json():
                if pv_names["bioSAXS"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": bioSAXSRampStatus.READY.value}
                    ]
                elif pv_names["IMBL"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": status.value}
                    ]
                elif pv_names["ADS"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": ADSRampStatus.READY.value}
                    ]
                mock_response_struct: list[dict[str, list[dict[str, Any]]]] = [
                        {"data" : mock_data}
                ]
                return mock_response_struct
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    # act
    verdict = check_recent_wiggler_ramp()

    # assert
    assert verdict == expected

# arrange
@pytest.mark.parametrize(
        ("status", "expected"),
        [
            (ADSRampStatus.UNKNOWN, False),
            (ADSRampStatus.READY, False),
            (ADSRampStatus.RAMPING, True),
            (ADSRampStatus.RSD_INTERLOCKED, False),
            (ADSRampStatus.SOFT_INTERLOCKED, False)
        ]
)


def test_check_recent_ADS_ramp(monkeypatch, status, expected):


    def mock_get(url, *args, **kwargs):
        class MockResponse:
            """
            Mock requests.Response class returned from requests.get
            """
            @staticmethod
            def json():
                if pv_names["bioSAXS"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": bioSAXSRampStatus.READY.value}
                    ]
                elif pv_names["IMBL"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": IMBLRampStatus.RAMP_END.value}
                    ]
                elif pv_names["ADS"] in url:
                    mock_data: list[dict[str, Any]] = [
                            {"val": status.value}
                    ]
                mock_response_struct: list[dict[str, list[dict[str, Any]]]] = [
                        {"data" : mock_data}
                ]
                return mock_response_struct
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    # act
    verdict = check_recent_wiggler_ramp()

    # assert
    assert verdict == expected
