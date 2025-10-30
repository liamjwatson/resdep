from typing import Any, Union, Literal
import traceback
import datetime
import json
import warnings
import epics
import time
import os

class epicsBLMs:
    """
    A libera object which handles EPICS BLM PVs, values, states, and common functions \\
    *e.g.* get PVs, get initial values, restore defaults

    Methods
    -------
    get_loss_PVs() -> tuple[dict[str, Any], ...]
        Loads beam loss PVs associated with regular slow acquision (SA) 
        and the two ADC counter masks
        Returns dicts of PVs with keys of form "{sector}{section}", *e.g.* '11A'

    get_adc_counter_mask_PVs() -> tuple[dict[str, Any], ...]
        Loads PVs associated with adc counter masks (offset and window for masks 1 & 2)
        Returns dicts of PVs with keys of form "{sector}", *e.g.* '7'
    
    get_settings_PVs() -> tuple[dict[str, Any], ...]
        Loads PVs associated with BLM settings (Vgc = gain voltage, att = attenuation)
        Returns dicts of PVs with keys of form "{sector}{section}", *e.g.* '5B'

    get_init_adc_counter_masks(self,) -> tuple[dict[str, float |None], ...], | None:
        Grabs the initial (not default, **initial**, *i.e.* at the time of calling this method)
        values of the adc counter masks (offset and window for masks 1 & 2)
        Returns dicts of values with keys of form "{sector}", *e.g.* '7'
    
    get_init_settings(self,) -> tuple[dict[str, float| None], ...] | None:
        Grabs the initial (not default, **initial**, *i.e.* at the time of calling this method)
        BLM settings (Vgc = gain voltage, att = attenuation)
        Returns dicts of values with keys of form "{sector}", *e.g.* '7'

    get_sector11(self, ) -> tuple[dict[str, Any], ...] | Any
        Loads all PVs and initial values from the methods list above 
        but only for sector 11 (upstream of the scrapers)
        Returns dicts of both PVs and initial values with appropriate keys
        (see above functions)

    restore_inits(mode='all', 'settings', or 'adc_counter_masks') -> None
        Restores the desired PVs to the stored initial values
        Prints when done
        
    inits_to_json(mode='all', 'settings', or 'adc_counter_masks') -> None
        Writes desired inits to json file in ~/BLM_settings/... 
        Prints when done
    
    restore_from_json(mode='all', 'settings', or 'adc_counter_masks', path: str) -> None
        Restores the desired PVs from saved JSON files
        Prints when done
    
    restore_defaults(mode='all') -> None
        Alias for restore_from_json(), but for stored master default JSONs
        Prints when done

    """
    def __init__(self, ):
        # states
        self._got_loss_PVs              : bool = False
        self._got_settings_PVs          : bool = False
        self._got_init_settings         : bool = False
        self._got_adc_counter_mask_PVs  : bool = False
        self._got_init_adc_counter_masks: bool = False
        self._got_sector11              : bool = False
        self._restored                  : bool = False

        # initialise dictionaries
        # using "flat is better than nested" approach, all dicts have the same keys
        #   of form {sector}{section}, e.g. "6B"
        #   except for the adc_counter_offset|window which are per IOC (so the key is just {sector})
        # PVs
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

        # initial values
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

        # default values
        self.default_mode                  : Union[str, None] = None
        self.default_Vgc                   : dict[str, float] = {}
        self.default_att                   : dict[str, float] = {}
        self.default_decay_Vgc             : dict[str, float] = {}
        self.default_decay_att             : dict[str, float] = {}
        self.default_adc_counter_offset_1  : dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_1  : dict[str, Union[float, None]] = {}
        self.default_adc_counter_offset_2  : dict[str, Union[float, None]] = {}
        self.default_adc_counter_window_2  : dict[str, Union[float, None]] = {}

        # wait time between PV calls / assignments to not flood system
        self.__wait_time = 0.1

    #
    # ----------------------------------------------------------------------------------------------------------
    def get_loss_PVs(self, ) -> tuple[dict[str, Any], ...]:
        """
        Loads all loss PVs (regular slow acquisition [SA] and loss from the two ADC counter masks)
        from all sectors and returns dictionaries (of PVs) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '11A' 
        """

        # grab PVs in loop
        for sector in range(1,14+1,1):
            for section in ['A', 'B']:
                self.loss[f"{sector}{section}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:SIGNALS_SA_{section}_MONITOR")
                self.loss[f"{sector}{section}"].wait_for_connection()
                self.adc_counter_loss_1[f"{sector}{section}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:counter.{section}1")
                self.adc_counter_loss_1[f"{sector}{section}"].wait_for_connection()
                self.adc_counter_loss_2[f"{sector}{section}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:counter.{section}2")
                self.adc_counter_loss_2[f"{sector}{section}"].wait_for_connection()
        
        # update state
        self._got_loss_PVs = True

        return self.loss, self.adc_counter_loss_1, self.adc_counter_loss_2
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_adc_counter_mask_PVs(self, ) -> tuple[dict[str, Any],...]:
        """
        Loads all adc counter masks (offset + window -- 1 & 2) PVs from all sectors and returns dictionaries (of PVs) \\
        Keys for each dictionary are of the form: {sector}... \\
        *e.g.* '11A' 
        """

        # grab PVs in loop
        for sector in range(1,14+1,1):
            self.adc_counter_offset_1[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c1:offset_sp")
            self.adc_counter_offset_1[f"{sector}"].wait_for_connection()
            self.adc_counter_window_1[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c1:window_sp")
            self.adc_counter_window_1[f"{sector}"].wait_for_connection()
            self.adc_counter_offset_2[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c2:offset_sp")
            self.adc_counter_offset_2[f"{sector}"].wait_for_connection()
            self.adc_counter_window_2[f"{sector}"] = epics.pv.get_pv(f"SR{sector:02d}BLM01:adcmask_c2:window_sp")
            self.adc_counter_window_2[f"{sector}"].wait_for_connection()
        
        # update state
        self._got_adc_counter_mask_PVs = True

        return self.adc_counter_offset_1, self.adc_counter_window_1, self.adc_counter_offset_2, self.adc_counter_window_2
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_init_adc_counter_masks(self,) -> Union[tuple[dict[str, Union[float, None]], ...], None]:
        """
        Loads all initial ADC counter mask settings from all sectors and returns dictionaries (of values) \\
        Keys for each dictionary are of the form: {sector}{section}... \\
        *e.g.* '4B' 
        """

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

        # update states
        self._got_init_adc_counter_masks = True

        return self.init_adc_counter_offset_1, self.init_adc_counter_window_1, self.init_adc_counter_offset_2, self.init_adc_counter_window_2
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_settings_PVs(self, ) -> tuple[dict[str, Any], ...]:
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
                self.Vgc[f"{sector}{section}"] 		    = epics.pv.get_pv(f"SR{sector:02d}BLM01:bld:vgc:{section}_sp")
                self.Vgc[f"{sector}{section}"].wait_for_connection()
                self.att[f"{sector}{section}"] 		    = epics.pv.get_pv(f"SR{sector:02d}BLM01:att:{section}_sp")
                self.att[f"{sector}{section}"].wait_for_connection()
                self.decay_Vgc[f"{sector}{section}"] 	= epics.pv.get_pv(f"SR{sector:02d}BLM01:DCY:bld:vgc:{section}")
                self.decay_Vgc[f"{sector}{section}"].wait_for_connection()
                self.decay_att[f"{sector}{section}"] 	= epics.pv.get_pv(f"SR{sector:02d}BLM01:DCY:att:{section}")
                self.decay_att[f"{sector}{section}"].wait_for_connection()

        # mode: auto, injection or decay
        self.mode = epics.pv.get_pv("SR00BLM01:USER_MODE_SELECTION_CMD")
        self.mode.wait_for_connection()
        
        # update state
        self._got_settings_PVs = True

        return self.Vgc, self.att, self.decay_Vgc, self.decay_att
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_init_settings(self,) -> Union[tuple[dict[str, float], ...], None]:
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

        return self.init_Vgc, self.init_att, self.init_decay_Vgc, self.init_decay_att
    
    #
    # ----------------------------------------------------------------------------------------------------------
    def get_sector11(self, ) -> Union[tuple[dict[str, Any], ...], Any]:
        """
        Loads PVs and initial settings from sector 11 and returns as dictionaries with keys 11A, 11B \\
        Note: mode is assigned: {0: not set, 1: injection, 2: decay, 3: auto}
        """

        # Check state, dont want to grab inits if they've already been changed
        if self._got_sector11:
            print('Call to get_sector11() STOPPED - already called, will overwrite initital values.')
            return None 

        # grab PVs in loop
        for section in ['A', 'B']:
            self.loss[f'11{section}'] = epics.pv.get_pv(f"SR11BLM01:SIGNALS_SA_{section}_MONITOR")
            self.loss[f'11{section}'].wait_for_connection()
            self.adc_counter_loss_1[f"11{section}"] = epics.pv.get_pv(f"SR11BLM01:signals:counter.{section}1")
            self.adc_counter_loss_1[f"11{section}"].wait_for_connection()
            self.adc_counter_loss_2[f"11{section}"] = epics.pv.get_pv(f"SR11BLM01:signals:counter.{section}2")
            self.adc_counter_loss_2[f"11{section}"].wait_for_connection()
            self.Vgc[f'11{section}'] = epics.pv.get_pv(f"SR11BLM01:bld:vgc:{section}_sp")
            self.Vgc[f'11{section}'].wait_for_connection()
            self.att[f'11{section}'] = epics.pv.get_pv(f"SR11BLM01:att:{section}_sp")
            self.att[f'11{section}'].wait_for_connection()
            self.decay_Vgc[f'11{section}']  = epics.pv.get_pv(f"SR11BLM01:DCY:bld:vgc:{section}")
            self.decay_Vgc[f'11{section}'].wait_for_connection()
            self.decay_att[f'11{section}']  = epics.pv.get_pv(f"SR11BLM01:DCY:att:{section}")
            self.decay_att[f'11{section}'].wait_for_connection()
        self.adc_counter_offset_1["11"] = epics.pv.get_pv(f"SR11BLM01:adcmask_c1:offset_sp")
        self.adc_counter_offset_1["11"].wait_for_connection()
        self.adc_counter_window_1["11"] = epics.pv.get_pv(f"SR11BLM01:adcmask_c1:window_sp")
        self.adc_counter_window_1["11"].wait_for_connection()
        self.adc_counter_offset_2["11"] = epics.pv.get_pv(f"SR11BLM01:adcmask_c2:offset_sp")
        self.adc_counter_offset_2["11"].wait_for_connection()
        self.adc_counter_window_2["11"] = epics.pv.get_pv(f"SR11BLM01:adcmask_c2:window_sp")
        self.adc_counter_window_2["11"].wait_for_connection()
            
        # get mode PV
        self.mode = epics.pv.get_pv("SR00BLM01:USER_MODE_SELECTION_CMD")
        self.mode.wait_for_connection()

        # In this case, we also have to check if any of the sector 11 inits are stored
        # due to calls from other functions such as get_init_settings(). 
        # get init settings
        if not self._got_init_settings:
            self.init_mode = self.mode.get()
            time.sleep(self.__wait_time)
            for key in ['11A', '11B']:
                self.init_Vgc[key] = self.Vgc[key].get()
                time.sleep(self.__wait_time)
                self.init_att[key] = self.att[key].get()
                time.sleep(self.__wait_time)
                self.init_decay_Vgc[key] = self.decay_Vgc[key].get()
                time.sleep(self.__wait_time)
                self.init_decay_att[key] = self.decay_att[key].get()
                time.sleep(self.__wait_time)
        # get counter masks inits
        if not self._got_init_adc_counter_masks:
            self.init_adc_counter_offset_1["11"] = self.adc_counter_offset_1["11"].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_window_1["11"] = self.adc_counter_window_1["11"].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_offset_2["11"] = self.adc_counter_offset_2["11"].get()
            time.sleep(self.__wait_time)
            self.init_adc_counter_window_2["11"] = self.adc_counter_window_2["11"].get()
            time.sleep(self.__wait_time)

        # update state
        self._got_sector11 = True

        return (self.loss, self.adc_counter_loss_1, self.adc_counter_loss_2,
                self.mode, self.init_mode,
                self.Vgc, self.att, self.decay_Vgc, self.decay_att, 
                self.init_Vgc, self.init_att, self.init_decay_Vgc, self.init_decay_att,
                self.adc_counter_offset_1, self.adc_counter_window_1, 
                self.adc_counter_offset_2, self.adc_counter_window_2,
                self.init_adc_counter_offset_1, self.init_adc_counter_window_1, 
                self.init_adc_counter_offset_2, self.init_adc_counter_window_2
                )
    #
    # ----------------------------------------------------------------------------------------------------------
    def restore_inits(self, mode: Literal['all', 'adc_counter_masks', 'settings']):
        """
        Restores all (loaded) initial settings from all sectors and returns dictionaries (of values) \\
        Note: mode is assigned: {0: not set, 1: injection, 2: decay, 3: auto}

        Parameters
        ----------
        mode: Literal['all', 'adc_counter_masks', 'settings']
            str assignment for what settings to restore
        
        Returns
        -------
        Print statement upon completion
        """
        # warn if theres no inits loaded AT ALL
        conditions = [
            self._got_init_adc_counter_masks,
            self._got_init_settings,
            self._got_sector11
        ]
        if not any(conditions):
            warnings.warn("No initial settings loaded and so none restored.")
            pass

        # Check state, cant restore inits if there are none.
        conditions = [
            
        ]
        if all(
            [mode == 'all' or mode == 'adc_counter_masks',
            self._got_init_adc_counter_masks or self._got_sector11]
            ):
            print("restoring adc_counter_masks...")
            for key in self.adc_counter_offset_1:
                self.adc_counter_offset_1[key].put(self.init_adc_counter_offset_1[key])
                while self.adc_counter_offset_1[key].put_complete:
                    time.sleep(self.__wait_time)
                self.adc_counter_window_1[key].put(self.init_adc_counter_window_1[key])
                while self.adc_counter_window_1[key].put_complete:
                    time.sleep(self.__wait_time)
                self.adc_counter_offset_2[key].put(self.init_adc_counter_offset_2[key])
                while self.adc_counter_offset_2[key].put_complete:
                    time.sleep(self.__wait_time)
                self.adc_counter_window_2[key].put(self.init_adc_counter_window_2[key])
                while self.adc_counter_window_2[key].put_complete:
                    time.sleep(self.__wait_time)
        elif all(
            [mode == 'all' or mode == 'settings',
            not self._got_init_settings,
            not self._got_sector11]
            ):
            warnings.warn("Asked to restore adc counter mask settings, but no inits loaded.")

        # Check state, cant restore inits if there are none
        if all(
            [mode == 'all' or mode == 'settings',
            self._got_init_adc_counter_masks or self._got_sector11]
            ):
            self.mode.put(self.init_mode)
            while self.mode.put_complete:
                time.sleep(self.__wait_time)
            for key in self.Vgc:
                self.Vgc[key].put(self.init_Vgc[key])
                while self.Vgc[key].put_complete:
                    time.sleep(self.__wait_time)
                self.att[key].put(self.init_att[key])
                while self.att[key].put_complete:
                    time.sleep(self.__wait_time)
                self.decay_Vgc[key].put(self.init_decay_Vgc[key])
                while self.decay_Vgc[key].put_complete:
                    time.sleep(self.__wait_time)
                self.decay_att[key].get(self.init_decay_att[key])
                while self.decay_att[key].put_complete:
                    time.sleep(self.__wait_time)
        elif all(
            [mode == 'all' or mode == 'settings',
            not self._got_init_adc_counter_masks,
            not self._got_sector11]
            ):
            warnings.warn("Asked to restore blm settings, but no inits loaded.")

        # update state
        self._restored = True

        return print("BLM Settings restored!")
    #
    # ----------------------------------------------------------------------------------------------------------
    def inits_to_json(self, mode: Literal['all', 'adc_counter_masks', 'settings']):
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
        inits_path = os.path.join('BLM_inits', timestamp_str)
        os.makedirs(inits_path, exist_ok=True)

        # Check state, cant restore inits if there are none
        conditions = [
            mode == 'all' or mode == 'adc_counter_masks',
            self._got_init_adc_counter_masks or self._got_sector11
        ]
        if all(conditions):
            print("saving adc_counter_masks to json...")
            with open(os.path.join(inits_path, 'init_adc_counter_offset_1.json'), 'w') as f:
                json.dump(self.init_adc_counter_offset_1, f)
            with open(os.path.join(inits_path, 'init_adc_counter_window_1.json'), 'w') as f:
                json.dump(self.init_adc_counter_window_1, f)
            with open(os.path.join(inits_path, 'init_adc_counter_offset_2.json'), 'w') as f:
                json.dump(self.init_adc_counter_offset_2, f)
            with open(os.path.join(inits_path, 'init_adc_counter_window_2.json'), 'w') as f:
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
            with open(os.path.join(inits_path, 'init_mode.json'), 'w') as f:
                json.dump(self.init_mode, f)
            with open(os.path.join(inits_path, 'init_Vgc.json'), 'w') as f:
                json.dump(self.init_Vgc, f)
            with open(os.path.join(inits_path, 'init_att.json'), 'w') as f:
                json.dump(self.init_att, f)
            with open(os.path.join(inits_path, 'init_decay_Vgc.json'), 'w') as f:
                json.dump(self.init_decay_Vgc, f)
            with open(os.path.join(inits_path, 'init_decay_att.json'), 'w') as f:
                json.dump(self.init_decay_att, f)
        elif not any([self._got_init_adc_counter_masks, self._got_sector11]):
            warnings.warn("Asked to write blm settings to json, but no inits loaded.")

        return print("All loaded inits written to JSON!")
    #
    # ----------------------------------------------------------------------------------------------------------
    def restore_from_json(self, mode: Literal['all', 'adc_counter_masks', 'settings'], path='BLM_defaults'):
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
    #
    # ----------------------------------------------------------------------------------------------------------
    def restore_defaults(self, mode: Literal['all', 'adc_counter_masks', 'settings']):
        """
        Restores defaults from json. \\
        Simply an alias for restore_from_json() but with default path args.
        """
        self.restore_from_json(mode=mode)
        return None