"""
Classes for beam position monitors (BPMs)
"""

"""
██████╗ ███████╗ █████╗ ███╗   ███╗    
██╔══██╗██╔════╝██╔══██╗████╗ ████║    
██████╔╝█████╗  ███████║██╔████╔██║    
██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║    
██████╔╝███████╗██║  ██║██║ ╚═╝ ██║    
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝    
██████╗  ██████╗ ███████╗██╗████████╗██╗ ██████╗ ███╗   ██╗    
██╔══██╗██╔═══██╗██╔════╝██║╚══██╔══╝██║██╔═══██╗████╗  ██║    
██████╔╝██║   ██║███████╗██║   ██║   ██║██║   ██║██╔██╗ ██║    
██╔═══╝ ██║   ██║╚════██║██║   ██║   ██║██║   ██║██║╚██╗██║    
██║     ╚██████╔╝███████║██║   ██║   ██║╚██████╔╝██║ ╚████║    
╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝    
███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗ ███████╗
████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝
██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝███████╗
██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗╚════██║
██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║███████║
╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
"""                     

from abc import ABC, abstractmethod
from typing import Callable, Union, Optional
from pathlib import Path
import warnings
import logging
import traceback
import json
import numpy as np
import numpy.typing as npt
import epics


class BPMs(ABC):
    """
    EPICS BPM abstract base class that can store families of BPMs

    Current scope is only for storage ring and MX3 BPMs, and TBPMs.

    Attributes
    ----------
    x_position_PVs, y_position_PVs, intensity_PVs: dict[str, epics.pv.PV]
        Dictionary of PVs accessing the x/y-position or intensity readback. 
        See your subclass for key format.
    x_position, y_position, intensity: dict[str, list[float]]
        Dictionary of x/y-position or intensity readback values for storage 
        (to append from `PV.get()`). See your subclass for key format.
    position_unit: str
        Units of the position values. Typically nm or microns.
    position_unit_scale: float
        Scientific units representing the scale, e.g. nm = 1e-9.
    bpm_separations: dict[str, float] | None
        Separation between adjacent BPMs in meters. Keys follow `bpm1|bpm2` 
        in reference to your subclass's keys.

    Methods
    -------
    connect
        Connect to EPICS PVs. 
        Abstract method -- Must be overwritten and configured in your subclass.
    calculate_angles
        Calculates the angle of the beam (yaw and pitch) between adjacent BPMs.
        Requires definition of position_unit, 
        position_unit_scale and bpm_separations.
    record_data
        Appends readback of PV to storage dictionary.
        e.g. `x_position` <-- `x_position_PVs`
    save_data
        Saves all storage dictionaries to passed `path` arg as .json.
    load_from_finished_experiment
        Loads saved .json files at passed arg `path`. 
        Populates storage dictionaries in BPM instance.

    Warning
    -------
    `connect` is an abstract method that must be overwritten in the subclass.
    In this method, you should populate the dictionaries: 
    `x_position_PVs`, `y_position_PVs`, and `intensity_PVs`,
    using a [`str`][] key and an `epics.pv` value.

    Similarly, you must define `position_unit`, `position_unit_scale` 
    and `bpm_separations` in the subclass `__init__` if you want to call 
    [`calculate_angles`][resdep.epicsBPMs.BPMs.calculate_angles].

    Examples
    --------

    ```py title="Define subclass"
    Foo_BPMs(BPMs): ...
        def __init__(self):
            # define units (x/y pos from EPICS readback)
            position_unit       = "nm"
            position_unit_scale = 1e-9
            # populate bpm_separations
            bpm_separations["1|2"] = 1.2345 # meters
            bpm_separations["2|3"] = 2.3456 # meters
            bpm_separations["3|4"] = ...
    # override abstract class `connect`
        def connect(self,): 
            # define PV names
            for bpm in [1,2]:
                x_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"SR01BPM0{bpm}:x_position", connect=True
                )
                y_position_PVs =...
                intensity_PVs =...
    ```

    ```py title="Instancing"
    foo_bpms = Foo_BPMs()
    foo_bpms.connect()

    for i in range(60):
        foo_bpms.record_data()
        time.sleep(1)
    foo_bpms.save_data()

    pitch, yaw = foo_bpms.calculate_angles()
    plt.plot(yaw["1|2"]) # plot yaw between bpm 1 and bpm 2
    ```
    """                                                                     
                    
    def __init__(
        self,
    ) -> None:

        # --- PVs
        self.x_position_PVs: dict[str, epics.pv.PV]
        self.y_position_PVs: dict[str, epics.pv.PV]
        self.intensity_PVs: dict[str, epics.pv.PV]
        self._pv_dicts: list[dict[str, epics.pv.PV]]

        # --- data
        self.x_position: dict[str, list[float]] 
        self.y_position: dict[str, list[float]]
        self.intensity: dict[str, list[float]]
        self._value_dicts: list[dict[str, list[float]]]

        # --- position units for each EPICS readback
        # (different bpms have different EPICS engineering units)
        self.position_unit: str = "Unspecified"
        self.position_unit_scale: float = 1

        # drift space between bpms
        # keys: `bpm1|bpm2`. See your invoked instance for `bpm` naming scheme.
        self.bpm_separations: Optional[dict[str, float]] = None

        # All PVs disconnected flag for handling `record_data()` etc.
        self.disconnected_bpms: list[str] = []
        self.all_disconnected: bool = False

        return None

    # -------------------------------------------------------------------------
    def __init_subclass__(cls) -> None:
        """
        Automatically decorate abstract method `connect` 
        with private decorator function which populates the storage dicts.
        """
        super().__init_subclass__()
        cls.connect = cls._connect_decorator(cls.connect)

    # -------------------------------------------------------------------------
    @abstractmethod
    def connect(
        self,
    ): ...
    # -------------------------------------------------------------------------
    @staticmethod
    def _connect_decorator(function: Callable):
        """
        Decorates connect with a state check. Only want to grab PVs once. 
        Populates PV and storage dicts with keys.
        """

        def wrapper(self: BPMs, *args, **kwargs):

            # check if PVs have loaded
            pv_attrs = [
                "x_position_PVs",
                "y_position_PVs",
                "intensity_PVs"
            ]
            if all([hasattr(self, attr) for attr in pv_attrs]):
                logging.warning(
                    "Request to connect, but BPM PVs already loaded!"
                )
                return None

            # --- PVs
            self.x_position_PVs = {}
            self.y_position_PVs = {}
            self.intensity_PVs = {}
            self._pv_dicts = [
                self.x_position_PVs,
                self.y_position_PVs,
                self.intensity_PVs,
            ]

            # run connect
            function(self, *args, **kwargs)

            # exit early if all BPMs are disconnected
            bpms_connected: list[bool] = [
                pv.connected for pv in self.x_position_PVs.values()
            ]
            if not any(bpms_connected):
                self.all_disconnected = True
                raise ConnectionRefusedError(
                    f"All {self.__class__.__name__} PVs disconnected"
                )

            # remove "not connected" PVs from dictionaries, so that they are 
            # not called in `.get()` or `.calculate...` funcitons
            # `connect()` should already warn "couldn't connect" to console
            for dictionary in self._pv_dicts:
                for bpm, pv in dictionary.items():
                    if not pv.connected:
                        del dictionary[bpm]
                        self.disconnected_bpms.append(bpm)

            # --- initialise data stuctures
            self.x_position = {}
            self.y_position = {}
            self.intensity = {}
            self._value_dicts = [
                self.x_position,
                self.y_position,
                self.intensity,
            ]

            for bpm in self.x_position_PVs:
                self.x_position[bpm] = []
                self.y_position[bpm] = []
                self.intensity[bpm] = []

        return wrapper

    # -------------------------------------------------------------------------
    def calculate_angles(
        self, loop_around: bool = False
    ) -> tuple[dict[str, npt.NDArray[np.floating]], ...]:
        """
        Calculates yaw (angle in *x*) and pitch (angle in *y*) between 
        each BPM in *micro radians*.

        Parameters
        ----------
        loop_around: bool, default: False
            Enables angle calculation between the last and first BPM 
            (in the storage ring for instance).

        Returns
        -------
        yaw: dict[str, npt.NDArray[np.floating]]
            Angle in horizontal plane *x* between two neighbouring BPMs.
        pitch: dict[str, npt.NDArray[np.floating]]
            Angle in vertical plane *y* between two neighbouring BPMs.

        Notes
        -----
        - All angles are in units: *micro radians*.
        - [`dict`][] keys: `bpm1|bpm2`. 
            See your invoked instance for `bpm` naming scheme.

        Schematic
        ---------
        Schematic (angle calculated is `@`):

            +----------------+          Downstream
            |         pos 1  | BPM n        |
            +-----------▼----+              |
                       /.                   │
                      /@.                   │
                     /  .                   │
                    /   .                   │
                   /    .                   │
                  /     .                   │
                 /      .                   │
            +---▼------------+              |
            | pos 2          | BPM n+1      ▼
            +----------------+           Upstream
        """

        # check that x and y position dicts are the same length
        if len(self.x_position) != len(self.y_position):
            logging.warning(
                    "Storage dictionaries for x and y have "
                    + "a different number of keys. "
                    + "Be careful comparing data."
            )

        if self.bpm_separations is None:
            raise AttributeError(
                "bpm_separations (between bpms) not defined "
                + "in BPM subclass definition."
                + "Should be of type dict[str, float] "
                + "where keys are of format 'bpm1|bpm2'."
            )

        logging.info(
                "Calculating pitch and yaw. Input units: "
                + f"{self.position_unit} ({self.position_unit_scale})"
        )

        yaw: dict[str, npt.NDArray[np.floating]] = {}
        pitch: dict[str, npt.NDArray[np.floating]] = {}
        position_arrays: dict[str, npt.NDArray[np.floating]] = {}
        angles: list[dict] = [yaw, pitch]
        positions: list[dict] = [self.x_position, self.y_position]

        # generate position dict keys
        bpms = list(self.x_position.keys())

        for position, angle in zip(positions, angles):
            # convert list[float] (nm) -> npt.NDArray[np.floating] (m)
            for bpm, values in position.items():
                position_arrays[bpm] = (
                    np.array(values) * self.position_unit_scale
                )

            for index, bpm in enumerate(position_arrays):
                try:
                    next_bpm = bpms[index + 1]
                    key = f"{bpm}|{next_bpm}"
                    angle[key] = 1e6 * np.arctan(
                        (position_arrays[next_bpm] - position_arrays[bpm])
                        / self.bpm_separations[key]
                    )
                except IndexError:
                    # the end of the list has been reached
                    break

            if loop_around:
                last_bpm = bpms[-1]
                first_bpm = bpms[0]
                key = f"{last_bpm}|{first_bpm}"
                angle[key] = 1e6 * np.arctan(
                    (position_arrays[first_bpm] - position_arrays[last_bpm])
                    / self.bpm_separations[key]
                )

        return yaw, pitch

    # -------------------------------------------------------------------------
    def record_data(
        self,
    ) -> None:
        """
        Updates dictionary attributes (pos, intensity) with 
        values from `epics.PV.get()`.
        """
        if not hasattr(self, "x_position_PVs"):
            raise AttributeError(
                    "PVs not connected. "
                    + "Please call .connect() before record_data."
            )

        if len(self.x_position_PVs) == 0:
            raise ValueError(
                "No PVs connected. Call connect() before .record_data()"
            )

        for value_dict, pv_dict in zip(self._value_dicts, self._pv_dicts):
            for bpm, pv in pv_dict.items():
                value = pv.get(timeout=0.5)
                value_dict[bpm].append(value)

        return None

    # -------------------------------------------------------------------------
    def save_data(
        self,
        path: Optional[Path] = None,
    ) -> None:
        """
        Dumps `x`/`y_position` attributes to .json files in folder at `path`.

        Parameters
        ----------
        path: pathlib.Path
            Path to save folder
        """

        if self.all_disconnected:
            logging.warning(
                "PVs not connected/disconnected. No objects to save."
            )
            return None

        if path is None:
            path = Path.cwd() / "BPMs"
            warnings.warn(
                f"No path passed to save_position_data(). Saving to {path}."
            )
        elif not path.is_dir():
            path = path.parent / "BPMs"
            warnings.warn(
                "Path passed to save_position_data() points to a file. "
                + f"Saving to parent folder {path}."
            )

        with open(path / "x_position.json", "w") as f:
            json.dump(self.x_position, f)
        with open(path / "y_position.json", "w") as f:
            json.dump(self.y_position, f)
        with open(path / "intensity.json", "w") as f:
            json.dump(self.intensity, f)

        logging.info(
                f"{self.__class__.__name__} position and intensities saved!"
        )

        return None

    # -------------------------------------------------------------------------
    def load_from_finished_experiment(self, path: Path) -> None:
        """
        Loads attributes from saved .json files in a 
        finished experiment data folder.
        Each path should be to the specific BPM. 
        *e.g.* `path=".../1713h/BPMs/MX3/"`

        Parameters
        ----------
        path: Path
            Path to save folder

        Raises
        ------
        ValueError
            If path is a file, not a directory.
        """

        if not path.is_dir():
            raise ValueError(
                "Argument 'path' in BPM load_from_finished_experiment "
                + "is a file, not a directory."
            )

        with open(path / "x_position.json", "r") as f:
            self.x_position = json.load(f)
        with open(path / "y_position.json", "r") as f:
            self.y_position = json.load(f)
        with open(path / "intensity.json", "r") as f:
            self.intensity = json.load(f)

        return None


class SR_BPMs(BPMs):
    """
    Collection of storange ring BPMs.
    Keys of PV dicts follow syntax `{sector}{bpm_number}`.
    Subclass of [`BPMs`][resdep.epicsBPMs.BPMs]

    Position units (EPICS): *nanometer*
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.position_unit = "nm"
        self.position_unit_scale = 1e-9  # m, i.e. nanometers

        self._sectors: list[int] = [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
        ]
        # ! <----------------------------- PICK BACK UP HERE
        self._bpm_indicies = [
                1, 2, 3, 4, 5, 6, 7
        ]
        self.generate_bpm_separations()

        return None

    # -------------------------------------------------------------------------
    def generate_bpm_separations(
        self,
    ) -> None:
        """
        Generate a dictionary of the of separations between 
        each BPM in the storage ring.

        Info
        ----
        Called in `__init__`.
        Dict keys: `{bpm}|{next_bpm}`
        Based on the following information:

        BPM locations:

        1.  2.304 m (after straight)
        2.  3.884 m (after quad 1)
        3.  6.020 m (after bend 1)
        4.  7.901 m (after sextapole 4)
        5.  9.420 m (before bend 2)
        6. 11.556 m (after bend 2)
        7. 13.125 m (before next straight)

        Distance between sectors / straights (BPM 7-->1):

        - Straights [1,...,5] : 4.422 m
        - Straights [6,7]     : 2.266 m
        - Straights [8,...,14]: 4.422 m
        """
        # --- generate bpm separations
        # NOTE: this doesn't quite add up to 216 m. 
        # About 3 m out, need to check where the discrepancy is.
        # [1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:1] (most sectors)
        bpm_separations_per_sector = [
            1.58,
            2.1358,
            1.881,
            1.519,
            2.1356,
            1.569,
            4.422,
        ]  # m
        bpm_separations_list = []
        for _ in self._sectors:
            bpm_separations_list += bpm_separations_per_sector
        # populate keys
        bpm_keys: list[str] = []
        bpm_separation_keys: list[str] = []
        for sector in self._sectors:
            for bpm in self._bpm_indicies:
                bpm_keys.append(f"{sector}:{bpm}")
        try:
            for index, bpm in enumerate(bpm_keys):
                next_bpm = bpm_keys[index + 1]
                bpm_separation_keys.append(f"{bpm}|{next_bpm}")
        except IndexError: # end of list
            last_bpm = bpm_keys[-1]
            first_bpm = bpm_keys[0]
            bpm_separation_keys.append(f"{last_bpm}|{first_bpm}")

        # populate separations dictionary
        self.bpm_separations = {}
        for index, bpms in enumerate(bpm_separation_keys):
            self.bpm_separations[bpms] = bpm_separations_list[index]
        # correct for sectors 6,7 with different BPM separations in straight
        difference_in_straights = 4.422 - 2.266  # m
        for sector in [6, 7]:
            self.bpm_separations[f"{sector - 1}:6|{sector - 1}:7"] += (
                difference_in_straights / 2
            )
            self.bpm_separations[
                f"{sector-1}:7|{sector}:1"
            ] += -difference_in_straights
            self.bpm_separations[f"{sector}:1|{sector}:2"] += (
                difference_in_straights / 2
            )

        return None

    # -------------------------------------------------------------------------
    def connect(
        self,
    ) -> None:
        """
        Load `x_position`, `y_position` and `intensity` PVs.
        Key format: `sector:bpm`, *e.g.* `"11:4"`
        """

        for sector in range(1, 14 + 1, 1):
            for bpm in range(1, 7 + 1, 1):
                self.x_position_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BPM{bpm:02d}:SA_X_MONITOR",
                    connect=True,
                    timeout=0.5,
                )
                self.y_position_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BPM{bpm:02d}:SA_Y_MONITOR",
                    connect=True,
                    timeout=0.5,
                )
                self.intensity_PVs[f"{sector}:{bpm}"] = epics.pv.get_pv(
                    f"SR{sector:02d}BPM{bpm:02d}:SA_SUM_MONITOR",
                    connect=True,
                    timeout=0.5,
                )

        return None


class MX3_BPMs(BPMs):
    """
    Collection of MX3 BPMs in the optical front end / photon delivery system (PDS).

    Info
    ----
    - Position units (EPICS): *micron*
    - Intensity units: *nano amp*
    """             

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.position_unit = "um"
        self.position_unit_scale = 1e-6  # m, i.e. microns

        bpm_pos = {
            "1": 18.575,  # m
            "2": 26.650,  # m
            "5": 34.960,  # m
            "3": 36.610,  # m, approx
            "4": 36.870,  # m, approx
        }
        self.bpm_separations = {
            "1|2": bpm_pos["2"] - bpm_pos["1"],
            "2|5": bpm_pos["5"] - bpm_pos["2"],
            "5|3": bpm_pos["3"] - bpm_pos["5"],
            "3|4": bpm_pos["4"] - bpm_pos["3"],
        }

        return None

    # -------------------------------------------------------------------------
    def connect(
        self,
    ) -> None:
        """
        Load `x`/`y_position` and `intensity` PVs. Also initates storage attributes ([`dicts`][dict]). Key format: `BPM number`, e.g. `"4"`.


        Layout
        ------
        ```
            |-------------------- Hutch C -------------------------|-- Hutch B --|-- Hutch A --|-- SR ---
            |Detector <-- BPM 4 <----- BPM 3 <----------- BPM 5 <------ BPM 2 <------ BPM 1 <---- Beam --
        ```
        """

        for bpm in [1, 2, 5, 3, 4]:
            if bpm % 2 == 0:  # is even
                self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3DAQIOC{bpm:02d}:BPM0:PosX_RBV",
                    connect=True,
                    timeout=0.5,
                )
                self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3DAQIOC{bpm:02d}:BPM0:PosY_RBV",
                    connect=True,
                    timeout=0.5,
                )
                self.intensity_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3DAQIOC{bpm:02d}:BPM0:Int_RBV",
                    connect=True,
                    timeout=0.5,
                )
            else:  # is odd
                self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3BPM{bpm:02d}DAQ01:PosX:MeanValue_RBV",
                    connect=True,
                    timeout=0.5,
                )
                self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3BPM{bpm:02d}DAQ01:PosY:MeanValue_RBV",
                    connect=True,
                    timeout=0.5,
                )
                self.intensity_PVs[f"{bpm}"] = epics.pv.get_pv(
                    f"MX3BPM{bpm:02d}DAQ01:SumAll:MeanValue_RBV",
                    connect=True,
                    timeout=0.5,
                )

        return None


class TBPMs(BPMs):
    """
    Temperature BPMs upstream of MX3 front end
    """

    def __init__(self) -> None:
        super().__init__()

        return None

    # -------------------------------------------------------------------------
    def connect(
        self,
    ) -> None:
        """Load `x_position`, `y_position` and `intensity` PVs.
        Key format: `bpm`, *e.g.* `"2"`
        """
        for bpm in [1, 2]:
            self.x_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                f"SR04FE01BPM{bpm:02d}:X_POSITION_MONITOR",
                connect=True,
                timeout=0.5,
            )
            self.y_position_PVs[f"{bpm}"] = epics.pv.get_pv(
                f"SR04FE01BPM{bpm:02d}:Y_POSITION_MONITOR",
                connect=True,
                timeout=0.5,
            )
            self.intensity_PVs[f"{bpm}"] = epics.pv.get_pv(
                f"SR04FE01BPM{bpm:02d}:TEMPERATURE_SUM_MONITOR",
                connect=True,
                timeout=0.5,
            )

        return None


if __name__ == "__main__":
    print(
        "epicsBPMs contains an abstract class file 'BPMs' that is subclassed " 
        "by a specific BPM group."
    )
    print(
        "Examples include storage ring BPMs (SR_BPMs) and MX3 front end BPMs "
        "(MX3_BPMs)."
    )
    print(
        "Used to connect to PVs and record position data. "
        "Can also calculate angles (yaw/pitch) from collected data."
    )
    print("Run help(BPMs) or help(MX3_BPMs) after import for more details.")
