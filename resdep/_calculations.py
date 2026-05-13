"""
Functions for calculating beam energy and related
"""
"""
 ██████╗ █████╗ ██╗      ██████╗██╗   ██╗██╗      █████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗
██╔════╝██╔══██╗██║     ██╔════╝██║   ██║██║     ██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝
██║     ███████║██║     ██║     ██║   ██║██║     ███████║   ██║   ██║██║   ██║██╔██╗ ██║███████╗
██║     ██╔══██║██║     ██║     ██║   ██║██║     ██╔══██║   ██║   ██║██║   ██║██║╚██╗██║╚════██║
╚██████╗██║  ██║███████╗╚██████╗╚██████╔╝███████╗██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║███████║
 ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
"""
from typing import Union, overload
import numpy as np

# --- Constants
g 			: float = 2.0023193043609236
a_g 		: float = (g - 2)/2
m_e 		: float = 9.109383713928e-31 	# kg
c 			: float = 299792458				# m/s
e 			: float = 1.602176634e-19		# C
# * Fractional spin tune
v_s 		: float = 0.833 				# 6.833
v_s303GeV 	: float = 0.879 				# 6.879, based on if the beam energy is 3.0311 GeV 
# End User Run Machine Parameters (2025-09-28)
v_x 		: float = 0.289148 				# 13.29
v_y 		: float = 0.21626 				# 5.219
v_synch 	: float	= 0.00847				

@overload
def energy_calc(freq: np.floating, f_rev: float, harmonic: int) -> np.floating: ...
@overload
def energy_calc(freq: float, f_rev: float, harmonic: int) -> float: ...
def energy_calc(freq: Union[float, np.floating], f_rev: float, harmonic: int) -> Union[float, np.floating]:
    """
    Frequency (kHz) -> energy (GeV) conversion

    Parameters
    ----------
    freq: float | np.floating
        Frequency data, kHz
    f_rev: float
        Revolution frequency, kHz
    harmonic: int
        Harmonic of frequency drive

    Returns
    -------
    Energy: float | np.floating
        Beam energy, GeV
    """
    
    return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9) # GeV
# ------------------------------------------------------------------------------------------------------
@overload
def freq_calc(energy: float, f_rev: float, harmonic: int) -> float: ...
@overload
def freq_calc(energy: np.floating, f_rev: float, harmonic: int) -> np.floating: ...
def freq_calc(energy: Union[float, np.floating], f_rev: float, harmonic: int) -> Union[float, np.floating]:
    """
    Energy (GeV) -> frequency (kHz) conversion:

    Parameters
    ----------
    energy: float | np.floating
        Energy data, GeV
    f_rev: float
        Revolution frequency, kHz
    harmonic: int
        Harmonic of frequency drive

    Returns
    -------
    frequency: float | np.floating
        Beam energy, GeV
    """
    return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)
# ------------------------------------------------------------------------------------------------------
def tune_calc(energy: float) -> float:
    """
    Energy (GeV) to tune (whole | non-fractional) conversion 

    Parameters
    ----------
    energy: float
        Energy, GeV
    """
    return a_g * e * energy * 1e9 / (m_e * c**2)
# ------------------------------------------------------------------------------------------------------
def round_to_1_sigfig(value: Union[float, np.floating]) -> float:
    """
    Round to one significant figure for fitted beam energy formatting
    """
    if value == 0:
        return 0
    return float(np.round(value, -int(np.floor(np.log10(abs(value)))))
)
# ------------------------------------------------------------------------------------------------------
def round_to_error_sigfig(value: Union[float, np.floating], error: Union[float, np.floating]) -> float:
    """
    Round value to the same significant figures as the error
    """
    if error == 0:
        return float(value)
    return float(np.round(value, -int(np.floor(np.log10(np.abs(error))))))


if __name__ == "__main__":
    print("_calculations.py contains helper functions for resonant depolarisation experiment.py and resdepGUI.py.")
    print("Run help(_calculations) after import for more details.")