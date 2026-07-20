"""
Functions for calculating beam energy, tunes, and rounding errors and values 
to significant figures.
"""

"""
 ██████╗ █████╗ ██╗      ██████╗██╗   ██╗██╗      █████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗
██╔════╝██╔══██╗██║     ██╔════╝██║   ██║██║     ██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝
██║     ███████║██║     ██║     ██║   ██║██║     ███████║   ██║   ██║██║   ██║██╔██╗ ██║███████╗
██║     ██╔══██║██║     ██║     ██║   ██║██║     ██╔══██║   ██║   ██║██║   ██║██║╚██╗██║╚════██║
╚██████╗██║  ██║███████╗╚██████╗╚██████╔╝███████╗██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║███████║
 ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
"""                                                 
from typing import Union, overload, Literal
import numpy as np
import numpy.typing as npt

import resdep._constants as const

@overload
def energy_calc(
    freq: np.floating, f_rev: float, harmonic: int
) -> np.floating: ...
@overload
def energy_calc(
    freq: float, f_rev: float, harmonic: int
    ) -> float: ...
def energy_calc(
    freq: Union[float, np.floating], f_rev: float, harmonic: int
) -> Union[float, np.floating]:
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

    return (freq/f_rev - harmonic + 6)*const.m_e*const.c**2/(const.e*const.a_g*1e9) 
# -----------------------------------------------------------------------------
@overload
def freq_calc(
    energy: float, f_rev: float, harmonic: int
    ) -> float: ...
@overload
def freq_calc(
    energy: np.floating, f_rev: float, harmonic: int
) -> np.floating: ...
def freq_calc(
    energy: Union[float, np.floating], f_rev: float, harmonic: int
) -> Union[float, np.floating]:
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

    return f_rev*(energy*1e9*const.e*const.a_g/(const.m_e*const.c**2) + harmonic - 6)
# -----------------------------------------------------------------------------
def tune_calc(energy: float) -> float:
    """
    Energy (GeV) to tune (whole | non-fractional) conversion

    Parameters
    ----------
    energy: float
        Energy, GeV
    """         
    return const.a_g*const.e*energy*1e9/(const.m_e*const.c**2)
# -----------------------------------------------------------------------------
def calculate_sigfigs(value: Union[float, np.floating]) -> int:
    """
    Calculate the number of significant figures of a value
    """
    return int(np.floor(np.log10(abs(value))))
# -----------------------------------------------------------------------------
def round_to_1_sigfig(value: Union[float, np.floating]) -> float:
    """
    Round to one significant figure for fitted beam energy formatting
    """
    if value == 0:
        return 0
    n_sigfigs = calculate_sigfigs(value)
    return float(np.round(value, -n_sigfigs))
# -----------------------------------------------------------------------------
def round_to_error_sigfig(
    value: Union[float, np.floating], error: Union[float, np.floating]
) -> float:
    """
    Round value to the same significant figures as the error
    """
    if error == 0:
        return float(value)
    n_sigfigs = calculate_sigfigs(error)
    return float(np.round(value, -n_sigfigs))
# -----------------------------------------------------------------------------
def calculate_cusum(
        data: npt.NDArray,
        step_ref: float,
        dir: Literal["UPPER", "LOWER"]
    ) -> npt.NDArray:
    """CUSUM step detection, detects large changes in cumsum away from mean
    """ 
    if dir == "UPPER":
        sgn = 1
    else:
        sgn = -1
    n_points = len(data)
    cusum = np.zeros(n_points)
    mu_target = np.mean(data)
    for idx in range(1, n_points):
        cusum[idx] = max(
            0, 
            cusum[idx-1] + sgn*(data[idx] - mu_target - sgn*step_ref)
        )
        
    return cusum
# -----------------------------------------------------------------------------
def totvar_denoise(
        y: npt.NDArray, 
        eigval: float, 
        mu: float = 0,
        fused_lasso: bool = False
    ) -> npt.NDArray:
    """
    Total variance denoising algorithm.

    Symbols are math based on 
    [this paper](https://lcondat.github.io/publis/Condat-fast_TV-SPL-2012.pdf)
    """
    if fused_lasso and mu == 0:
        raise ValueError("Use mu>0 for fused_lasso mode")

    N = len(y)

    if N <= 1:
        x = y
        return x

    x = np.zeros(N)

    k       = 0
    k0      = 0
    k_low   = 0
    k_upp   = 0
    
    v_min = y[0] - eigval
    v_max = y[0] + eigval

    u_min = eigval
    u_max = -eigval
    
    while True:
        if k == N:
            x[N] = v_min + u_min
            return x

        while k < N-1:
            if (y[k+1] + u_min) < (v_min - eigval):
                if fused_lasso:
                    v_min = fused_lasso_approx(v_min, mu)
                x[k0:k_low+1] = v_min
                k_low += 1
                k = k_low
                k0 = k_low
                k_upp = k_low
                v_min = y[k]
                v_max = y[k] + 2*eigval
                u_min = eigval
                u_max = -eigval
            elif (y[k+1] + u_max) > (v_max + eigval):
                if fused_lasso:
                    v_max = fused_lasso_approx(v_max, mu)
                x[k0:k_upp+1] = v_max
                k_upp += 1
                k = k_upp
                k0 = k_upp
                k_low = k_upp
                v_min = y[k] - 2*eigval
                v_max = y[k]
                u_min = eigval
                u_max = -eigval
            else:
                k += 1
                u_min += y[k] - v_min
                u_max += y[k] - v_max
                if u_min >= eigval:
                    v_min += (u_min - eigval)/(k - k0 + 1)
                    u_min = eigval
                    k_low = k
                if u_max <= -eigval:
                    v_max += (u_max + eigval)/(k - k0 + 1)
                    u_max = -eigval
                    k_upp = k

        if u_min < 0:
            if fused_lasso:
                v_min = fused_lasso_approx(v_min, mu)
            x[k0:k_low+1] = v_min
            k_low += 1
            k = k_low
            k0 = k_low
            v_min = y[k]
            u_min = eigval
            u_max = y[k] + eigval - v_max
        elif u_max > 0:
            if fused_lasso:
                v_max = fused_lasso_approx(v_max, mu)
            x[k0:k_upp] = v_max
            k_upp += 1
            k = k_upp
            k0 = k_upp
            v_max = y[k]
            u_max = -eigval
            u_min = y[k] - eigval - v_min
        else:
            v_min += u_min/(k - k0 + 1)
            if fused_lasso:
                v_min = fused_lasso_approx(v_min, mu)
            x[k0:N] = v_min 
            return x


def fused_lasso_approx(v: float, mu: float) -> float:
    """
    fused lasso variant of total variance denoising. 

    Symbols are math based on 
    [this paper](https://lcondat.github.io/publis/Condat-fast_TV-SPL-2012.pdf)
    """
    if v > mu:
        v += -mu
    elif v < -mu:
        v += mu
    else:
        v = 0
    
    return v

if __name__ == "__main__":
    print(
        "_calculations.py contains helper functions for", 
        "resonant depolarisation experiment.py and resdepGUI.py."
    )
    print("Run help(_calculations) after import for more details.")
