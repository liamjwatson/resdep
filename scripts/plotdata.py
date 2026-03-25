"""
Plot resdep data
"""

from typing import Any
import json
from matplotlib import legend
import numpy as np
import matplotlib.pyplot as plt 
import os
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

# fitting
from scipy import stats, optimize
# from sklearn.metrics import r2_score

# resdep modules
from resdep.epicsBPMs import SR_BPMs, MX3_BPMs, TBPMs

def model(x, x0, s, A, c):
    law = stats.norm(loc=x0, scale=s)
    return A * law.cdf(x) + c

# --- consts
f_rev 		= 1.38799e3 			# kHz
v_synch		= 0.00847				
g 			= 2.0023193043609236
a_g 		= (g - 2)/2
m_e 		= 9.109383713928e-31 	# kg
c 			= 299792458				# m/s
e 			= 1.602176634e-19		# C

# --- import data

# data_path = Path("/san_data/accelerator/opdata/usr/personal/watsonl/resdep-develop")
data_path = Path.cwd()
data_path = data_path / "data" / "resdep" / "2026-03-30" / "2240h"
# data_path = os.path.join(parent_path, "data", "resdep", "2026-03-02", "2300h")
# data_path = os.path.join(current_path, "data", "resdep", "2026-02-22", "1146h")
# metadata json
with open(data_path / 'metadata.json', 'r') as f:
	metadata = json.load(f)
f.close()
# freqs txt
freqs = []
with open(os.path.join(data_path, 'freqs.txt'), 'r') as f:
	for line in f.readlines():
		freqs.append(float(line)/1e3)	# Hz -> kHz
f.close()
freqs = np.array(freqs)
# current txt
current = []
with open(os.path.join(data_path, 'current.txt'), 'r') as f:
	for line in f.readlines():
		current.append(float(line))
f.close()
# # beam_losses json
# with open(os.path.join(data_path, 'beam_losses.json'), 'r') as f:
# 	beam_losses = json.load(f)
# f.close()
# beam_losses adc window 1
with open(os.path.join(data_path, 'adc_counter_loss_1.json'), 'r') as f:
	beam_loss_window_1 = json.load(f)
f.close()
# beam_losses adc window 2
with open(os.path.join(data_path, 'adc_counter_loss_2.json'), 'r') as f:
	beam_loss_window_2 = json.load(f)
f.close()
# ODB beam size and offset
with open(os.path.join(data_path, "ODB_data.json"), "r") as f:
	ODB_data = json.load(f)

# Assign metadata to variables:
if "f_rev" in metadata.keys():
	f_rev = metadata["f_rev"]
tune = metadata["fractional tune"]
harmonic = metadata['harmonic']

# --- BPMs
sr_bpms = ...
mx3_bpms = ...
tbpms = ...
bpm_path = data_path / "BPMs"
if bpm_path.exists():
	# SR
	sr_path = bpm_path / "SR"
	if sr_path.exists():
		sr_bpms = SR_BPMs()
		sr_bpms.load_from_finished_experiment(path=sr_path)
	# TBPM
	tbpm_path = bpm_path / "TBPM"
	if tbpm_path.exists():
		tbpms = TBPMs()
		tbpms.load_from_finished_experiment(path=tbpm_path)
	# MX3
	mx3_path = bpm_path / "MX3"
	if mx3_path.exists():
		mx3_bpms = MX3_BPMs()
		mx3_bpms.load_from_finished_experiment(path=mx3_path)


# calculate expected resonance frequency
res_freq: float = f_rev * (tune + harmonic)

# Create energy top axis
def energy_calc(freq):
	return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9)
def freq_calc(energy):
	return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)




# --- plot data
# fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # plot normalised data:
# norm_beam_losses = {}
# for index, key in enumerate(beam_losses):
# 	norm_beam_losses[key] = gaussian_filter1d(beam_losses[key]/np.max(beam_losses[key]), 2)
# 	if index % 2 == 0:
# 		axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', label=key)
# 	else:
# 		axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', color='k', label=key)	
# 	axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs[0].set_title('All sectors')
# axs[0].set_xlabel('frequency (kHz)')

# second_axis = axs[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs[1].plot(freqs, norm_beam_losses['11A'], '-', label='11A')
# axs[1].plot(freqs, norm_beam_losses['11B'] + 0.15, '-', label='11B')
# axs[1].legend(loc='lower right')
# axs[1].set_title('Sector 11')



# # --- plot data - current normalised
# fig2, axs2 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # --- normalise to current
# beam_losses_Inorm = {}
# for key in beam_losses:
# 	beam_losses_Inorm[key] = np.array(beam_losses[key])/(np.array(current)**2)

# # plot normalised data:
# for index, key in enumerate(beam_losses):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs2[0].set_title('All sectors (current normalised)')

# second_axis2 = axs2[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis2.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs2[1].plot(freqs, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
# axs2[1].plot(freqs, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
# axs2[1].legend(loc='lower right')
# axs2[1].set_title('Sector 11 (current normalised)')

# plt.show()

# ----------------------------------- #
# ------	ADC counter loss 	----- #
# ----------------------------------- #
#


# freqs_array = np.array(freqs)

# # --- plot data
# fig3, axs3 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)


# # plot normalised data:
# for index, key in enumerate(beam_loss_window_1):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs3[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs3[0].set_title('ADC counter loss 1 - All sectors')
# axs3[0].set_xlabel('frequency (kHz)')

# # Create energy top axis
# second_axis = axs3[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs3[1].plot(freqs_array, beam_loss_window_1['11A']/np.max(beam_loss_window_1['11A']), '-', label='11A')
# axs3[1].plot(freqs_array, beam_loss_window_1['11B']/np.max(beam_loss_window_1['11B']) + 0.15, '-', label='11B')
# axs3[1].legend(loc='lower right')
# axs3[1].set_title('Sector 11')

# # plt.savefig(os.path.join(data_path, "ADC_counter_loss_1.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)


# # --- plot data
# fig4, axs4 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # plot normalised data:
# for index, key in enumerate(beam_loss_window_2):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs4[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs4[0].set_title('ADC counter loss 2 - All sectors')
# axs4[0].set_xlabel('frequency (kHz)')

# # Create energy top axis
# second_axis = axs4[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs4[1].plot(freqs_array, beam_loss_window_2['11A']/np.max(beam_loss_window_2['11A']), '-', label='11A')
# axs4[1].plot(freqs_array, beam_loss_window_2['11B']/np.max(beam_loss_window_2['11B']) + 0.15, '-', label='11B')
# axs4[1].legend(loc='lower right')
# axs4[1].set_title('Sector 11')

# # plt.savefig(os.path.join(data_path, "adc_counter_loss_2.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)




# ----------------------------------- #
# ------		Ratio Loss  	----- #
# ----------------------------------- #

# ! minus 1 from the data and do cumsum

ratio_loss: dict[str, Any] = {}
freqs_array = np.array(freqs)
fitted_beam_energy_frequencies: dict[str, float] = {}
fitted_beam_energies: dict[str, float] = {}
fitted_beam_energy_variances: dict[str, float] = {}

for key in beam_loss_window_1:
	ratio_loss[key] = (np.array(beam_loss_window_1[key]) + 1)/(np.array(beam_loss_window_2[key]) + 1)

start = 0
end = len(freqs_array)
sigma = 10
window_length = 5 # 1101
do_fit = False
sectors = ["1", "4", "8", "11", "12", "13"]
# sectors = ["1", "8", "13"]

fig, axs = plt.subplots(1,1, figsize=(7,5), layout="tight")
deriv_fig, deriv_axs = plt.subplots(1,1, figsize=(7,5), layout="tight")
cumsum_fig, cumsum_axs = plt.subplots(1,1, figsize=(7,5), layout="tight")

for sector in sectors:
	# filter / bin
	bend = gaussian_filter1d(ratio_loss[f"{sector}B"][start:end], sigma)
	# set zero
	bend += np.min(bend)
	# normalise
	bend *= 1/np.max(bend)
	# differentiate
	deriv_bend = savgol_filter(x=bend, window_length=window_length, polyorder=1, deriv=1)
	deriv_bend_peak = np.argmax(deriv_bend)
	# cumsum
	bend_at_zero = bend - np.mean(bend[:200])
	bend_cumsum = np.cumsum(bend_at_zero)
	# plot
	axs.plot(freqs_array[start:end], bend + 0.03 * float(sector), label=f"{sector}B")
	deriv_axs.plot(freqs_array[start:end], deriv_bend + 6e-5 * float(sector), label=f"{sector}B")
	deriv_axs.axvline(x=freqs_array[deriv_bend_peak], ymin=0, ymax=1, color='red')
	cumsum_axs.plot(freqs_array[start:end], bend_cumsum, label=f"{sector}B")

	if do_fit:
		# do fit
		popt, pcov = optimize.curve_fit(model, freqs_array[start:end], bend, p0=[res_freq, 1, 1, 1], maxfev=8000)
		y_model = model(freqs_array[start:end], *popt)

		# -- calculate goodness of fit
		# residual sum of squares
		ss_res = np.sum((bend - y_model)**2)
		# total sum of squares
		ss_tot = np.sum((bend - np.mean(bend))**2)
		# r-squared
		r2 = 1 - (ss_res / ss_tot)

		# score = r2_score(bend, y_model)
		score = 0
		fitted_beam_energy_frequencies[f"{sector}B"] = popt[0]  
		fitted_beam_energies[f"{sector}B"] = energy_calc(popt[0])
		fitted_beam_energy_variances[f"{sector}B"] = energy_calc(pcov[0])
		print(f"f0={popt[0]:0.3f}, E0={energy_calc(popt[0]):0.5f}, score={score:0.2f}, r^2={r2:0.2f}")
		# plot baseline
		axs.axhline(y=y_model[0] + 0.03 * float(sector), xmin=0, xmax=1, alpha=0.1, linestyle="--", color="black")
		# plot fit
		axs.plot(freqs_array[start:end], y_model + 0.03 * float(sector), linestyle='--', color="red")

axs.legend(bbox_to_anchor=(0.5, -0.3), loc='lower center', ncol=7)
axs.set_xlim(freqs_array[start], freqs_array[-1])
axs.set_xlabel("Frequency (kHz)")

# Create energy top axis
second_axis = axs.secondary_xaxis("top", functions=(energy_calc, freq_calc))
second_axis.set_xlabel('Energy (GeV)')


# define sig fig calc:
def round_to_1_sigfig(x):
	return np.round(x, -int(np.floor(np.log10(abs(x)))))

if do_fit:
	# calculate 2* st.dev
	f_rdp_mean = np.mean(np.array(list(fitted_beam_energy_frequencies.values())))
	E0_mean = np.mean(np.array(list(fitted_beam_energies.values())))
	E0_stdev = 2*np.std(np.array(list(fitted_beam_energies.values())))
	E0_stdev_sigfig = round_to_1_sigfig(E0_stdev)
	E0_mean_sigfig = np.round(E0_mean, -int(np.floor(np.log10(abs(E0_stdev)))))
	sideband_energy_shift = E0_mean - energy_calc(f_rdp_mean - f_rev*v_synch)
	expected_sidebands = [energy_calc(f_rdp_mean - 11.756), energy_calc(f_rdp_mean + f_rev*v_synch)]

	print(f"mean E0 = {E0_mean_sigfig} GeV" + u" \u00B1 " + f"{E0_stdev_sigfig*1e6:.0f} keV")

	print(f"Sidebands expected at " + u"(\u00B1" + f"{sideband_energy_shift*1e3:.2f} MeV): " + f"{expected_sidebands[0]:.4f}, {expected_sidebands[1]:.4f}")

	# shade region on plot
	axs.axvspan(xmin=freq_calc(E0_mean-E0_stdev), xmax=freq_calc(E0_mean+E0_stdev), alpha=0.1, color="black")

# prevent scientific notation axes
axs.ticklabel_format(useOffset=False)
second_axis.ticklabel_format(useOffset=False)

# plt.savefig(os.path.join(data_path, "ratio_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
# plt.savefig(os.path.join(data_path, "ratio_loss_fit.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

# --- deriv plt.show()

deriv_axs.legend(bbox_to_anchor=(0.5, -0.3), loc='lower center', ncol=7)
deriv_axs.set_xlim(freqs_array[start], freqs_array[-1])
deriv_axs.set_xlabel("Frequency (kHz)")

# Create energy top axis
second_axis = deriv_axs.secondary_xaxis("top", functions=(energy_calc, freq_calc))
second_axis.set_xlabel('Energy (GeV)')

# prevent scientific notation axes
deriv_axs.ticklabel_format(useOffset=False)
second_axis.ticklabel_format(useOffset=False)

# plt.show()





# ----------------------------------- #
# ------	ODB	beam size  	    ----- #
# ----------------------------------- #

# fig, axs = plt.subplots(2, 2, figsize=(8,6), layout="tight")

# fig.suptitle("ODB size and offset")

# axs[0,0].plot(ODB_data["X_size"])
# axs[0,1].plot(ODB_data["X_offset"])
# axs[1,0].plot(ODB_data["Y_size"])
# axs[1,1].plot(ODB_data["Y_offset"])

# axs[0,0].set_title(r"X beam size")
# axs[0,1].set_title(r"X beam offset")
# axs[1,0].set_title(r"Y beam size")
# axs[1,1].set_title(r"Y beam offset")

# axs[0,0].set_ylabel(r"X beam size ($\mu$m)")
# axs[0,1].set_ylabel(r"X beam offset ($\mu$m)")
# axs[1,0].set_ylabel(r"Y beam size ($\mu$m)")
# axs[1,1].set_ylabel(r"Y beam offset ($\mu$m)")

# plt.savefig(os.path.join(data_path, "ODB.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

# plt.show()


# ----------------------------------- #
# ------		BPMs	  	    ----- #
# ----------------------------------- #

BPM_classes = [sr_bpms, tbpms, mx3_bpms]
BPM_groups = ["SR", "TBPM", "MX3"]

for BPMs, group_name in zip(BPM_classes, BPM_groups):
	for attribute in ["x_position", "y_position", "intensity"]:
		if hasattr(BPMs, attribute):

			fig, axs = plt.subplots(figsize=(8,6), layout="tight")
			fig.suptitle(f"{group_name} BPMs: {attribute}")

			attr = getattr(BPMs, attribute)

			for key, value in attr.items():
				# norm_value = np.array(value)/np.max(value)
				value_array = np.array(value)
				value_offset = value_array - np.mean(value_array)
				axs.plot(value_offset, '-', label=key)

# axs.legend()

plt.show()