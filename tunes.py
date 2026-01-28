# --------------------------------------------------------------------------------------------------------------------
# Functions for reading tunes from EPICS
# 

from typing import Union
import epics
import time
import numpy as np

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