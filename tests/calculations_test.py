import pytest

import resdep._constants as const
from resdep._calculations import (
        tune_calc,
        energy_calc,
        freq_calc,
        round_to_1_sigfig,
        round_to_error_sigfig,
        calculate_sigfigs,
)


def test_energy_to_frequency_conversion() -> None:
    energy = 3.031
    
    calculated_frequency = freq_calc(
            energy=energy,
            f_rev=const.f_rev,
            harmonic=1
    )
    calculated_energy = energy_calc(
            freq=calculated_frequency,
            f_rev=const.f_rev,
            harmonic=1
    )

    assert calculated_energy == energy

def test_sigfig_rounding() -> None:
    energy = 3.03123456789 # GeV
    energy_rounded_to_15keV = 3.03123 # GeV
    error = 15*1e-6 # GeV
    sigfigs = -5

    error_rounded = round_to_1_sigfig(value=error)
    energy_rounded = round_to_error_sigfig(value=energy, error=error_rounded)
    calculated_sigfigs = calculate_sigfigs(error)

    assert energy_rounded == energy_rounded_to_15keV
    assert calculated_sigfigs == sigfigs

