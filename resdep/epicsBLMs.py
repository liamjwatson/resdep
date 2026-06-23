"""
Classes for beam loss monitors (BLMs)
"""

"""
██████╗ ███████╗ █████╗ ███╗   ███╗    ██╗      ██████╗ ███████╗███████╗
██╔══██╗██╔════╝██╔══██╗████╗ ████║    ██║     ██╔═══██╗██╔════╝██╔════╝
██████╔╝█████╗  ███████║██╔████╔██║    ██║     ██║   ██║███████╗███████╗
██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║    ██║     ██║   ██║╚════██║╚════██║
██████╔╝███████╗██║  ██║██║ ╚═╝ ██║    ███████╗╚██████╔╝███████║███████║
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝    ╚══════╝ ╚═════╝ ╚══════╝╚══════╝
███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ ███████╗
████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝
██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝███████╗
██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗╚════██║
██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║███████║
╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
"""

from typing import Any, Union, Literal
import logging
import traceback
import datetime
import json
import warnings
import epics
import time
import os
from pathlib import Path


class BLMs:
    """
    A libera object which handles EPICS BLM PVs, values, states, and common functions.
    *e.g.* get PVs, get initial values, restore defaults

    Examples
    --------
    ```py title="General usage"
    blm = BLMs()

    # get PVs
    blm.get_loss_PVs()
    blm.get_decimation()

    # put settings
    blm.apply_full_decimation()
    blm.apply_adc_counter_masks(
        offset_1=0
        window_1=30
        offset_2=30
        window_2=56
    )

    # readback data
    loss = []
    for i in range(60):
        loss.append(blm.adc_counter_loss_1["11"].get(timeout=0.1))
        time.sleep(1)

    plt.plot(sector_11_loss)
    ```

    ```py title="Fail-safe way to restore initial settings/values"
    try:
        blm.get_adc_counter_masks() # <--- automatically calls get_init_adc_counter_masks()
        # do something
    except ...
    finally:
        blm.restore_inits(mode="adc_counter_masks")
    ```
    """

    def __init__(
        self,
    ):
        # --- wait time between PV calls / assignments to not flood system
        self._WAIT_TIME: float = 0.1
        self.check_for_OOS()

    # ----------------------------------------------------------------------------------------------------------
    def check_for_OOS(
        self,
    ) -> None:
        """Checks which BLMs (which sectors) are out-of-service (OOS); ignores those PVs (no connect, get, put).

        Attributes
        -------
        sectors_connected: list[str]
            sectors in service
        sectors_OOS: list[str]
            sectors out-of-service

        Raises
        ------
        ConnectionRefusedError
            If all BLMs are disconnected or out-of-service.
        """
        self.sectors_connected: list[int] = []
        self.sectors_OOS: list[int] = []

        for sector in range(1, 14 + 1, 1):
            # status list: 0: Unknown, 1: Ok, 2: No reply, 3: Invalid
            box_status_monitor_PV = epics.pv.get_pv(
                f"SR{sector:02d}IOC91:BOX_STATUS_MONITOR",
                connect=True,
                timeout=0.1,
            )
            box_status = box_status_monitor_PV.get(timeout=0.1)
            time.sleep(self._WAIT_TIME)
            if box_status == 1:  # <-- Ok
                self.sectors_connected.append(sector)
            else:
                self.sectors_OOS.append(sector)
                logging.warning(
                    f"Sector {sector} BLM OUT-OF-SERVICE! "
                    + "Ignoring associated PVs."
                )

        if len(self.sectors_connected) == 0:
            raise ConnectionRefusedError(
                "All BLMs disconnected / out-of-service."
            )

        logging.debug(f"In service sectors: {self.sectors_connected}")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_loss_PVs(
        self,
    ) -> None:
        """
        Loads all loss PVs (regular slow acquisition [SA] and loss from the two ADC counter masks)
        from all sectors and returns dictionaries (of PVs).

        Attributes
        ----------
        loss_PV: dict[str, Any]
            Slow acquisition loss PVs
        adc_counter_loss_1_PV, adc_counter_loss_2_PV: dict[str, Any]
            Slow acquisition loss PV on counter stream 1/2
        integrated_buffer_loss_PV: dict[str, Any]
            Integrated turn by turn loss PV.
            Outputs `SUM_DEC=86` points which correspond to one full revolution

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}{section}"`.
        *e.g.* `"11A"`
        """

        logging.info("Grabbing loss PVs...")

        self.loss_PV: dict[str, Any] = {}
        self.adc_counter_loss_1_PV: dict[str, Any] = {}
        self.adc_counter_loss_2_PV: dict[str, Any] = {}
        self.integrated_buffer_loss_PV: dict[str, Any] = {}

        # grab PVs in loop
        for sector in self.sectors_connected:
            for section in ["A", "B"]:
                self.loss_PV[f"{sector}{section}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BLM01:SIGNALS_SA_{section}_MONITOR",
                    connect=True,
                    timeout=0.1,
                )
                self.adc_counter_loss_1_PV[f"{sector}{section}"] = (
                    epics.pv.get_pv(
                        f"SR{sector:02d}BLM01:signals:counter.{section}1",
                        connect=True,
                        timeout=0.1,
                    )
                )
                self.adc_counter_loss_2_PV[f"{sector}{section}"] = (
                    epics.pv.get_pv(
                        f"SR{sector:02d}BLM01:signals:counter.{section}2",
                        connect=True,
                        timeout=0.1,
                    )
                )
                self.integrated_buffer_loss_PV[f"{sector}{section}"] = (
                    epics.pv.get_pv(
                        f"SR{sector:02d}BLM01:signals:adc_integrated.{section}",
                        connect=True,
                        timeout=0.1,
                    )
                )

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_adc_counter_mask_PVs(
        self,
    ) -> None:
        """
        Loads all adc counter masks (offset + window -- 1 & 2) PVs from all sectors.
        Also loads `counting_mode` and `threshold_count_diff`.

        Attributes
        ----------
        adc_counter_offset_1_PV, adc_counter_offset_2_PV: dict[str, Any]
            Offset in the counter stream 1/2 window.
            Units are ADC cycles, from `0` to `SUM_DEC-1`.
        adc_counter_window_1_PV, adc_counter_window_2_PV: dict[str, Any]
            The length of the counter stream 1/2 window.
            Units are ADC cycles, from `1` to `SUM_DEC`.
        counting_mode_PV: dict[str, Any]
            Counting mode on counter streams.
            `0` = differential (change between counts), `1` = normal (threshold counts).
        threshold_count_diff_PV: dict[str, Any]
            Threshold between comparitive counts in differential mode to register loss event (ADC counts)

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}"`, *e.g.* `"11"`.
        Except for `threshold_count_diff` which also contain the section (straight/bend). *e.g.* `"7B"`.
        """

        logging.info("Grabbing adc_counter_mask_PVs...")

        # initialise storage dicts (PVs)
        self.adc_counter_offset_1_PV: dict[str, Any] = {}
        self.adc_counter_window_1_PV: dict[str, Any] = {}
        self.adc_counter_offset_2_PV: dict[str, Any] = {}
        self.adc_counter_window_2_PV: dict[str, Any] = {}
        self.counting_mode_PV: dict[str, Any] = {}
        self.threshold_count_diff_PV: dict[str, Any] = {}

        # grab PVs in loop
        for sector in self.sectors_connected:
            self.adc_counter_offset_1_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask_c1:offset_sp",
                connect=True,
                timeout=0.1,
            )
            self.adc_counter_window_1_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask_c1:window_sp",
                connect=True,
                timeout=0.1,
            )
            self.adc_counter_offset_2_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask_c2:offset_sp",
                connect=True,
                timeout=0.1,
            )
            self.adc_counter_window_2_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask_c2:window_sp",
                connect=True,
                timeout=0.1,
            )
            self.counting_mode_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:counting_mode_sp",
                connect=True,
                timeout=0.1,
            )
            for section in ["A", "B"]:
                self.threshold_count_diff_PV[f"{sector}{section}"] = (
                    epics.pv.get_pv(
                        f"SR{sector:02d}BLM01:threshold:count_diff:{section}_sp",
                        connect=True,
                        timeout=0.1,
                    )
                )

        # grab inits
        self.get_init_adc_counter_masks()

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_init_adc_counter_masks(
        self,
    ) -> None:
        """Loads all initial ADC counter mask settings from all sectors.

        Attributes
        ----------
        init_adc_counter_offset_1, init_adc_counter_offset_2 : dict[str, Union[float, None]]
            Initial values for the ADC counter stream window offsets.
            Values range: `0` to `SUM_DEC-1`.
        init_adc_counter_window_1, init_adc_counter_window_2 : dict[str, Union[float, None]]
            Initial values for the ADC counter stream window lengths.
            Values range: `0` to `SUM_DEC`.
        init_counting_mode         : dict[str, Union[float, None]]
            `0` = differential (change between counts), `1` = normal (threshold counts).
        init_threshold_count_diff  : dict[str, Union[float, None]]
            threshold between comparitive counts in differential mode to register loss event (ADC counts).

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}{section}"`, *e.g.* `"4B"`.
        """

        logging.info("Grabbing adc_counter_mask initial values...")

        # Check state, dont want to grab inits if they've already been changed
        if hasattr(self, "init_adc_counter_offset_1"):
            logging.warning(
                "Call to get_init_counter_masks() STOPPED - already called, will overwrite initital values."
            )
            return None

        # if called on its own,
        if not hasattr(self, "adc_counter_offset_1_PV"):
            self.get_adc_counter_mask_PVs()

        # initialise value storage dicts
        self.init_adc_counter_offset_1: dict[str, Union[float, None]] = {}
        self.init_adc_counter_window_1: dict[str, Union[float, None]] = {}
        self.init_adc_counter_offset_2: dict[str, Union[float, None]] = {}
        self.init_adc_counter_window_2: dict[str, Union[float, None]] = {}
        self.init_counting_mode: dict[str, Union[float, None]] = {}
        self.init_threshold_count_diff: dict[str, Union[float, None]] = {}

        pv_dicts = [
            self.adc_counter_offset_1_PV,
            self.adc_counter_window_1_PV,
            self.adc_counter_offset_2_PV,
            self.adc_counter_window_2_PV,
            self.counting_mode_PV,
            self.threshold_count_diff_PV,
        ]

        value_dicts = [
            self.init_adc_counter_offset_1,
            self.init_adc_counter_window_1,
            self.init_adc_counter_offset_2,
            self.init_adc_counter_window_2,
            self.init_counting_mode,
            self.init_threshold_count_diff,
        ]

        # grab values
        for value_dict, pv_dict in zip(value_dicts, pv_dicts):
            for key, pv in pv_dict.items():
                if pv.connected:
                    value_dict[key] = pv.get(timeout=0.1)
                    time.sleep(self._WAIT_TIME)

        return None

    # ----------------------------------------------------------------------------------------------------------
    def apply_adc_counter_masks(
        self,
        offset_1: int,
        window_1: int,
        offset_2: int,
        window_2: int,
        counting_mode=0,
    ) -> None:
        """Apply passed `adc_counter_window` and `_offset`  values across all BLMs. Default counting mode to integrated (`0`).

        Parameters
        ----------
        offset_1, offset_2: int
            ADC counter offset, such that `offset` + `window` <= `SUM_DEC` (86).
        window_1, window_2: int
            ADC counter window, such that `offset` + `window` <= `SUM_DEC` (86).
        counting_mode: Literal[0, 1]
            Loss count mode for (specifically) the ADC counter masks.
            `0`: differential, `1`: normal (thresholding)
        """
        logging.info("Applying ADC counter masks...")

        # load PVs if not already loaded
        if not hasattr(self, "adc_counter_offset_1_PV"):
            self.get_adc_counter_mask_PVs()

        # apply liberaBLM ADC windows
        for key, pv in self.adc_counter_window_1_PV.items():
            if pv.connected:  # assume if offset_1_PV connects then all other adc_counter_mask PVs have connected
                self.adc_counter_offset_1_PV[key].put(
                    offset_1, use_complete=True
                )
                self.adc_counter_window_1_PV[key].put(
                    window_1, use_complete=True
                )
                self.adc_counter_offset_2_PV[key].put(
                    offset_2, use_complete=True
                )
                self.adc_counter_window_2_PV[key].put(
                    window_2, use_complete=True
                )
                self.counting_mode_PV[key].put(
                    counting_mode, use_complete=True
                )
        # wait for puts to complete
        for key, pv in self.adc_counter_offset_1_PV.items():
            if pv.connected:
                while not all(
                    [
                        self.adc_counter_offset_1_PV[key].put_complete,
                        self.adc_counter_window_1_PV[key].put_complete,
                        self.adc_counter_offset_2_PV[key].put_complete,
                        self.adc_counter_window_2_PV[key].put_complete,
                        self.counting_mode_PV[key].put_complete,
                    ]
                ):
                    time.sleep(0.01)

        logging.info("ADC counter masks applied!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_sumdec_adc_mask_PVs(
        self,
    ) -> None:
        """Loads all adc masks for SUM buffer (offset + window) PVs from all sectors.

        Attributes
        ----------
        sumdec_adc_mask_offset_PV : dict[str, Any]
            ADC mask offset for **SUM buffer counting**, not counter masks.
        sumdec_adc_mask_window_PV : dict[str, Any]
            ADC mask length for **SUM buffer counting**, not counter masks.

        Warning
        -------
        These are the general ADC masks for usual **SUM buffer** counting, not the counter mask windows.
        Please reference the Libera BLM documentation for the difference between these two masks.

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}"`
        *e.g.* `"4B"`
        """
        logging.info("Getting SUM buffer ADC windows...")

        # initialise storage dicts
        self.sumdec_adc_mask_offset_PV: dict[str, Any] = {}
        self.sumdec_adc_mask_window_PV: dict[str, Any] = {}

        # grab PVs in loop
        for sector in self.sectors_connected:
            self.sumdec_adc_mask_offset_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask:offset_sp",
                connect=True,
                timeout=0.1,
            )
            self.sumdec_adc_mask_window_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:adcmask:window_sp",
                connect=True,
                timeout=0.1,
            )

        logging.info("SUM buffer PVs grabbed!")

        # get initial values
        self.get_init_sumdec_adc_masks()

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_init_sumdec_adc_masks(
        self,
    ) -> None:
        """Loads all initial SUM buffer settings from all sectors.

        Attributes
        ----------
        init_sumdec_adc_mask_offset: dict[str, Union[float, None]]
            Initial mask offset for the SUM buffer counter.
        init_sumdec_adc_mask_window: dict[str, Union[float, None]]
            Initial mask length for the SUM buffer counter.

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}"`
        *e.g.* `"4B"`.
        """

        logging.info("Getting initial SUM buffer settings...")

        # Check state, dont want to grab inits if they've already been changed
        if hasattr(self, "init_sumdec_adc_mask_offset"):
            logging.warning(
                "Call to get_init_sumdec_adc_masks() STOPPED - already called, will overwrite initital values."
            )
            return None

        # get PVs if they haven't already been loaded
        if not hasattr(self, "sumdec_adc_mask_offset_PV"):
            self.get_sumdec_adc_mask_PVs()

        self.init_sumdec_adc_mask_offset: dict[str, Union[float, None]] = {}
        self.init_sumdec_adc_mask_window: dict[str, Union[float, None]] = {}

        # grab values
        for key, pv in self.sumdec_adc_mask_offset_PV.items():
            if (
                pv.connected
            ):  # assume if `offset` connects then `window` should be as well.
                self.init_sumdec_adc_mask_offset[key] = (
                    self.sumdec_adc_mask_offset_PV[key].get(timeout=0.1)
                )
                time.sleep(self._WAIT_TIME)
                self.init_sumdec_adc_mask_window[key] = (
                    self.sumdec_adc_mask_window_PV[key].get(timeout=0.1)
                )
                time.sleep(self._WAIT_TIME)

        logging.info("Initial SUM buffer settings grabbed!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_decimation(
        self,
    ) -> None:
        """Loads PVs and initial values associated with decimation (number of ADC cycles for each operation or in each buffer).

        Attributes
        ----------
        sum_decimation_PV : dict[str, Any]
            PV - Sets the decimation factor from ADC to SUM (setting range `[16, 4096]`).
        t0_interval_PV : dict[str, Any]
            PV - Sets the decimation factor for the ADC masks in the Counter stream. Setting range `[16,4096]`.
        t0_interval_expected_PV : dict[str, Any]
            PV - Calculated from the internal ADC clock and the `t0` input trigger (SROC). Expect ~`86`.
        sumdec_periods_PV : dict[str, Any]
            PV - Sets the number of revolutions over which the integrated buffer is calculated.

        init_sum_decimation, init_t0_interval, init_t0_interval_expected, init_sumdec_periods : dict[str, Union[float, None]]
            Initial values of the above PVs.

        Info
        ----
        Importantly, this function loads the `t0_interval_expected` based on the PLL T0 (SROC) events.
        By default, the counter masks and the raw ADC mask that feeds into SUM and SA decimation is set to `16`,
        not the expected `86 = f_ADC/f_rev`. Has no associated `get_init_` function, is self contained.

        Keys for each dictionary are of the form: `"{sector}"`
        *e.g.* `"4B"`.
        """
        logging.info("Grabbing decimation PVs...")

        # initialise storage dicts (PVs)
        self.sum_decimation_PV: dict[str, Any] = {}
        self.t0_interval_PV: dict[str, Any] = {}
        self.t0_interval_expected_PV: dict[str, Any] = {}
        self.sumdec_periods_PV: dict[str, Any] = {}

        pv_dicts = [
            self.sum_decimation_PV,
            self.t0_interval_PV,
            self.t0_interval_expected_PV,
            self.sumdec_periods_PV,
        ]

        # grab PVs
        for sector in self.sectors_connected:
            # Sets the decimation factor from ADC to SUM (Setting range [16, 4096])
            # sanity check to make sure we set ADC offset through full range
            self.sum_decimation_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:decimation:sum_sp",
                connect=True,
                timeout=0.1,
            )
            # Sets the decimation factor for the ADC masks in the Counter stream. Setting range [16,4096]
            # default = 16, want = 86 so we can also change the adc_counter_window and offset through the full fill pattern
            self.t0_interval_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:decimation:t0_interval_sp",
                connect=True,
                timeout=0.1,
            )
            # sanity check = 86
            self.t0_interval_expected_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:decimation:t0_interval_expected",
                connect=True,
                timeout=0.1,
            )
            # Sets the number of revolutions over which the integrated buffer is calculated
            self.sumdec_periods_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:decimation:sumdec_periods_sp",
                connect=True,
                timeout=0.1,
            )

        # Check state, dont want to grab inits if they've already been changed
        if hasattr(self, "init_sum_decimation"):
            logging.warning(
                "Call to get_decimation() STOPPED - already called, will overwrite initital values."
            )
            return None

        # initialise storage dicts (initial values)
        self.init_sum_decimation: dict[str, Union[float, None]] = {}
        self.init_t0_interval: dict[str, Union[float, None]] = {}
        self.init_t0_interval_expected: dict[str, Union[float, None]] = {}
        self.init_sumdec_periods: dict[str, Union[float, None]] = {}

        value_dicts = [
            self.init_sum_decimation,
            self.init_t0_interval,
            self.init_t0_interval_expected,
            self.init_sumdec_periods,
        ]

        # grab init values
        logging.info("Grabbing decimation initial values...")
        for value_dict, pv_dict in zip(value_dicts, pv_dicts):
            for key, pv in pv_dict.items():
                if pv.connected:
                    value_dict[key] = pv.get(timeout=0.1)
                    time.sleep(self._WAIT_TIME)

        logging.info("Done with decimation (got PVs and inits)!")

        # return
        return None

    # ----------------------------------------------------------------------------------------------------------
    def apply_full_decimation(
        self,
    ) -> None:
        """Sets the `t0_interval` for all sectors to `SUM_DEC=86` (`t0_interval_expected`)."""
        if not hasattr(self, "sum_decimation_PV"):
            logging.warning(
                "No loaded decimation PVs or initial values. Fetching now..."
            )
            self.get_decimation()

        # sectors whose decimation has been updated
        affected_sectors: list[str] = []

        for key, pv in self.t0_interval_PV.items():
            if (
                pv.connected
                and self.init_t0_interval[key]
                != self.init_t0_interval_expected[key]
            ):
                pv.put(self.init_t0_interval_expected[key], use_complete=True)
                affected_sectors.append(key)

        # wait for puts to complete
        for key in affected_sectors:
            while not self.t0_interval_PV[key].put_complete:
                time.sleep(self._WAIT_TIME)

        logging.info("Full decimation applied!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_t2_trigger_delays(
        self,
    ) -> None:
        """
        Loads `t2` trigger delay PVs and initial values.

        Attributes
        ----------
        t2_trigger_delays_PV: dict[str, Any]
            Delay for post-mortem acquisition from the `t2` (injection) in units of ADC clock cycles.
        init_t2_trigger_delays : dict[str, Union[float, None]]
            Initial values of the above PV.

        Info
        ----
        Supposed units: *ADC cycles*.
        Configures such that `t2` delays are synchronised with the bunch train, delays increase as you move around the ring.
        This affects integrated buffer loss (triggered on `t2`), so that they all look the same, despite being at
        different locations around the ring.

        Keys for each dictionary are of the form: `"{sector}"`
        *e.g.* `"4B"`.
        """

        logging.info("Getting T2 trigger delays...")

        self.default_t2_trigger_delays = {
            "1": 11,
            "2": 3,
            "3": 0,
            "4": 33,
            "5": 47,
            "6": 59,
            "7": 92,  # 1 rev +  6
            "8": 97,  # 1 rev + 11
            "9": 105,  # 1 rev + 19
            "10": 108,  # 1 rev + 22
            "11": 113,  # 1 rev + 27
            "12": 112,  # 1 rev + 26
            "13": 93,  # 1 rev +  7
            "14": 4,
        }

        # initialise dictionaries
        self.t2_trigger_delays_PV: dict[str, Any] = {}

        for sector in self.sectors_connected:
            self.t2_trigger_delays_PV[f"{sector}"] = epics.pv.get_pv(
                f"SR{sector:02d}BLM01:triggers:t2:delay_sp",
                connect=True,
                timeout=0.1,
            )

        if hasattr(self, "init_t2_trigger_delays"):
            logging.warning(
                "t2_triggers initial values already loaded, dont want to overwrite."
            )
            return None

        self.init_t2_trigger_delays: dict[str, Union[float, None]] = {}

        for key, pv in self.t2_trigger_delays_PV.items():
            if pv.connected:
                self.init_t2_trigger_delays[key] = pv.get(timeout=0.1)

        logging.info("T2 trigger delays fetched!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_settings_PVs(
        self,
    ) -> None:
        """Loads all settings/config PVs from all sectors.

        Attributes
        ----------
        mode_PV : Any
            PV - switch between setting library.
            `0`: not set, `1`: injection, `2`: decay, `3`: auto.
        Vgc_PV : dict[str, Any]
            PV - gain voltage (V). Current setpoint, regardless of mode.
        att_PV : dict[str, Any]
            PV - attenuation (db). Current setpoint, regardless of mode.
        decay_Vgc_PV : dict[str, Any]
            PV - gain voltage (V) applied when switching to decay mode.
        decay_att_PV : dict[str, Any]
            PV - attenuation (db) applied when switching to decay mode.

        Info
        ----
        Keys for each dictionary are of the form: `"{sector}{section}"`.
        *e.g.* `"11A"`.

        `mode` is assigned:

        - `0`: not set
        - `1`: injection
        - `2`: decay
        - `3`: auto

        These PVs are slow to load, please allow a number of seconds to load.
        """
        logging.info("Grabbing settings PVs...")

        # initialise storage dicts (PVs)
        self.mode_PV: Any
        self.Vgc_PV: dict[str, Any] = {}
        self.att_PV: dict[str, Any] = {}
        self.decay_Vgc_PV: dict[str, Any] = {}
        self.decay_att_PV: dict[str, Any] = {}

        # grab PVs in loop
        for sector in self.sectors_connected:
            for section in ["A", "B"]:
                self.Vgc_PV[f"{sector}{section}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BLM01:bld:vgc:{section}_sp",
                    connect=True,
                    timeout=0.1,
                )
                self.att_PV[f"{sector}{section}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BLM01:att:{section}_sp",
                    connect=True,
                    timeout=0.1,
                )
                self.decay_Vgc_PV[f"{sector}{section}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BLM01:DCY:bld:vgc:{section}",
                    connect=True,
                    timeout=0.1,
                )
                self.decay_att_PV[f"{sector}{section}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BLM01:DCY:att:{section}",
                    connect=True,
                    timeout=0.1,
                )

        # mode: auto, injection or decay
        self.mode_PV = epics.pv.get_pv(
            "SR00BLM01:USER_MODE_SELECTION_CMD", connect=True, timeout=0.1
        )

        logging.info("Settings PVs grabbed!")

        # grab initial values
        self.get_init_settings()

        return None

    # ----------------------------------------------------------------------------------------------------------
    def get_init_settings(
        self,
    ) -> None:
        """
        Loads all initial settings from all sectors.

        Attributes
        ----------
        init_mode : Any
            Setting library currently applied.
            `0`: not set, `1`: injection, `2`: decay, `3`: auto.
        init_Vgc : dict[str, Any]
            Applied gain voltage (V). Current setpoint, regardless of mode.
        init_att : dict[str, Any]
            Applied attenuation (db). Current setpoint, regardless of mode.
        init_decay_Vgc : dict[str, Any]
            Gain voltage (V) applied when switching to decay mode.
        init_decay_att : dict[str, Any]
            Attenuation (db) applied when switching to decay mode.

        Keys for each dictionary are of the form: `"{sector}{section}"`.
        *e.g.* `"11A"`.

        `mode` is assigned:

        - `0`: not set
        - `1`: injection
        - `2`: decay
        - `3`: auto
        """
        logging.info("Grabbing initial settings values....")

        # Check state, dont want to grab inits if they've already been changed
        if hasattr(self, "init_mode"):
            logging.warning(
                "Call to get_init_settings() STOPPED - already called, will overwrite initital values."
            )
            return None

        # grab PVs if havent already
        if not hasattr(self, "mode_PV"):
            self.get_settings_PVs()

        # Initialise storage dicts (initial values)
        self.init_mode: Union[str, None] = None
        # NOTE: mode is assigned : {0: not set, 1: injection, 2: decay, 3: auto}
        self.init_Vgc: dict[str, float] = {}
        self.init_att: dict[str, float] = {}
        self.init_decay_Vgc: dict[str, float] = {}
        self.init_decay_att: dict[str, float] = {}

        # grab values
        for key in self.Vgc_PV:
            self.init_Vgc[key] = self.Vgc_PV[key].get(timeout=0.1)
            time.sleep(self._WAIT_TIME)
            self.init_att[key] = self.att_PV[key].get(timeout=0.1)
            time.sleep(self._WAIT_TIME)
            self.init_decay_Vgc[key] = self.decay_Vgc_PV[key].get(timeout=0.1)
            time.sleep(self._WAIT_TIME)
            self.init_decay_att[key] = self.decay_att_PV[key].get(timeout=0.1)
            time.sleep(self._WAIT_TIME)
        # grab initial mode
        self.init_mode = self.mode_PV.get(timeout=0.1)

        logging.info("Initial settings grabbed!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def restore_inits(
        self,
        mode: Literal[
            "adc_counter_masks", "sumdec_adc_masks", "decimation", "settings"
        ],
    ) -> None:
        """
        Restores initial settings (of all loaded PVs) to all sectors

        Parameters
        ----------
        mode: Literal["adc_counter_masks", "sumdec_adc_masks", "decimation", "settings"]
            [str][] assignment for what settings to restore
        """

        # if-else chain here because python=3.9 (cant use switch-case syntax)
        if mode == "adc_counter_masks":
            # check for loaded inits
            if not hasattr(self, "init_adc_counter_offset_1"):
                logging.error(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            logging.info("Restoring adc_counter_masks...")
            for key in self.adc_counter_offset_1_PV:
                self.adc_counter_offset_1_PV[key].put(
                    self.init_adc_counter_offset_1[key], use_complete=True
                )
                self.adc_counter_window_1_PV[key].put(
                    self.init_adc_counter_window_1[key], use_complete=True
                )
                self.adc_counter_offset_2_PV[key].put(
                    self.init_adc_counter_offset_2[key], use_complete=True
                )
                self.adc_counter_window_2_PV[key].put(
                    self.init_adc_counter_window_2[key], use_complete=True
                )
                self.counting_mode_PV[key].put(
                    self.init_counting_mode[key], use_complete=True
                )
            for key in self.threshold_count_diff_PV:
                self.threshold_count_diff_PV[key].put(
                    self.init_threshold_count_diff[key], use_complete=True
                )
            # wait for all puts to complete
            for key in self.adc_counter_offset_1_PV:
                while not all(
                    [
                        self.adc_counter_offset_1_PV[key].put_complete,
                        self.adc_counter_window_1_PV[key].put_complete,
                        self.adc_counter_offset_2_PV[key].put_complete,
                        self.adc_counter_window_2_PV[key].put_complete,
                        self.counting_mode_PV[key].put_complete,
                    ]
                ):
                    time.sleep(self._WAIT_TIME)
            for key in self.threshold_count_diff_PV:
                while not self.threshold_count_diff_PV[key].put_complete:
                    time.sleep(self._WAIT_TIME)
            logging.info("adc_counter_masks restored to initial values!")

        elif mode == "sumdec_adc_masks":
            # check for loaded inits
            if not hasattr(self, "init_sumdec_adc_mask_offset"):
                logging.error(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            logging.info("Restoring SUM_DEC ADC masks...")
            for key in self.sumdec_adc_mask_offset_PV:
                self.sumdec_adc_mask_offset_PV[key].put(
                    self.init_sumdec_adc_mask_offset[key], use_complete=True
                )
                self.sumdec_adc_mask_window_PV[key].put(
                    self.init_sumdec_adc_mask_window[key], use_complete=True
                )
            # wait for all puts to complete
            for key in self.sumdec_adc_mask_offset_PV:
                while not all(
                    [
                        self.sumdec_adc_mask_offset_PV[key].put_complete,
                        self.sumdec_adc_mask_window_PV[key].put_complete,
                    ]
                ):
                    time.sleep(self._WAIT_TIME)
            logging.info("Restored SUM_DEC ADC masks!")

        elif mode == "decimation":
            # check for loaded inits
            if not hasattr(self, "init_sum_decimation"):
                logging.error(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            logging.info("Restoring decimation settings...")
            for key in self.sum_decimation_PV:
                self.sum_decimation_PV[key].put(
                    self.init_sum_decimation[key], use_complete=True
                )
                self.t0_interval_PV[key].put(
                    self.init_t0_interval[key], use_complete=True
                )
                self.t0_interval_expected_PV[key].put(
                    self.init_t0_interval_expected[key], use_complete=True
                )
            # wait for all puts to complete
            for key in self.sum_decimation_PV:
                while not all(
                    [
                        self.sum_decimation_PV[key].put_complete,
                        self.t0_interval_PV[key].put_complete,
                        self.t0_interval_expected_PV[key].put_complete,
                    ]
                ):
                    time.sleep(self._WAIT_TIME)
            logging.info("Restored decimation!")

        elif mode == "settings":
            # check for loaded inits
            if not hasattr(self, "init_Vgc"):
                logging.error(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            logging.info("Restoring blm settings...")
            self.mode_PV.put(self.init_mode, use_complete=True)
            for key in self.Vgc_PV:
                self.Vgc_PV[key].put(self.init_Vgc[key], use_complete=True)
                self.att_PV[key].put(self.init_att[key], use_complete=True)
                self.decay_Vgc_PV[key].put(
                    self.init_decay_Vgc[key], use_complete=True
                )
                self.decay_att_PV[key].get(
                    self.init_decay_att[key], use_complete=True
                )
            # wait for all puts to complete
            while not self.mode_PV.put_complete:
                time.sleep(self._WAIT_TIME)
            for key in self.Vgc_PV:
                while not all(
                    [
                        self.Vgc_PV[key].put_complete,
                        self.att_PV[key].put_complete,
                        self.decay_Vgc_PV[key].put_complete,
                        self.decay_att_PV[key].put_complete,
                    ]
                ):
                    time.sleep(self._WAIT_TIME)
            logging.info("blm settings restored to initial values!")

        else:
            logging.error(
                f"Invalid restore mode! No inits resotred.\nYour input -- > mode={mode}."
            )

        return None

    # ----------------------------------------------------------------------------------------------------------
    def inits_to_json(
        self, mode: Literal["all", "adc_counter_masks", "settings"]
    ) -> None:
        """Writes all (stored) inits to JSON files.

        Parameters
        ----------
        mode: Literal['all', 'adc_counter_masks', 'settings']
            str assignment for what settings to restore

        Info
        ----
        Fails safe, in that if there are no inits stored, it wont try to write them to file.
        Dir is `./BLM_inits/YYYY-MM-DD_hhmmss`.
        *e.g.* `./BLM_intis/2025-10-24_08h16m21s`.
        """
        # warn if theres no inits loaded AT ALL (then exit)
        conditions = [
            hasattr(self, "init_adc_counter_offset_1"),
            hasattr(self, "init_mode"),
        ]
        if not any(conditions):
            warnings.warn("No initial settings loaded and so none restored.")
            return None

        # Create save dir
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d_%Hh%Mm%Ss")
        path = Path.cwd()
        inits_path = path / "BLM_inits" / timestamp_str
        Path.mkdir(inits_path, parents=True, exist_ok=True)

        # Check state, cant restore inits if there are none
        conditions = [
            mode == "all" or mode == "adc_counter_masks",
            hasattr(self, "init_adc_counter_offset_1"),
        ]
        if all(conditions):
            logging.info("saving adc_counter_masks to json...")
            with open(inits_path / "init_adc_counter_offset_1.json", "w") as f:
                json.dump(self.init_adc_counter_offset_1, f)
            with open(inits_path / "init_adc_counter_window_1.json", "w") as f:
                json.dump(self.init_adc_counter_window_1, f)
            with open(inits_path / "init_adc_counter_offset_2.json", "w") as f:
                json.dump(self.init_adc_counter_offset_2, f)
            with open(inits_path / "init_adc_counter_window_2.json", "w") as f:
                json.dump(self.init_adc_counter_window_2, f)
        else:
            warnings.warn(
                "Asked to write blm adc counter masks to json, but no inits loaded."
            )

        # Check state, cant restore inits if there are none
        conditions = [
            mode == "all" or mode == "settings",
            hasattr(self, "init_mode"),
        ]
        if all(conditions):
            logging.info("saving blm settings to json...")
            with open(inits_path / "init_mode.json", "w") as f:
                json.dump(self.init_mode, f)
            with open(inits_path / "init_Vgc.json", "w") as f:
                json.dump(self.init_Vgc, f)
            with open(inits_path / "init_att.json", "w") as f:
                json.dump(self.init_att, f)
            with open(inits_path / "init_decay_Vgc.json", "w") as f:
                json.dump(self.init_decay_Vgc, f)
            with open(inits_path / "init_decay_att.json", "w") as f:
                json.dump(self.init_decay_att, f)
        else:
            warnings.warn(
                "Asked to write blm settings to json, but no inits loaded."
            )

        logging.info("All loaded inits written to JSON!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def restore_from_json(
        self,
        mode: Literal["all", "adc_counter_masks", "settings"],
        path="BLM_defaults",
    ) -> None:
        """
        Restores settings from saved JSON. \\
        Defaults to default config, or can provide a path to inits. \\
        Note: mode is assigned: {0: not set, 1: injection, 2: decay, 3: auto}

        Parameters
        ----------
        mode: Literal['all', 'adc_counter_masks', 'settings']
            str assignment for what settings to restore
        path: str
            Path to JSON files. Can provide dir to saved inits, defaults to default config.
        """
        # --- default values
        self.default_mode: Union[str, None] = None
        self.default_Vgc: dict[str, float] = {}
        self.default_att: dict[str, float] = {}
        self.default_decay_Vgc: dict[str, float] = {}
        self.default_decay_att: dict[str, float] = {}
        self.default_adc_counter_offset_1: dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_1: dict[str, Union[float, None]] = {}
        self.default_adc_counter_offset_2: dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_2: dict[str, Union[float, None]] = {}

        # Check state, cant restore inits if there are none
        if any([mode == "all", mode == "adc_counter_masks"]):
            # Check PVs are loaded, and if not, load them
            if not hasattr(self, "adc_counter_offset_1_PV"):
                self.get_adc_counter_mask_PVs()
            # Try to read each json, the restore just that PVs defaults in each try block
            # This way, if the json does not exist, we dont waste time trying to also write to PVs
            logging.info(
                "reading and restoring adc_counter_masks from json..."
            )
            try:
                with open(
                    os.path.join(path, "init_adc_counter_offset_1.json"), "r"
                ) as f:
                    self.default_adc_counter_offset_1 = json.load(f)
                for key in self.default_adc_counter_offset_1:
                    self.adc_counter_offset_1_PV[key].put(
                        self.default_adc_counter_offset_1[key]
                    )
                    while self.adc_counter_offset_1_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(
                    os.path.join(path, "init_adc_counter_window_1.json"), "r"
                ) as f:
                    self.default_adc_counter_window_1 = json.load(f)
                for key in self.default_adc_counter_window_1:
                    self.adc_counter_window_1_PV[key].put(
                        self.default_adc_counter_window_1[key]
                    )
                    while self.adc_counter_window_1_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(
                    os.path.join(path, "init_adc_counter_offset_2.json"), "r"
                ) as f:
                    self.default_adc_counter_offset_2 = json.load(f)
                for key in self.default_adc_counter_offset_2:
                    self.adc_counter_offset_2_PV[key].put(
                        self.default_adc_counter_offset_2[key]
                    )
                    while self.adc_counter_offset_2_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(
                    os.path.join(path, "init_adc_counter_window_2.json"), "r"
                ) as f:
                    self.default_adc_counter_window_2 = json.load(f)
                for key in self.default_adc_counter_window_2:
                    self.adc_counter_window_2_PV[key].put(
                        self.default_adc_counter_window_2[key]
                    )
                    while self.adc_counter_window_2_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())

        # Check state, cant restore inits if there are none
        if any([mode == "all", mode == "settings"]):
            # Check PVs are loaded, and if not, load them
            if not hasattr(self, "mode_PV"):
                self.get_settings_PVs()
            # Try to read each json, the restore just that PVs defaults in each try block
            # This way, if the json does not exist, we dont waste time trying to also write to PVs
            logging.info("reading and restoring blm settings from json...")
            try:
                with open(os.path.join(path, "init_mode.json"), "r") as f:
                    self.default_mode = json.load(f)
                self.mode_PV.put(self.default_mode)
                while self.mode_PV.put_complete:
                    time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(os.path.join(path, "init_Vgc.json"), "r") as f:
                    self.default_Vgc = json.load(f)
                for key in self.default_Vgc:
                    self.Vgc_PV[key].put(self.default_Vgc[key])
                    while self.Vgc_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(os.path.join(path, "init_att.json"), "r") as f:
                    self.default_att = json.load(f)
                for key in self.default_att:
                    self.att_PV[key].put(self.default_att[key])
                    while self.att_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(os.path.join(path, "init_decay_Vgc.json"), "r") as f:
                    self.default_decay_Vgc = json.load(f)
                for key in self.default_decay_Vgc:
                    self.decay_Vgc_PV[key].put(self.default_decay_Vgc[key])
                    while self.decay_Vgc_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())
            try:
                with open(os.path.join(path, "init_decay_att.json"), "r") as f:
                    self.default_decay_att = json.load(f)
                for key in self.default_decay_att:
                    self.decay_att_PV[key].put(self.default_decay_att[key])
                    while self.decay_att_PV[key].put_complete:
                        time.sleep(self._WAIT_TIME)
            except IOError:
                logging.error(traceback.format_exc())

        logging.info("BLM Settings restored from JSON!")

        return None

    # ----------------------------------------------------------------------------------------------------------
    def restore_defaults(
        self, mode: Literal["all", "adc_counter_masks", "settings"]
    ) -> None:
        """
        Restores defaults from json. \\
        Simply an alias for restore_from_json() but with default path args.
        """
        self.restore_from_json(mode=mode)

        return None


if __name__ == "__main__":
    print(
        "epicsBLMs contains a class file 'BLMs' that is used to connect to PVs and store loss data for resonant depolarisation experiments."
    )
    print(
        "The class is general and can be used to detect loss on almost all available output streams."
    )
    print("Run help(BLMs) after import for more details.")
