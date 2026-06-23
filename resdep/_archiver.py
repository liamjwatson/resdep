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
import datetime
import requests


def check_recent_beam_injection() -> bool:
    """
    Pulls beam current from the archiver. Checks if beam has been injected within the last 39 minutes (any current < 150 mA).

    Returns
    -------
    verdict: bool
        If beam has been injected recently, returns `True`.
        If we've held > 150 mA for the last 39 minutes, return `False`.
    """
    verdict = False

    # archiver time request must be in iso and utc format
    now: datetime.datetime = datetime.datetime.now()
    utc_offset: Union[datetime.timedelta, None] = now.astimezone().utcoffset()
    if utc_offset is None:
        raise TypeError(
            "Could not detect system timezone. "
            "Required for utc formatted requests to PV archiver appliance."
        )

    archiver_affix: str = "cr01arc04:17668/retrieval/data"
    pvname: str = "SR11BCM01:CURRENT_MONITOR"
    start_time: datetime.datetime = (
        now - datetime.timedelta(minutes=39) - utc_offset
    )
    end_time: datetime.datetime = now - utc_offset

    start_time_iso: str = start_time.isoformat()
    end_time_iso: str = end_time.isoformat()

    request: str = (
        f"http://{archiver_affix}/getData.json?"
        + f"pv={pvname}&from={start_time_iso}Z&to={end_time_iso}Z"
    )
    response: requests.models.Response = requests.get(request)
    data: list[dict[str, Any]] = response.json()[0]["data"]

    current: list[float] = []
    for index in range(len(data)):
        current.append(data[index]["val"])

    # find less than 150
    current_less_than_150mA: list[bool] = [i < 150 for i in current]  # noqa: E741
    if any(current_less_than_150mA):
        verdict = True

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
