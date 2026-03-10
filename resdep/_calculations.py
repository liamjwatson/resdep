"""
Functions for calculating beam energy and related
"""
from typing import Union, overload
import numpy as np
from scipy import stats

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
def energy_calc(freq: float, f_rev: float, harmonic: int) -> float: ...
@overload
def energy_calc(freq: np.floating, f_rev: float, harmonic: int) -> np.floating: ...
def energy_calc(freq: Union[float, np.floating], f_rev: float, harmonic: int) -> Union[float, np.floating]:
    """
    Frequency (kHz) -> energy (GeV) conversion
    """
    return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9)

@overload
def freq_calc(energy: float, f_rev: float, harmonic: int) -> float: ...
@overload
def freq_calc(energy: np.floating, f_rev: float, harmonic: int) -> np.floating: ...
def freq_calc(energy: Union[float, np.floating], f_rev: float, harmonic: int) -> Union[float, np.floating]:
    """
    Energy (GeV) -> frequency (kHz) conversion
    """
    return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)

def tune_calc(energy: float) -> float:
    """
    Energy (GeV) to tune conversion
    """
    return a_g * e * energy * 1e9 / (m_e * c**2)

def model(x, x0, s, A, c):
    """
    Error function fitting model
    """
    law = stats.norm(loc=x0, scale=s)
    return A * law.cdf(x) + c

def round_to_1_sigfig(value: Union[float, np.floating]) -> float:
    """
    Round to one significant figure for fitted beam energy formatting
    """
    if value == 0:
        return 0
    return float(np.round(value, -int(np.floor(np.log10(abs(value)))))
)
def round_to_error_sigfig(value: Union[float, np.floating], error: Union[float, np.floating]) -> float:
    """
    Round value to the same sigfigs as the error
    """
    if error == 0:
        return float(value)
    return float(np.round(value, -int(np.floor(np.log10(np.abs(error))))))


def calculate_fitted_energy_stats(energies: dict[str, float], stddevs: Union[dict[str, float], None] = None) -> tuple[float, ...]:
    """
    Calculate the mean and standard deviation of the fitted energies for all the selected sectors. 
    """

    E0_mean = float(np.mean(list(energies.values())))
    
    if len(energies) == 0: 
        raise KeyError("dict \"energies\" contains no data.")
    elif len(energies) == 1:
        if stddevs is None:
            raise TypeError("Only one fitted energy, but no standard deviation passed. (stddevs=None)")
        else:
            E0_stddev = float(2*list(stddevs.values())[0])
    else:
        E0_stddev = float(2*np.std(list(energies.values())))
    
    E0_stddev_sigfig = round_to_1_sigfig(E0_stddev)
    E0_mean_sigfig = round_to_error_sigfig(E0_mean, E0_stddev_sigfig)

    return E0_mean, E0_stddev, E0_mean_sigfig, E0_stddev_sigfig

if __name__ == "__main__":
    print("_calculations.py contains helper functions for resdep.py and resdepGUI.py and should not be run directly.")
    print("Instead, use (for example): \"> from _calculations import energy_calc\".")