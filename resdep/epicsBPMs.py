"""
Classes for beam position monitors (BPMs)
"""
"""
██████╗ ███████╗ █████╗ ███╗   ███╗    ██████╗  ██████╗ ███████╗██╗████████╗██╗ ██████╗ ███╗   ██╗    ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ ███████╗
██╔══██╗██╔════╝██╔══██╗████╗ ████║    ██╔══██╗██╔═══██╗██╔════╝██║╚══██╔══╝██║██╔═══██╗████╗  ██║    ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝
██████╔╝█████╗  ███████║██╔████╔██║    ██████╔╝██║   ██║███████╗██║   ██║   ██║██║   ██║██╔██╗ ██║    ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝███████╗
██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║    ██╔═══╝ ██║   ██║╚════██║██║   ██║   ██║██║   ██║██║╚██╗██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗╚════██║
██████╔╝███████╗██║  ██║██║ ╚═╝ ██║    ██║     ╚██████╔╝███████║██║   ██║   ██║╚██████╔╝██║ ╚████║    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║███████║
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝    ╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Union
from pathlib import Path
import warnings
import logging, traceback
import json
import numpy as np
import numpy.typing as npt
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

        # --- position units for each EPICS readback
        # (different bpms have different EPICS engineering units)
        self.position_unit: str         = "Unspecified"
        self.position_unit_scale: float = 1

        # drift space between bpms
        # keys: `bpm1|bpm2`. See your invoked instance for `bpm` naming scheme.
        self.bpm_separations: Union[dict[str, float], None] = None

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
    def calculate_angles(self, loop_around: bool = False) -> tuple[dict[str, npt.NDArray[np.floating]], ...]:
        """
        Calculates yaw (angle in *x*) and pitch (angle in *y*) between each BPM in *micro radians*\\
        Schematic (angle calculated is `@`):
                  
                      pos 1                       
            ┌───────────x────┐                    
            └───────────┬────┘BPM n     Downstream
                       /│                   │     
                      /@│                   │     
                     /  │                   │     
                    /   │                   │     
                   /    │                   │     
                  /     │                   │     
                 /      │                   │     
            ┌───▼───────▼────┐              ▼     
            └───x────────────┘BPM n+1    Upstream 
             pos 2                                
                
        Parameters
        ----------
        loop_around: bool
            Enables angle calculation between the last and first BPM (in the storage ring for instance). \\
            Default: `False`

        Returns
        -------
        yaw: dict[str, npt.NDArray[np.floating]]
            Angle in horizontal plane *x* between two neighbouring BPMs. \\
            Units: *micro radians* \\
            keys: `bpm1|bpm2`. See your invoked instance for `bpm` naming scheme.
        pitch: dict[str, npt.NDArray[np.floating]]
            Angle in vertical plane *y* between two neighbouring BPMs. \\
            Units: *micro radians* \\
            keys: `bpm1|bpm2`. See your invoked instance for `bpm` naming scheme.
        """

        print(f"Calculating pitch and yaw. Input units: {self.position_unit} ({self.position_unit_scale})")

        # generate position dict keys
        bpms = list(self.x_position.keys())

        if self.bpm_separations is None:
            raise AttributeError("bpm_separations (between bpms) not defined in BPM class definition.")

        yaw             : dict[str, npt.NDArray[np.floating]] = {}
        pitch           : dict[str, npt.NDArray[np.floating]] = {}
        position_arrays : dict[str, npt.NDArray[np.floating]] = {}
        angle_dicts     : list[dict] = [yaw, pitch]
        positions       : list[dict] = [self.x_position, self.y_position]

        for position, angle_dict in zip(positions, angle_dicts):
            # convert list[float] (nm) -> npt.NDArray[np.floating] (m)
            for bpm, values in position.items():
                position_arrays[bpm] = np.array(values) * self.position_unit_scale

            for index, bpm in enumerate(position_arrays):
                try:
                    next_bpm = bpms[index+1]
                    key      = f"{bpm}|{next_bpm}"
                    angle_dict[key] = 1e6 * np.arctan((position_arrays[next_bpm] - position_arrays[bpm]) / self.bpm_separations[key])
                except IndexError:
                    break

            if loop_around:
                last_bpm    = bpms[-1]
                first_bpm   = bpms[0]
                key         = f"{last_bpm}|{first_bpm}"
                angle_dict[key] = 1e6 * np.arctan((position_arrays[first_bpm] - position_arrays[last_bpm]) / self.bpm_separations[key])

        return yaw, pitch
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

    Position units (EPICS): *nanometer*
    """
    def __init__(self, ) -> None:
        super().__init__()

        self.position_unit          = "nm"
        self.position_unit_scale    = 1e-9 # m, i.e. nanometers

        self.generate_bpm_separations()

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    def generate_bpm_separations(self,) -> None:
        """
        BPM locations:
        1:  2.304 m (after straight)
        2:  3.884 m (after quad 1)
        3:  6.020 m (after bend 1)
        4:  7.901 m (after sextapole 4)
        5:  9.420 m (before bend 2)
        6: 11.556 m (after bend 2)
        7: 13.125 m (before next straight)

        Distance between sectors / straights (BPM 7-->1)
        Straights [1,...,5] : 4.422 m
        Straights [6,7]     : 2.266 m 
        Straights [8,...,14]: 4.422 m
        """
        # --- generate bpm separations
        # NOTE: this doesn't quite add up to 216 m. About 3 m out, need to check where the discrepancy is
        # [1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:1] (most sectors)
        bpm_separations_per_sector = [1.58, 2.1358, 1.881, 1.519, 2.1356, 1.569, 4.422] # m
        bpm_separations_list = []
        for loop_counter in range(1,14+1,1):
            bpm_separations_list += bpm_separations_per_sector
        # populate keys
        bpm_keys            : list[str] = []
        bpm_separation_keys : list[str] = []
        for sector in range(1, 14+1, 1):
            for bpm in range(1, 7+1, 1):
                bpm_keys.append(f"{sector}:{bpm}")
        try:
            for index, bpm in enumerate(bpm_keys):
                next_bpm = bpm_keys[index+1]
                bpm_separation_keys.append(f"{bpm}|{next_bpm}")
        except IndexError:
            last_bpm    = bpm_keys[-1]
            first_bpm   = bpm_keys[0]
            bpm_separation_keys.append(f"{last_bpm}|{first_bpm}")

        # create separations dictionary
        self.bpm_separations = {}
        for index, bpms in enumerate(bpm_separation_keys):
            self.bpm_separations[bpms] = bpm_separations_list[index]
        # correct for sectors 6,7 with different BPM separations in straight
        difference_in_straights = 4.422 - 2.266 # m
        for sector in [6,7]:
            self.bpm_separations[f"{sector-1}:6|{sector-1}:7"]  +=  difference_in_straights/2
            self.bpm_separations[f"{sector-1}:7|{sector}:1"]    += -difference_in_straights
            self.bpm_separations[f"{sector}:1|{sector}:2"]      +=  difference_in_straights/2

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
                self.intensity_PVs[f"{sector}:{bpm}"]  = epics.pv.get_pv(f"SR{sector:02d}BPM{bpm:02d}:SA_SUM_MONITOR", connect=True)

        return None

class MX3_BPMs(BPMs): 
    """
    Collection of MX3 BPMs in the optical front end / photon delivery system (PDS) \\
    Subclass of BPMs

    Position units (EPICS): *micron* \\ 
    Intensity units: *nano amp*
    """
    def __init__(self, ) -> None:
        super().__init__()
        
        self.position_unit          = "um"
        self.position_unit_scale    = 1e-6 # m, i.e. microns

        bpm_pos = {
            "1": 18.575, # m
            "2": 26.650, # m
            "5": 34.960, # m
            "3": 36.610, # m, approx
            "4": 36.870  # m, approx
        }
        self.bpm_separations = {
             "1|2": bpm_pos["2"] - bpm_pos["1"],
             "2|5": bpm_pos["5"] - bpm_pos["2"],
             "5|3": bpm_pos["3"] - bpm_pos["5"],
             "3|4": bpm_pos["4"] - bpm_pos["3"]
        }

        return None
    # -----------------------------------------------------------------------------------------------------------------------
    @BPMs._decorator_connect_state
    def connect(self, ) -> None:
        """
        Load `x_position`, `y_position`, and `intensity` PVs. Also initates storage attributes (dicts) \\
        Key format: `BPM number`, e.g. `"4"` 
        
        `|-------------------- Hutch C -------------------------|-- Hutch B --|-- Hutch A --|-- SR ---` \\
        `|Detector <-- BPM 4 <----- BPM 3 <----------- BPM 5 <------ BPM 2 <------ BPM 1 <---- Beam --`
        """

        for bpm in [1, 2, 5, 3, 4]:
            if bpm % 2 == 0: # is even
                self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:PosX:MeanValue_RBV", connect=True)
                self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:PosY:MeanValue_RBV", connect=True)
                self.intensity_PVs[f"{bpm}"]  = epics.pv.get_pv(f"MX3BPM{bpm:02d}DAQ01:SumAll:MeanValue_RBV", connect=True)
            else: # is odd
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
