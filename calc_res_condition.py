import epics
from typing import Union, Any
import time
import numpy as np

"""
Calculate the resonance condition between the spin and betatron tunes for maximum depolarisation
"""

def listen_to_tunes() -> tuple[float, ...]:
	"""
	Average tune over 10 s of measurements from BbB. Calculate mean and variance (for sweep_span)

	Returns
	-------
	v_x_av : float
		Average horizontal tune (over 10s data acquisition)
	v_y_av : float
		Average vertical tune (over 10s data acquisition)
	v_x_var : float
		Variance in the horizontal tune
	v_y_var : float
		Variance in the vertical tune
	"""
	# init
	v_x_av = 0
	v_y_av = 0
	v_x_var = 0
	v_y_var = 0

	# grab PVs
	peaktune_x = epics.pv.get_pv("IGPF:X:SRAM:PEAKTUNE2")
	peaktune_y = epics.pv.get_pv("IGPF:Y:SRAM:PEAKTUNE2")
	# store readback
	peaktune_x_readback : list[Union[float, None]] = []
	peaktune_y_readback : list[Union[float, None]] = []

	print("Lisitening to tunes for 10s...")
	start_time = time.time()

	while (time.time() - start_time) <= 10:
		peaktune_x_readback.append(peaktune_x.get())
		peaktune_y_readback.append(peaktune_y.get())
		time.sleep(1)

	if (not None in peaktune_x_readback) and (not None in peaktune_y_readback):
		v_x_av 	: float = np.mean(np.array(peaktune_x_readback), dtype=float)
		v_y_av 	: float = np.mean(np.array(peaktune_y_readback), dtype=float)
		v_x_var : float = np.var(np.array(peaktune_x_readback), dtype=float)
		v_y_var : float = np.var(np.array(peaktune_y_readback), dtype=float)
	else:
		raise ArithmeticError("Peaktune_readback returned None, no mean can be calculated.")


	print("Tune averages and variances calculated!")
	print(f"v_x = {v_x_av}, var = {v_x_var}")
	print(f"v_y = {v_y_av}, var = {v_y_var}")

	return v_x_av, v_y_av, v_x_var, v_y_var


# --- Constants
# * Fractional spin tune
v_s 		: float = 0.833 			# 6.833
v_s303GeV 	: float = 0.876 			# 6.876, based on if the beam energy is 3.03 GeV 
g 		: float = 2.0023193043609236
a_g 	: float = (g - 2)/2
m_e 	: float = 9.109383713928e-31 	# kg
c 		: float = 299792458				# m/s
e 		: float = 1.602176634e-19		# C
f_rev 	: float = 1.38799e3 			# kHz

# Grab masterRF from EPICS
# if disconnected, .get() will return none and f_rev with throw exception
masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR')
masterRFact: Union[float, None] = masterRF.get(timeout=1)			# Hz
try:
	f_rev: float = 1e-3 * masterRFact/360 	# kHz # pyright: ignore[reportOperatorIssue] 
except TypeError: # ^ masterRFact might be None
	print("Could not grab master RF from EPICS (weird?). Using default f_rev")


# --- Calculations 
v_x, v_y, v_x_var, v_y_var = listen_to_tunes()

# normal res frequency
print("Standard vertical resonant frequencies:")
print(f"Harmonic 0: {f_rev * (v_y + 0)} kHz")
print(f"Harmonic 1: {f_rev * (v_y + 1)} kHz")
print(f"Harmonic 2: {f_rev * (v_y + 2)} kHz")
print(f"Harmonic 3: {f_rev * (v_y + 3)} kHz")
print(f"Harmonic 4: {f_rev * (v_y + 4)} kHz")
print(f"Harmonic 5: {f_rev * (v_y + 5)} kHz")
print(f"Harmonic 6: {f_rev * (v_y + 6)} kHz")
print(f"Harmonic 7: {f_rev * (v_y + 7)} kHz\n")



# since these are fractional tunes
res_condition = (6 + v_s303GeV) + (5 + v_y)

# drive frequency
drive_frequency = f_rev * res_condition # kHz

print(f"fractional v_s = {v_s303GeV}")
print(f"fractional v_y = {v_y}")
print(f"resonant condition = {res_condition}")
print(f"drive freqency = {drive_frequency} kHz")

print("\nNow if we had perfect resonance...:")

v_s_perfect = 12 - (5 + v_y) - 6
drive_frequency_perfect = f_rev * 12

print(f"Perfect spin tune = {v_s_perfect}")
print(f"perfect drive freqency = {drive_frequency_perfect} kHz")

print("\nAlternate res condition???")
print(f"f = {f_rev * (v_s303GeV + v_y)} kHz")