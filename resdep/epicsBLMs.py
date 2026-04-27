"""
Classes for beam loss monitors (BLMs)
"""
"""
██████╗ ███████╗ █████╗ ███╗   ███╗    ██╗      ██████╗ ███████╗███████╗    ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ ███████╗ \\
██╔══██╗██╔════╝██╔══██╗████╗ ████║    ██║     ██╔═══██╗██╔════╝██╔════╝    ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝ \\
██████╔╝█████╗  ███████║██╔████╔██║    ██║     ██║   ██║███████╗███████╗    ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝███████╗ \\
██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║    ██║     ██║   ██║╚════██║╚════██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗╚════██║ \\
██████╔╝███████╗██║  ██║██║ ╚═╝ ██║    ███████╗╚██████╔╝███████║███████║    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║███████║ \\
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝    ╚══════╝ ╚═════╝ ╚══════╝╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
"""

from typing import Any, Union, Literal
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
    A libera object which handles EPICS BLM PVs, values, states, and common functions \\
    *e.g.* get PVs, get initial values, restore defaults
    """
    def __init__(self, ):
        # --- states
        self._got_loss_PVs              : bool = False
        self._got_settings_PVs          : bool = False
        self._got_init_settings         : bool = False
        self._got_adc_counter_mask_PVs  : bool = False
        self._got_init_adc_counter_masks: bool = False
        self._got_sumdec_adc_mask_PVs   : bool = False
        self._got_init_sumdec_adc_masks : bool = False
        self._got_decimation            : bool = False
        self._got_sector11              : bool = False
        self._got_t2_trigger_delays     : bool = False

        # initialise dictionaries
        # using "flat is better than nested" approach, all dicts have the same keys
        #   of form {sector}{section}, e.g. "6B"
        #   except for the adc_counter_offset|window which are per IOC (so the key is just {sector})
        # --- PVs
        self.loss                       : dict[str, Any] = {}
        self.adc_counter_loss_1         : dict[str, Any] = {}
        self.adc_counter_loss_2         : dict[str, Any] = {}
        self.mode                       : Any
        self.Vgc                        : dict[str, Any] = {}
        self.att                        : dict[str, Any] = {}
        self.decay_Vgc                  : dict[str, Any] = {}
        self.decay_att                  : dict[str, Any] = {}
        self.adc_counter_offset_1       : dict[str, Any] = {}
        self.adc_counter_window_1       : dict[str, Any] = {}
        self.adc_counter_offset_2       : dict[str, Any] = {}
        self.adc_counter_window_2       : dict[str, Any] = {}
        self.integrated_buffer_loss     : dict[str, Any] = {}
        self.counting_mode              : dict[str, Any] = {}
        self.threshold_count_diff       : dict[str, Any] = {}
        self.sumdec_adc_mask_offset     : dict[str, Any] = {}
        self.sumdec_adc_mask_window     : dict[str, Any] = {}
        self.sum_decimation             : dict[str, Any] = {}
        self.t0_interval                : dict[str, Any] = {}
        self.t0_interval_expected       : dict[str, Any] = {}
        self.sumdec_periods             : dict[str, Any] = {}
        self.t2_trigger_delays          : dict[str, Any] = {}

        # --- initial values
        self.init_mode                  : Union[str, None] = None
        # NOTE: mode is assigned        : {0: not set, 1: injection, 2: decay, 3: auto}
        self.init_Vgc                   : dict[str, float] = {}
        self.init_att                   : dict[str, float] = {}
        self.init_decay_Vgc             : dict[str, float] = {}
        self.init_decay_att             : dict[str, float] = {}
        self.init_adc_counter_offset_1  : dict[str, Union[float, None]] = {}
        self.init_adc_counter_window_1  : dict[str, Union[float, None]] = {}
        self.init_adc_counter_offset_2  : dict[str, Union[float, None]] = {}
        self.init_adc_counter_window_2  : dict[str, Union[float, None]] = {}
        self.init_counting_mode         : dict[str, Union[float, None]] = {}
        self.init_threshold_count_diff  : dict[str, Union[float, None]] = {}
        self.init_sumdec_adc_mask_offset: dict[str, Union[float, None]] = {}
        self.init_sumdec_adc_mask_window: dict[str, Union[float, None]] = {}
        self.init_sum_decimation        : dict[str, Union[float, None]] = {}
        self.init_t0_interval           : dict[str, Union[float, None]] = {}
        self.init_t0_interval_expected  : dict[str, Union[float, None]] = {}
        self.init_sumdec_periods        : dict[str, Union[float, None]] = {}
        self.init_t2_trigger_delays     : dict[str, Union[float, None]] = {}

        # --- default values
        self.default_mode                   : Union[str, None] = None
        self.default_Vgc                    : dict[str, float] = {}
        self.default_att                    : dict[str, float] = {}
        self.default_decay_Vgc              : dict[str, float] = {}
        self.default_decay_att              : dict[str, float] = {}
        self.default_adc_counter_offset_1   : dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_1   : dict[str, Union[float, None]] = {}
        self.default_adc_counter_offset_2   : dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_2   : dict[str, Union[float, None]] = {}
        self.default_sumdec_adc_mask_offset : dict[str, Union[float, None]] = {}
        self.default_sumdec_adc_mask_window : dict[str, Union[float, None]] = {}
        self.default_t2_trigger_delays      : dict[str, Union[float, None]] = {}

        # --- wait time between PV calls / assignments to not flood system
        self.__wait_time = 0.1
    # ----------------------------------------------------------------------------------------------------------
    def get_loss_PVs(self, ) -> None:
        """
        Loads all loss PVs (regular slow acquisition [SA] and loss from the two ADC counter masks)
        from all sectors and returns dictionaries (of PVs) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '11A' 
        """

        print("Grabbing loss PVs...")

        # grab PVs in loop
        for sector in range(1,14+1,1):
            for section in ['A', 'B']:
                self.loss[f"{sector}{section}"]                     = epics.pv.get_pv(f"SR{sector:02d}BLM01:SIGNALS_SA_{section}_MONITOR", connect=True)
                self.adc_counter_loss_1[f"{sector}{section}"]       = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:counter.{section}1", connect=True)
                self.adc_counter_loss_2[f"{sector}{section}"]       = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:counter.{section}2", connect=True)
                self.integrated_buffer_loss[f"{sector}{section}"]   = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:adc_integrated.{section}", connect=True)
        
        # update state
        self._got_loss_PVs = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_adc_counter_mask_PVs(self, ) -> None:
        """
        Loads all adc counter masks (offset + window -- 1 & 2) PVs from all sectors and returns dictionaries (of PVs) \\
        Keys for each dictionary are of the form: {sector}... \\
        *e.g.* '11A' 
        """

        print("Grabbing adc_counter_mask_PVs...")

        # grab PVs in loop
        for sector in range(1,14+1,1):
            self.adc_counter_offset_1[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c1:offset_sp", connect=True)
            self.adc_counter_window_1[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c1:window_sp", connect=True)
            self.adc_counter_offset_2[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c2:offset_sp", connect=True)
            self.adc_counter_window_2[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c2:window_sp", connect=True)
            self.counting_mode[f"{sector}"]        = epics.pv.get_pv(f"SR{sector:02d}BLM01:counting_mode_sp", connect=True) 
            for section in ["A", "B"]:
                self.threshold_count_diff[f"{sector}{section}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:threshold:count_diff:{section}_sp", connect=True)
        

        # update state
        self._got_adc_counter_mask_PVs = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_init_adc_counter_masks(self,) -> None:
        """
        Loads all initial ADC counter mask settings from all sectors and returns dictionaries (of values) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '4B' 
        """

        print("Grabbing adc_counter_mask initial values...")

        # Check state, dont want to grab inits if they've already been changed
        if self._got_init_adc_counter_masks:
            print('Call to get_init_counter_masks() STOPPED - already called, will overwrite initital values.')
            return None 

        if not self._got_adc_counter_mask_PVs:
            self.get_adc_counter_mask_PVs()

        # grab values
        for key in self.adc_counter_offset_1:
            self.init_adc_counter_offset_1[key] = self.adc_counter_offset_1[key].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_window_1[key] = self.adc_counter_window_1[key].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_offset_2[key] = self.adc_counter_offset_2[key].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_window_2[key] = self.adc_counter_window_2[key].get()
            time.sleep(self.__wait_time)
            self.init_counting_mode[key] = self.counting_mode[key].get()
            time.sleep(self.__wait_time)

        for key in self.threshold_count_diff:
            self.init_threshold_count_diff[key] = self.threshold_count_diff[key].get()
            time.sleep(self.__wait_time)

        # update states
        self._got_init_adc_counter_masks = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def apply_adc_counter_masks(self, offset_1: int, window_1: int, offset_2: int, window_2: int, counting_mode=0) -> None:
        """
        Apply passed adc_counter_mask values across all BLMs. Default counting mode to integrated (0).

        Parameters
        ----------
        offset_1: int
            ADC counter offset, such that offset_1 + window_1 <= SUM_DEC (86)
        window_1: int
            ADC counter window, such that offset_1 + window_1 <= SUM_DEC (86)
        offset_2: int
            ADC counter offset, such that offset_2 + window_2 <= SUM_DEC (86)
        window_2: int
            ADC counter window, such that offset_2 + window_2 <= SUM_DEC (86)
        counting_mode: Literal[0, 1]
            Loss count mode for (specifically) the ADC counter masks. \\
            0: differential, 1: normal (thresholding)
        """
        print("Applying ADC counter masks...")
		# apply liberaBLM ADC windows
        for key in self.adc_counter_window_1:
            self.adc_counter_offset_1[key].put(offset_1, use_complete=True)
            self.adc_counter_window_1[key].put(window_1, use_complete=True)
            self.adc_counter_offset_2[key].put(offset_2, use_complete=True)
            self.adc_counter_window_2[key].put(window_2, use_complete=True)
            self.counting_mode[key].put(counting_mode, use_complete=True)
		# wait for puts to complete
        for key in self.adc_counter_offset_1:
            while not all(
				[self.adc_counter_offset_1[key].put_complete,
				 self.adc_counter_window_1[key].put_complete,
				 self.adc_counter_offset_2[key].put_complete,
				 self.adc_counter_window_2[key].put_complete,
				 self.counting_mode[key].put_complete]
			):
                time.sleep(0.01)
       
        print("ADC counter masks applied!")

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_sumdec_adc_mask_PVs(self, ) -> None:
        """
        Loads all adc masks for SUM_DEC buffer (offset + window) PVs from all sectors and returns dictionaries (of PVs) \\
        **NOTE** These are the general ADC masks for usual SUM decimation counting, not the counter_mask windows.
        Please reference the Libera BLM documentation for the difference between these two masks.
        Keys for each dictionary are of the form: {sector}... \\
        *e.g.* '4B' 
        """

        # grab PVs in loop
        for sector in range(1,14+1,1):
            self.sumdec_adc_mask_offset[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask:offset_sp", connect=True)
            self.sumdec_adc_mask_window[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask:window_sp", connect=True)
        
        # update state
        self._got_sumdec_adc_mask_PVs = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_init_sumdec_adc_masks(self,) -> None:
        """
        Loads all initial SUM_DEC ADC mask settings from all sectors and returns dictionaries (of values) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '4B' 
        """

        # Check state, dont want to grab inits if they've already been changed
        if self._got_init_sumdec_adc_masks:
            print('Call to get_init_sumdec_adc_masks() STOPPED - already called, will overwrite initital values.')
            return None 

        if not self._got_sumdec_adc_mask_PVs:
            self.get_sumdec_adc_mask_PVs()

        # grab values
        for key in self.sumdec_adc_mask_offset:
            self.init_sumdec_adc_mask_offset[key] = self.sumdec_adc_mask_offset[key].get()
            time.sleep(self.__wait_time)
            self.init_sumdec_adc_mask_window[key] = self.sumdec_adc_mask_window[key].get()
            time.sleep(self.__wait_time)

        # update states
        self._got_init_sumdec_adc_masks = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_decimation(self,) -> None:
        """
        Loads PVs and initial values associated with decimation (number of ADC cycles for each operation or in each buffer)
        Importantly, loads the t0_interval_expected based on the PLL T0 (SROC) events. \\
        By default, the counter_masks and the raw ADC mask that feeds into SUM and SA decimation is set to 16, 
        not the expected 86 = f_ADC/f_rev
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '4B' 
        """

        # Check state, dont want to grab inits if they've already been changed
        if self._got_decimation:
            print('Call to get_decimation() STOPPED - already called, will overwrite initital values.')
            return None 
        
        # grab PVs
        print("Grabbing decimation PVs...")
        for sector in range(1,14+1,1):
            # Sets the decimation factor from ADC to SUM (Setting range [16, 4096])
            # sanity check to make sure we set ADC offset through full range
            self.sum_decimation[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:decimation:sum_sp", connect=True)
            # Sets the decimation factor for the ADC masks in the Counter stream. Setting range [16,4096]
            # default = 16, want = 86 so we can also change the adc_counter_window and offset through the full fill pattern
            self.t0_interval[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:decimation:t0_interval_sp", connect=True)
            # sanity check = 86
            self.t0_interval_expected[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:decimation:t0_interval_expected", connect=True)
            # Sets the number of revolutions over which the integrated buffer is calculated
            self.sumdec_periods[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:decimation:sumdec_periods_sp", connect=True)

        # wait (unessary maybe since we have connect=True)
        time.sleep(2)

        # grab init values
        print("Grabbing decimation inital values...")
        for key in self.t0_interval_expected:
            self.init_sum_decimation[key] = self.sum_decimation[key].get()
            time.sleep(self.__wait_time)
            self.init_t0_interval[key] = self.t0_interval[key].get()
            time.sleep(self.__wait_time)
            self.init_t0_interval_expected[key] = self.t0_interval_expected[key].get()
            time.sleep(self.__wait_time)
            self.init_sumdec_periods[key] = self.sumdec_periods[key].get()
            time.sleep(self.__wait_time)
        

        # update state
        print("Done with decimation (got PVs and inits)!")
        self._got_decimation = True

        # return
        return None
    # ----------------------------------------------------------------------------------------------------------
    def apply_full_decimation(self, ) -> None:
        """
        Sets the t0_intervals all to 86 (t0_interval_expected)
        """

        if not self._got_decimation:
            print("No loaded decimation PVs or inital values. Fetching now...")
            self.get_decimation()

        # update flag for put_complete
        value_was_updated: dict[str, bool] = {}

        for key, PV in self.t0_interval.items():
            value_was_updated[key] = False 
            if self.init_t0_interval[key] != self.init_t0_interval_expected[key]:
                value_was_updated[key] = True
                PV.put(self.init_t0_interval_expected[key], use_complete=True)

        # wait for puts to complete
        for key, PV in self.t0_interval.items():
            if value_was_updated[key]:
                while not PV.put_complete:
                    time.sleep(self.__wait_time)

        print("Full decimation applied!")

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_t2_trigger_delays(self,) -> None:
        """
        Loads `t2` trigger delay PVs and initial values. \\
        Supposed units: *ADC cycles*

        `t2` triggers are synchronised with the bunch train, delays increase as you move around the ring. \\
        This affects integrated buffer loss (triggered on `t2`), so that they all look the same, despite being at \\
        different locations around the ring.
        """

        print("Getting T2 trigger delays...")

        if self._got_t2_trigger_delays:
            print("Already loaded ")
            return None
        
        self.default_t2_trigger_delays = {
            "1":     11,
            "2":      3,
            "3":      0,
            "4":     33,
            "5":     47,
            "6":     59,
            "7":     92, # 1 rev +  6
            "8":     97, # 1 rev + 11
            "9":    105, # 1 rev + 19
            "10":   108, # 1 rev + 22
            "11":   113, # 1 rev + 27
            "12":   112, # 1 rev + 26
            "13":    93, # 1 rev +  7
            "14":     4
        }

        for sector in range(1, 14+1, 1):
            self.t2_trigger_delays[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:triggers:t2:delay_sp", connect=True)

        for key, PV in self.t2_trigger_delays.items():
            self.init_t2_trigger_delays[key] = PV.get()

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_settings_PVs(self, ) -> None:
        """
        Loads all settings / config PVs from all sectors and returns dictionaries (of PVs) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '11A' \\
        Note: mode is assigned: {0: not set, 1: injection, 2: decay, 3: auto}

        Important Info
        --------------
        These PVs are slow to load, please allow a minute or two to load in all the PVs
        """

        # grab PVs in loop
        for sector in range(1,14+1,1):
            for section in ['A', 'B']:
                self.Vgc[f"{sector}{section}"] 		    = epics.pv.get_pv(f"SR{sector:02d}BLM01:bld:vgc:{section}_sp", connect=True)
                self.att[f"{sector}{section}"] 		    = epics.pv.get_pv(f"SR{sector:02d}BLM01:att:{section}_sp", connect=True)
                self.decay_Vgc[f"{sector}{section}"] 	= epics.pv.get_pv(f"SR{sector:02d}BLM01:DCY:bld:vgc:{section}", connect=True)
                self.decay_att[f"{sector}{section}"] 	= epics.pv.get_pv(f"SR{sector:02d}BLM01:DCY:att:{section}", connect=True)

        # mode: auto, injection or decay
        self.mode = epics.pv.get_pv("SR00BLM01:USER_MODE_SELECTION_CMD", connect=True)
        
        # update state
        self._got_settings_PVs = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def get_init_settings(self,) -> None:
        """
        Loads all initial settings from all sectors and returns dictionaries (of values) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '4B' \\
        Note: mode is assigned: {0: not set, 1: injection, 2: decay, 3: auto}
        """

        # Check state, dont want to grab inits if they've already been changed
        if self._got_init_settings:
            print('Call to get_init_settings() STOPPED - already called, will overwrite initital values.')
            return None 

        if not self._got_settings_PVs:
            self.get_settings_PVs()

        # grab values
        for key in self.Vgc:
            self.init_Vgc[key] = self.Vgc[key].get()
            time.sleep(self.__wait_time)
            self.init_att[key] = self.att[key].get()
            time.sleep(self.__wait_time)
            self.init_decay_Vgc[key] = self.decay_Vgc[key].get()
            time.sleep(self.__wait_time)
            self.init_decay_att[key] = self.decay_att[key].get()
            time.sleep(self.__wait_time)
        # grab inital mode
        self.init_mode = self.mode.get()
        time.sleep(self.__wait_time)

        # update states
        self._got_init_settings = True

        return None
    # ----------------------------------------------------------------------------------------------------------
    def restore_inits(self, mode: Literal["adc_counter_masks", "sumdec_adc_masks", "decimation", "settings"]) -> None:
        """
        Restores all (loaded) initial settings from all sectors 

        Parameters
        ----------
        mode: Literal["adc_counter_masks", "sumdec_adc_masks", "decimation", "settings"]
            str assignment for what settings to restore
        
        """


        if mode == "adc_counter_masks":
            # check for loaded inits
            if not self._got_init_adc_counter_masks:
                print(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            print("Restoring adc_counter_masks...")
            for key in self.adc_counter_offset_1:
                self.adc_counter_offset_1[key].put(self.init_adc_counter_offset_1[key], use_complete=True)
                self.adc_counter_window_1[key].put(self.init_adc_counter_window_1[key], use_complete=True)
                self.adc_counter_offset_2[key].put(self.init_adc_counter_offset_2[key], use_complete=True)
                self.adc_counter_window_2[key].put(self.init_adc_counter_window_2[key], use_complete=True)
                self.counting_mode[key].put(self.init_counting_mode[key], use_complete=True)
            for key in self.threshold_count_diff:
                self.threshold_count_diff[key].put(self.init_threshold_count_diff[key], use_complete=True)
            # wait for all puts to complete
            for key in self.adc_counter_offset_1:
                while not all([
                    self.adc_counter_offset_1[key].put_complete, 
                    self.adc_counter_window_1[key].put_complete,
                    self.adc_counter_offset_2[key].put_complete,
                    self.adc_counter_window_2[key].put_complete,
                    self.counting_mode[key].put_complete
                ]):
                    time.sleep(self.__wait_time)
            for key in self.threshold_count_diff:
                while not self.threshold_count_diff[key].put_complete:
                    time.sleep(self.__wait_time)
            print("adc_counter_masks restored to initial values!")

        elif mode == "sumdec_adc_masks":
            # check for loaded inits
            if not self._got_init_sumdec_adc_masks:
                print(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            print("Restoring SUM_DEC ADC masks...")
            for key in self.sumdec_adc_mask_offset:
                self.sumdec_adc_mask_offset[key].put(self.init_sumdec_adc_mask_offset[key], use_complete=True)
                self.sumdec_adc_mask_window[key].put(self.init_sumdec_adc_mask_window[key], use_complete=True)
            # wait for all puts to complete
            for key in self.sumdec_adc_mask_offset:
                while not all(
                    [self.sumdec_adc_mask_offset[key].put_complete,
                    self.sumdec_adc_mask_window[key].put_complete]
                ):
                    time.sleep(self.__wait_time)
            print("Restored SUM_DEC ADC masks!")

        elif mode == "decimation":
            # check for loaded inits
            if not self._got_decimation:
                print(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            print("Restoring decimation settings...")
            for key in self.sum_decimation:
                self.sum_decimation[key].put(self.init_sum_decimation[key], use_complete=True)
                self.t0_interval[key].put(self.init_t0_interval[key], use_complete=True)
                self.t0_interval_expected[key].put(self.init_t0_interval_expected[key], use_complete=True)
            # wait for all puts to complete
            for key in self.sum_decimation:
                while not all(
                    [self.sum_decimation[key].put_complete,
                    self.t0_interval[key].put_complete,
                    self.t0_interval_expected[key].put_complete]
                ):
                    time.sleep(self.__wait_time)
            print("Restored decimation!")

        elif mode == "settings":
            # check for loaded inits
            if not self._got_init_settings:
                print(f"No {mode} inits loaded, restoration failed!")
                return None
            # restore inits
            print("Restoring blm settings...")
            self.mode.put(self.init_mode, use_complete=True)
            for key in self.Vgc:
                self.Vgc[key].put(self.init_Vgc[key], use_complete=True)
                self.att[key].put(self.init_att[key], use_complete=True)
                self.decay_Vgc[key].put(self.init_decay_Vgc[key], use_complete=True)
                self.decay_att[key].get(self.init_decay_att[key], use_complete=True)
            # wait for all puts to complete
            while not self.mode.put_complete:
                time.sleep(self.__wait_time)
            for key in self.Vgc:
                while not all(
                    [self.Vgc[key].put_complete,
                    self.att[key].put_complete,
                    self.decay_Vgc[key].put_complete,
                    self.decay_att[key].put_complete]
                ):
                    time.sleep(self.__wait_time)
            print("blm settings restored to initial values!")

        else:
            print(f"Invalid restore mode! No inits resotred.\nYour input -- > mode={mode}.")

        return None
    # ----------------------------------------------------------------------------------------------------------
    def inits_to_json(self, mode: Literal['all', 'adc_counter_masks', 'settings']) -> None:
        """
        Writes all (stored) inits to JSON files. \\
        Fails safe, in that if there are no inits stored, it wont try to write them to file \\
        Dir is ~/BLM_inits/YYYY-MM-DD_hh(h)mm(m)ss(s) \\
        *e.g.* ~/BLM_intis/2025-10-24_08h16m21s

        Parameters
        ----------
        mode: Literal['all', 'adc_counter_masks', 'settings']
            str assignment for what settings to restore
        
        Returns
        -------
        Print statement upon completion
        """
        # warn if theres no inits loaded AT ALL (then exit)
        conditions = [
            self._got_init_adc_counter_masks,
            self._got_init_settings,
            self._got_sector11
        ]
        if not any(conditions):
            warnings.warn("No initial settings loaded and so none restored.")
            return None
        
        # Create save dir
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d_%Hh%Mm%Ss")
        path = Path.cwd()
        inits_path = path / 'BLM_inits' / timestamp_str
        Path.mkdir(inits_path, parents=True, exist_ok=True)

        # Check state, cant restore inits if there are none
        conditions = [
            mode == 'all' or mode == 'adc_counter_masks',
            self._got_init_adc_counter_masks or self._got_sector11
        ]
        if all(conditions):
            print("saving adc_counter_masks to json...")
            with open(inits_path / 'init_adc_counter_offset_1.json', 'w') as f:
                json.dump(self.init_adc_counter_offset_1, f)
            with open(inits_path / 'init_adc_counter_window_1.json', 'w') as f:
                json.dump(self.init_adc_counter_window_1, f)
            with open(inits_path / 'init_adc_counter_offset_2.json', 'w') as f:
                json.dump(self.init_adc_counter_offset_2, f)
            with open(inits_path / 'init_adc_counter_window_2.json', 'w') as f:
                json.dump(self.init_adc_counter_window_2, f)
        elif not any([self._got_init_adc_counter_masks, self._got_sector11]):
            warnings.warn("Asked to write blm adc counter masks to json, but no inits loaded.")

        # Check state, cant restore inits if there are none
        conditions = [
            mode == 'all' or mode == 'settings',
            self._got_init_adc_counter_masks or self._got_sector11
        ]
        if all(conditions):
            print("saving blm settings to json...")
            with open(inits_path / 'init_mode.json', 'w') as f:
                json.dump(self.init_mode, f)
            with open(inits_path / 'init_Vgc.json', 'w') as f:
                json.dump(self.init_Vgc, f)
            with open(inits_path / 'init_att.json', 'w') as f:
                json.dump(self.init_att, f)
            with open(inits_path / 'init_decay_Vgc.json', 'w') as f:
                json.dump(self.init_decay_Vgc, f)
            with open(inits_path / 'init_decay_att.json', 'w') as f:
                json.dump(self.init_decay_att, f)
        elif not any([self._got_init_adc_counter_masks, self._got_sector11]):
            warnings.warn("Asked to write blm settings to json, but no inits loaded.")

        return print("All loaded inits written to JSON!")
    # ----------------------------------------------------------------------------------------------------------
    def restore_from_json(self, mode: Literal['all', 'adc_counter_masks', 'settings'], path='BLM_defaults') -> None:
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
        
        Returns
        -------
        Print statement upon completion
        """


        # Check state, cant restore inits if there are none
        if any([mode == 'all', mode == 'adc_counter_masks']):
            # Check PVs are loaded, and if not, load them
            if not self._got_adc_counter_mask_PVs:
                self.get_adc_counter_mask_PVs()
            # Try to read each json, the restore just that PVs defaults in each try block
            # This way, if the json does not exist, we dont waste time trying to also write to PVs
            print("reading and restoring adc_counter_masks from json...")
            try:
                with open(os.path.join(path, 'init_adc_counter_offset_1.json'), 'r') as f: 
                    self.default_adc_counter_offset_1 = json.load(f)
                for key in self.default_adc_counter_offset_1:
                    self.adc_counter_offset_1[key].put(self.default_adc_counter_offset_1[key])
                    while self.adc_counter_offset_1[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_adc_counter_window_1.json'), 'r') as f: 
                    self.default_adc_counter_window_1 = json.load(f)
                for key in self.default_adc_counter_window_1:
                    self.adc_counter_window_1[key].put(self.default_adc_counter_window_1[key])
                    while self.adc_counter_window_1[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_adc_counter_offset_2.json'), 'r') as f: 
                    self.default_adc_counter_offset_2 = json.load(f)
                for key in self.default_adc_counter_offset_2:
                    self.adc_counter_offset_2[key].put(self.default_adc_counter_offset_2[key])
                    while self.adc_counter_offset_2[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_adc_counter_window_2.json'), 'r') as f: 
                    self.default_adc_counter_window_2 = json.load(f)
                for key in self.default_adc_counter_window_2:
                    self.adc_counter_window_2[key].put(self.default_adc_counter_window_2[key])
                    while self.adc_counter_window_2[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())

        # Check state, cant restore inits if there are none
        if any([mode == 'all', mode == 'settings']):
            # Check PVs are loaded, and if not, load them  
            if not self._got_settings_PVs:
                self.get_settings_PVs()
            # Try to read each json, the restore just that PVs defaults in each try block
            # This way, if the json does not exist, we dont waste time trying to also write to PVs
            print("reading and restoring blm settings from json...")
            try:
                with open(os.path.join(path, 'init_mode.json'), 'r') as f: 
                    self.default_mode = json.load(f)
                self.mode.put(self.default_mode)
                while self.mode.put_complete:
                    time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_Vgc.json'), 'r') as f: 
                    self.default_Vgc = json.load(f)
                for key in self.default_Vgc:
                    self.Vgc[key].put(self.default_Vgc[key])
                    while self.Vgc[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_att.json'), 'r') as f: 
                    self.default_att = json.load(f)
                for key in self.default_att:
                    self.att[key].put(self.default_att[key])
                    while self.att[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_decay_Vgc.json'), 'r') as f: 
                    self.default_decay_Vgc = json.load(f)
                for key in self.default_decay_Vgc:
                    self.decay_Vgc[key].put(self.default_decay_Vgc[key])
                    while self.decay_Vgc[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())
            try:
                with open(os.path.join(path, 'init_decay_att.json'), 'r') as f: 
                    self.default_decay_att = json.load(f)
                for key in self.default_decay_att:
                    self.decay_att[key].put(self.default_decay_att[key])
                    while self.decay_att[key].put_complete:
                        time.sleep(self.__wait_time)
            except IOError:
                print(traceback.format_exc())

        return print("BLM Settings restored from JSON!")
    # ----------------------------------------------------------------------------------------------------------
    def restore_defaults(self, mode: Literal['all', 'adc_counter_masks', 'settings']) -> None:
        """
        Restores defaults from json. \\
        Simply an alias for restore_from_json() but with default path args.
        """
        self.restore_from_json(mode=mode)
        
        return None
