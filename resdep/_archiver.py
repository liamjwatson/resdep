#!/usr/bin/env python3
"""
Handles and exports data from the PV archiver appliance

Info
----
Adapted from [`pytrendGUI.chanarc_export`](https://bitbucket.synchrotron.org.au/projects/ACC/repos/pytrendgui/browse/chanarc_export.py)
by Paul Bennetto. Simpler version for just accessing a few known (reliable) PVs.
"""
"""
 █████╗ ██████╗  ██████╗██╗  ██╗██╗██╗   ██╗███████╗██████╗ 
██╔══██╗██╔══██╗██╔════╝██║  ██║██║██║   ██║██╔════╝██╔══██╗
███████║██████╔╝██║     ███████║██║██║   ██║█████╗  ██████╔╝
██╔══██║██╔══██╗██║     ██╔══██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗
██║  ██║██║  ██║╚██████╗██║  ██║██║ ╚████╔╝ ███████╗██║  ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
"""                     
from typing import Any, Union
from enum import IntEnum
import logging
import datetime
import requests

class bioSAXSRampStatus(IntEnum):
    UNKNOWN = 0
    READY = 1
    RAMPING = 2
    INTERLOCKED = 3

class IMBLRampStatus(IntEnum):
    UNKNOWN = 0
    RAMP_STOPPED = 1
    RAMP_PAUSED = 2
    RAMP_ERROR = 3
    RAMP_END = 4
    RAMP_SYNC = 5
    RAMP_TO_SYNC = 6

class ADSRampStatus(IntEnum):
    UNKNOWN = 0
    READY = 1
    RAMPING = 2
    RSD_INTERLOCKED = 3
    SOFT_INTERLOCKED = 4

def convert_datetime_to_ISO_format(start_time, end_time) -> tuple[str, ...]:
    """
    Convert normal datetime with timezone (TZ) info to ISO format for archiver 
    request.
    """
    now: datetime.datetime = datetime.datetime.now()
    utc_offset: Union[datetime.timedelta, None] = now.astimezone().utcoffset()
    if utc_offset is None:
        raise TypeError(
            "Could not detect system timezone. "
            "Required for utc formatted requests to PV archiver appliance."
        )

    start_time_utc: datetime.datetime = start_time - utc_offset
    end_time_utc: datetime.datetime = end_time - utc_offset

    start_time_iso: str = start_time_utc.isoformat()
    end_time_iso: str = end_time_utc.isoformat()

    return start_time_iso, end_time_iso

def check_recent_beam_injection() -> bool:
    """
    Pulls beam current from the archiver. Checks if beam has been injected 
    within the last 39 minutes (any current < 150 mA).

    Returns
    -------
    verdict: bool
        If beam has been injected recently, returns `True`.
        If we've held > 150 mA for the last 39 minutes, return `False`.
    """                 
    verdict = True

    archiver_affix: str = "cr01arc04:17668/retrieval/data"
    pvname: str = "SR11BCM01:CURRENT_MONITOR"

    now: datetime.datetime = datetime.datetime.now()
    start_time: datetime.datetime = (
            now - datetime.timedelta(minutes=39)
    )
    end_time = now

    start_time_iso, end_time_iso = convert_datetime_to_ISO_format(
            start_time, end_time
    )

    request: str = (
        f"http://{archiver_affix}/getData.json?"
        + f"pv={pvname}&from={start_time_iso}Z&to={end_time_iso}Z"
    )
    response: requests.models.Response = requests.get(request, timeout=10)
    data: list[dict[str, Any]] = response.json()[0]["data"]

    # have to populate current in loop as each data point is an individual 
    # entry with associated metadata (timestamp etc), not a contiguous list 
    # of values
    current: list[float] = []
    for index in range(len(data)):
        current.append(data[index]["val"])

    # find less than 150
    current_less_than_150mA: list[bool] = [i < 150 for i in current]  # noqa: E741
    if any(current_less_than_150mA):
        verdict = True
    else:
        verdict = False

    return verdict

def check_recent_wiggler_ramp() -> bool:
    """
    Checks the archiver for INITIATION of a field ramp of the bioSAXS, IMBL or 
    ADS wigglers.
    Can't just check the most recent timestamp of the last PV value for 
    ramp status as ADSRampStatus reports frequently for some reason (even if 
    the status hasn't actually changed).
    Can't be sensitive to "READY" status as an indication of RAMP END for this 
    reason, and therefore we can only detect when the ramp starts.

    Returns
    -------
    verdict: bool
        True if any field change detected.
    """             
    verdict = True

    archiver_affix: str = "cr01arc04:17668/retrieval/data"
    pv_names: dict[str, str] = {
            "bioSAXS": "SR02SCU01:RAMP_STATUS",
            "IMBL": "SR08SCW01:FIELD_RAMPING_STATUS",
            "ADS": "SR10SCW01:RAMP_STATUS"
    }

    now: datetime.datetime = datetime.datetime.now()
    start_time: datetime.datetime = (
            now - datetime.timedelta(minutes=39)
    )
    end_time = now

    start_time_iso, end_time_iso = convert_datetime_to_ISO_format(
            start_time, end_time
    )

    for wiggler, pv_name in pv_names.items():

        request: str = (
            f"http://{archiver_affix}/getData.json?"
            + f"pv={pv_name}&from={start_time_iso}Z&to={end_time_iso}Z"
        )
        response: requests.models.Response = requests.get(request, timeout=10)
        data: list[dict[str, Any]] = response.json()[0]["data"]

        if len(data) == 0:
            continue

        if wiggler == "bioSAXS":
            ramp_status: list[bioSAXSRampStatus] = []
            for index in range(len(data)):
                ramp_status.append(
                        bioSAXSRampStatus(int(data[index]["val"]))
                )
            for status in ramp_status:
                if status == bioSAXSRampStatus.RAMPING:
                    logging.warning(f"Wiggler {wiggler} ramp detected!")
                    verdict = True
                    return verdict

        elif wiggler == "IMBL":
            ramp_status: list[IMBLRampStatus] = []
            for index in range(len(data)):
                ramp_status.append(
                        IMBLRampStatus(int(data[index]["val"]))
                )
            for status in ramp_status:
                in_ramp_cycle: list[bool] = [
                        status == IMBLRampStatus.RAMP_SYNC,
                        status == IMBLRampStatus.RAMP_TO_SYNC,
                ]
                if any(in_ramp_cycle):
                    logging.warning(f"Wiggler {wiggler} ramp detected!")
                    verdict = True
                    return verdict

        elif wiggler == "ADS":
            ramp_status: list[ADSRampStatus] = []
            for index in range(len(data)):
                ramp_status.append(
                        ADSRampStatus(int(data[index]["val"]))
                )
            for status in ramp_status:
                if status == ADSRampStatus.RAMPING:
                    logging.warning(f"Wiggler {wiggler} ramp detected!")
                    verdict = True
                    return verdict

        else:
            raise KeyError(
                    f"Wiggler {wiggler} is not configured to be checked for "
                    +"recent ramp."
            )
            
    verdict = False

    return verdict

if __name__ == "__main__":
    print(
        "archiver.py contains functions for pulling PV data from the archiver."
    )
    print(
        "Use help(archiver) or help(resdep.archiver) for help,", 
        "depending on your import."
    )
    response = input(
        "Do you want to check for a recent beam injection? (y/n):\n"
    )
    if response == "y":
        verdict = check_recent_beam_injection()
        if verdict:
            print(
                "Beam has been injected in the last 40 minutes.",
                "Beam is likely not fully polarised."
            )
        else:
            print("No recent injection detected.")
