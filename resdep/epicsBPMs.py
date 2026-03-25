from abc import ABC, abstractmethod
from typing import Any, Callable, Union
from pathlib import Path
import warnings
import logging, traceback
import json
import epics

class BPMs(ABC):
    """
    EPICS BPM abstract base class that can store families of BPMs

    Current scope is only for storage ring and MX3 BPMs.
    """
    def __init__(self, ) -> None:

        # --- PVs
        self.x_position_PVs: dict[str, Any] = {}
        self.y_position_PVs: dict[str, Any] = {}
        self.intensity_PVs : dict[str, Any] = {}

        # --- data
        self.x_position: dict[str, list[float]] = {}
        self.y_position: dict[str, list[float]] = {}
        self.intensity : dict[str, list[float]] = {}

        # --- states
        self._got_PVs = False

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    @abstractmethod
    def connect(self, ): 
        pass
    # -----------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _decorator_connect_state(decorated: Callable):
        """
        Decorates connect with a state check. Only want to grab PVs once.
        """
        def wrapper(self,):

            if self._got_PVs:
                warnings.warn("Already grabbed BPM PVs.")
                return None
            
            # run connect
            decorated(self)

            for key in self.x_position_PVs:
                self.x_position[key] = []
                self.y_position[key] = []
                self.intensity[key]  = []

            self._got_PVs = True
        
        return wrapper
    # -----------------------------------------------------------------------------------------------------------------------
    def record_data(self, ) -> None:
        """
        Updates class scope dictionaries with values from `PV.get()`
        """

        for key in self.x_position_PVs:
            x_pos       = self.x_position_PVs[key].get()
            y_pos       = self.y_position_PVs[key].get()
            intensity   = self.intensity_PVs[key].get()

            self.x_position[key].append(x_pos)
            self.y_position[key].append(y_pos)
            self.intensity[key].append(intensity)

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    def save_data(self, path: Union[Path, None] = None, ) -> None:
        """
        Dumps `x`/`y_position` attributes to `.json` files in folder `path`

        Parameters
        ----------
        path: Path
            Path to save folder
        """

        if path is None:
            path = Path.cwd() / "BPMs"
            warnings.warn(f"No path passed to save_position_data(). Saving to {path}.")
        elif not path.is_dir():
            path = path.parent / "BPMs"
            warnings.warn(f"Path passed to save_position_data() points to a file. Saving to parent folder {path}.")

        with open(path / "x_position.json", "w") as f:
            json.dump(self.x_position, f)
        with open(path / "y_position.json", "w") as f:
            json.dump(self.y_position, f)
        with open(path / "intensity.json", "w") as f:
            json.dump(self.intensity, f)

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    def load_from_finished_experiment(self, path: Path) -> None:
        """
        Loads attributes from saved .json files in a finished experiment data folder. \\
        Each path should be to the specific BPM, i.e. `path=".../1713h/BPMs/MX3/"`
        """

        if not path.is_dir():
           raise ValueError("Argument 'path' in BPM load_from_finished_experiment is a file, not a directory.")

        try:
            with open(path / "x_position.json", "r") as f:
                self.x_position = json.load(f)
            with open(path / "y_position.json", "r") as f:
                self.y_position = json.load(f)
            with open(path / "intensity.json", "r") as f:
                self.intensity = json.load(f)

        except Exception:
            logging.error(traceback.format_exc())

        return None
    
class SR_BPMs(BPMs):
    """
    Collection of storange ring BPMs \\
    Keys of PV dicts follow syntax `{sector}{bpm_number}` \\
    Subclass of BPMs
    """
    def __init__(self, ) -> None:
        super().__init__()

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    @BPMs._decorator_connect_state
    def connect(self, ) -> None:
        """
        Load `x_position`, `y_position` and `intensity` PVs. Also initates storage attributes (dicts) \\
        Key format: `sector:bpm`, *e.g.* `"11:4"`
        """

        for sector in range(1, 14+1, 1):
            for bpm in range(1, 7+1, 1):
                self.x_position_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(f"SR{sector:02d}BPM{bpm:02d}:SA_X_MONITOR", connect=True)
                self.y_position_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(f"SR{sector:02d}BPM{bpm:02d}:SA_Y_MONITOR", connect=True)
                self.intensity_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(f"SR{sector:02d}BPM{bpm:02d}:SA_SUM_MONITOR", connect=True)

        return None

class MX3_BPMs(BPMs):
    """
    Collection of MX3 BPMs in the optical front end / photon delivery system (PDS) \\
    Subclass of BPMs
    """
    def __init__(self, ) -> None:
        super().__init__()

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    @BPMs._decorator_connect_state
    def connect(self, ) -> None:
        """
        Load `x_position`, `y_position`, and `intensity` PVs. Also initates storage attributes (dicts) \\
        Key format: `BPM number`, e.g. `"4"` 
        
        |-------------------- Hutch C -------------------------|-- Hutch B --|-- Hutch A --|-- SR --- \\
        Detector <------ BPM 4 <------ BPM 3 <------ BPM 5 <------ BPM 2 <------ BPM 1 <------ Beam
        """

        odd_BPMs  = [1, 3, 5]
        even_BPMs = [2, 4] # alias [best0, best1]

        for bpm in odd_BPMs:
            self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:PosX:MeanValue_RBV", connect=True)
            self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:PosY:MeanValue_RBV", connect=True)
            self.intensity_PVs[f"{bpm}"]  = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:SumAll:MeanValue_RBV", connect=True)

        for bpm in even_BPMs:
            self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3DAQIOC{bpm:02d}:BPM0:PosX_RBV", connect=True)
            self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3DAQIOC{bpm:02d}:BPM0:PosY_RBV", connect=True)
            self.intensity_PVs[f"{bpm}"]  = epics.pv.get_pv(f"MX3DAQIOC{bpm:02d}:BPM0:Int_RBV", connect=True)

        return None
    
class TBPMs(BPMs):
    """
    Temperature BPMs upstream of MX3 front end
    """
    def __init__(self) -> None:
        super().__init__()

        return None    
    # -----------------------------------------------------------------------------------------------------------------------
    @BPMs._decorator_connect_state
    def connect(self, ) -> None:

        for bpm in [1, 2]:
            self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"SR04FE01BPM{bpm:02d}:X_POSITION_MONITOR", connect=True)
            self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"SR04FE01BPM{bpm:02d}:Y_POSITION_MONITOR", connect=True)
            self.intensity_PVs[f"{bpm}"]  = epics.pv.get_pv(f"SR04FE01BPM{bpm:02d}:TEMPERATURE_SUM_MONITOR", connect=True)

        return None