from typing import Any
import time
import epics
import traceback


class Scraper():
    """
    Class object for *an individual* scraper \\
    Loads PVs, stores inital values, and houses member functions that move the scrapers.

    Parameters
    ----------
    direction: str
        Direction is one of "upper", "lower", "inner", "outer".
        Case invariant.

    Methods
    -------
    connect(direction: str) -> None:
        Connects relevant PVs and stores initial values

    move(position: float) -> None:
        Moves scraper to provided position

    moveOut() -> None:
        Moves scraper to default out position.

    EPICS Callbacks
    ---------------

    whileMoving() -> None:
        EPICS Callback for the MOTION_STATUS PV. Just prints to std.out if moving or stopped. 
    """
    def __init__(self, direction: str) -> None:
        # Constructor
        self._direction: str = direction.upper()

        is_acceptable_direction: list[bool] = [
            self._direction == "UPPER",
            self._direction == "LOWER",
            self._direction == "INNER",
            self._direction == "OUTER",
        ]

        if not any(is_acceptable_direction):
            raise ValueError("Direction is NOT one of \"upper\", \"lower\", \"inner\", \"outer\".")
        
        # Properties
        self.init_pos: float

        # PVs
        self.position_PV        : Any
        self.position_sp_PV     : Any
        self.motion_status_PV   : Any

        # default positions
        self._default_positions: dict[str, float] = {
            "UPPER": 20.35,
            "LOWER": 14.20,
            "INNER": 24.01,
            "OUTER":  1.33,
        }

    #
    # ----------------------------------------------------------------------------------------------------------
    def connect(self,) -> None:
        """
        Connect to EPICS PVs and store initial values (*e.g.* position)
        """

        self.position_PV        = epics.pv.get_pv(f"SR11SCR01:{self._direction}_POSITION_MONITOR", connect=True)
        self.position_sp_PV     = epics.pv.get_pv(f"SR11SCR01:{self._direction}_POSITION_SP", connect=True)
        self.motion_status_PV   = epics.pv.get_pv(f"SR11SCR01:{self._direction}_MOTION_STATUS", connect=True, 
                                                  callback=self.whileMoving)

        # inital values
        self.init_pos = self.position_PV.value

    #
    # ----------------------------------------------------------------------------------------------------------
    def move(self, position: float) -> None:
        """
        Moves scraper to provided position
        
        Parameters
        ----------
        position: float
            Scraper position set point. Check that it is appropriate.
        """
        try:
            self.position_sp_PV.put(position, wait=True)
            last_move_time = time.time()

            # while scraper is moving, wait. Exit when stopped moving
            # Move on if scaper takes longer than a minute to move
            while self.motion_status_PV.value == 1:
                time.sleep(0.5)
                # exit loop if motor takes longer than two minutes to move
                if (time.time() - last_move_time) >= 60: # seconds
                    print(f"WARNING! {self._direction} scraper took more than a minute to move. Continuing...")
                    break

        except Exception:
            print(traceback.format_exc())

    #
    # ----------------------------------------------------------------------------------------------------------
    def moveOut(self,) -> None:
        self.move(position=self._default_positions[self._direction])

    #
    # CALLBACKS #
    # --------- #
    #
    # ----------------------------------------------------------------------------------------------------------
    def whileMoving(self, pvname: str, value: int, **kw) -> None:
        # For motion status
        if value == 1: # Moving
            print(f"Moving {self._direction} scraper...")
        elif value == 0: # Stoppped
            print(f"{self._direction} moved into position!")

            