"""
Plot resdep data
"""

from functools import partial
from typing import Any
from datetime import datetime
import json
import numpy as np
import matplotlib.pyplot as plt 
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from cycler import cycler
import os
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

# fitting
from scipy import optimize
# from sklearn.metrics import r2_score

# resdep modules
from resdep.epicsBPMs import SR_BPMs, MX3_BPMs, TBPMs
from resdep._calculations import energy_calc, freq_calc, model

# --- consts
f_rev 		= 1.38799e3 			# kHz
v_synch		= 0.00847				
g 			= 2.0023193043609236
a_g 		= (g - 2)/2
m_e 		= 9.109383713928e-31 	# kg
c 			= 299792458				# m/s
e 			= 1.602176634e-19		# C
mu: str 	= u"\u03bc" 

# --- import data

data_path = Path.cwd()
data_path = data_path / "data" / "resdep" / "2026-03-30" / "2039h"
print(f"folder={data_path.name}")
if not data_path.exists():
	raise FileNotFoundError("Incorrect path")

# metadata json
with open(data_path / 'metadata.json', 'r') as f:
	metadata = json.load(f)
print("---metadata---")
print(metadata)

# freqs txt
freqs: list[float] = []
with open(os.path.join(data_path, 'freqs.txt'), 'r') as f:
	for line in f.readlines():
		freqs.append(float(line)/1e3)	# Hz -> kHz
freqs_array = np.array(freqs)

# timestamps txt
timestamps_strings: list[str] = [] 
with open(data_path / "timestamps.txt", "r") as f:
	for line in f.readlines():
		timestamps_strings.append(line[:-1])
# convert to datetime
timestamps_datetimes: list[datetime] = [datetime.strptime(time, "%Y-%m-%d %H:%M:%S") for time in timestamps_strings]
# Create minutes axis
start_time = timestamps_datetimes[0]
minutes: list[float] = [(time - start_time).total_seconds()/60 for time in timestamps_datetimes]

# current txt
current: list[float] = []
with open(os.path.join(data_path, 'current.txt'), 'r') as f:
	for line in f.readlines():
		current.append(float(line))

# beam_losses adc window 1
with open(os.path.join(data_path, 'adc_counter_loss_1.json'), 'r') as f:
	beam_loss_window_1 = json.load(f)

# beam_losses adc window 2
with open(os.path.join(data_path, 'adc_counter_loss_2.json'), 'r') as f:
	beam_loss_window_2 = json.load(f)

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
	tbpm_path = bpm_path / "TBPMs"
	if tbpm_path.exists():
		tbpms = TBPMs()
		tbpms.load_from_finished_experiment(path=tbpm_path)
	# MX3
	mx3_path = bpm_path / "MX3"
	if mx3_path.exists():
		mx3_bpms = MX3_BPMs()
		mx3_bpms.load_from_finished_experiment(path=mx3_path)
		# check keys are in the correct order ([1, 2, 5, 3, 4]):
		correct_bpm_order = ["1", "2", "5", "3", "4"]
		for attribute in ["x_position", "y_position", "intensity"]:
			attr = getattr(mx3_bpms, attribute)
			for index, key in enumerate(attr.keys()):
				if key != correct_bpm_order[index]:
					reordered_dict = {bpm: attr[bpm] for bpm in correct_bpm_order}
					setattr(mx3_bpms, attribute, reordered_dict)
					break


# calculate expected resonance frequency
res_freq: float = f_rev * (tune + harmonic)


# ------------------------------------------------------------------------------------------------------
def plot_normal_loss() -> None:

	beam_losses = []

	# --- plot data
	fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

	# plot normalised data:
	norm_beam_losses = {}
	for index, key in enumerate(beam_losses):
		norm_beam_losses[key] = gaussian_filter1d(beam_losses[key]/np.max(beam_losses[key]), 2)
		if index % 2 == 0:
			axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', label=key)
		else:
			axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', color='k', label=key)	
		axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
	axs[0].set_title('All sectors')
	axs[0].set_xlabel('frequency (kHz)')

	second_axis = axs[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
	second_axis.set_xlabel('Energy (GeV)')

	# plot just sector 11 (normalised)
	axs[1].plot(freqs, norm_beam_losses['11A'], '-', label='11A')
	axs[1].plot(freqs, norm_beam_losses['11B'] + 0.15, '-', label='11B')
	axs[1].legend(loc='lower right')
	axs[1].set_title('Sector 11')



	# --- plot data - current normalised
	fig2, axs2 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

	# --- normalise to current
	beam_losses_Inorm = {}
	for key in beam_losses:
		beam_losses_Inorm[key] = np.array(beam_losses[key])/(np.array(current)**2)

	# plot normalised data:
	for index, key in enumerate(beam_losses):
		# Colour straight, make corresponding arc black
		if index % 2 == 0:
			axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', label=key)
		else:
			axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', color='k', label=key)	
		axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
	axs2[0].set_title('All sectors (current normalised)')

	second_axis2 = axs2[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
	second_axis2.set_xlabel('Energy (GeV)')

	# plot just sector 11 (normalised)
	axs2[1].plot(freqs, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
	axs2[1].plot(freqs, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
	axs2[1].legend(loc='lower right')
	axs2[1].set_title('Sector 11 (current normalised)')

	plt.show()

	# ----------------------------------- #
	# ------	ADC counter loss 	----- #
	# ----------------------------------- #
	


	freqs_array = np.array(freqs)

	# --- plot data
	fig3, axs3 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)


	# plot normalised data:
	for index, key in enumerate(beam_loss_window_1):
		# Colour straight, make corresponding arc black
		if index % 2 == 0:
			axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', label=key)
		else:
			axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', color='k', label=key)	
		axs3[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
	axs3[0].set_title('ADC counter loss 1 - All sectors')
	axs3[0].set_xlabel('frequency (kHz)')

	# Create energy top axis
	second_axis = axs3[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
	second_axis.set_xlabel('Energy (GeV)')

	# plot just sector 11 (normalised)
	axs3[1].plot(freqs_array, beam_loss_window_1['11A']/np.max(beam_loss_window_1['11A']), '-', label='11A')
	axs3[1].plot(freqs_array, beam_loss_window_1['11B']/np.max(beam_loss_window_1['11B']) + 0.15, '-', label='11B')
	axs3[1].legend(loc='lower right')
	axs3[1].set_title('Sector 11')

	# plt.savefig(os.path.join(data_path, "ADC_counter_loss_1.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)


	# --- plot data
	fig4, axs4 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

	# plot normalised data:
	for index, key in enumerate(beam_loss_window_2):
		# Colour straight, make corresponding arc black
		if index % 2 == 0:
			axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', label=key)
		else:
			axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', color='k', label=key)	
		axs4[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
	axs4[0].set_title('ADC counter loss 2 - All sectors')
	axs4[0].set_xlabel('frequency (kHz)')

	# Create energy top axis
	second_axis = axs4[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
	second_axis.set_xlabel('Energy (GeV)')

	# plot just sector 11 (normalised)
	axs4[1].plot(freqs_array, beam_loss_window_2['11A']/np.max(beam_loss_window_2['11A']), '-', label='11A')
	axs4[1].plot(freqs_array, beam_loss_window_2['11B']/np.max(beam_loss_window_2['11B']) + 0.15, '-', label='11B')
	axs4[1].legend(loc='lower right')
	axs4[1].set_title('Sector 11')

	# plt.savefig(os.path.join(data_path, "adc_counter_loss_2.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	return None
# ------------------------------------------------------------------------------------------------------
def plot_ratio_loss() -> None:

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
			fitted_beam_energies[f"{sector}B"] = energy_calc(popt[0], f_rev, harmonic)
			fitted_beam_energy_variances[f"{sector}B"] = energy_calc(pcov[0], f_rev, harmonic)
			print(f"f0={popt[0]:0.3f}, E0={energy_calc(popt[0], f_rev, harmonic):0.5f}, score={score:0.2f}, r^2={r2:0.2f}")
			# plot baseline
			axs.axhline(y=y_model[0] + 0.03 * float(sector), xmin=0, xmax=1, alpha=0.1, linestyle="--", color="black")
			# plot fit
			axs.plot(freqs_array[start:end], y_model + 0.03 * float(sector), linestyle='--', color="red")

	axs.legend(bbox_to_anchor=(0.5, -0.3), loc='lower center', ncol=7)
	axs.set_xlim(freqs_array[start], freqs_array[-1])
	axs.set_xlabel("Frequency (kHz)")

	# Create energy top axis
	second_axis = axs.secondary_xaxis("top", 
		functions=(
			partial(energy_calc, f_rev=f_rev, harmonic=harmonic), # type: ignore
			partial(freq_calc, f_rev=f_rev, harmonic=harmonic)# type: ignore
			)
		)
	second_axis.set_xlabel('Energy (GeV)')


	# define sig fig calc:
	def round_to_1_sigfig(x):
		if x == 0:
			return 0
		return np.round(x, -int(np.floor(np.log10(abs(x)))))

	if do_fit:
		# calculate 2* st.dev
		f_rdp_mean = np.mean(np.array(list(fitted_beam_energy_frequencies.values())))
		E0_mean = np.mean(np.array(list(fitted_beam_energies.values())))
		E0_stdev = 2*np.std(np.array(list(fitted_beam_energies.values())))
		E0_stdev_sigfig = round_to_1_sigfig(E0_stdev)
		E0_mean_sigfig = np.round(E0_mean, -int(np.floor(np.log10(abs(E0_stdev)))))
		sideband_energy_shift = E0_mean - energy_calc(f_rdp_mean - f_rev*v_synch, f_rev, harmonic)
		expected_sidebands = [energy_calc(f_rdp_mean - 11.756, f_rev, harmonic), energy_calc(f_rdp_mean + f_rev*v_synch, f_rev, harmonic)]

		print(f"mean E0 = {E0_mean_sigfig} GeV" + u" \u00B1 " + f"{E0_stdev_sigfig*1e6:.0f} keV")

		print(f"Sidebands expected at " + u"(\u00B1" + f"{sideband_energy_shift*1e3:.2f} MeV): " + f"{expected_sidebands[0]:.4f}, {expected_sidebands[1]:.4f}")

		# shade region on plot
		axs.axvspan(xmin=freq_calc(float(E0_mean-E0_stdev), f_rev, harmonic), xmax=freq_calc(float(E0_mean+E0_stdev), f_rev, harmonic), alpha=0.1, color="black")

	# prevent scientific notation axes
	axs.ticklabel_format(useOffset=False)
	second_axis.ticklabel_format(useOffset=False)

	# plt.savefig(os.path.join(data_path, "ratio_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
	plt.savefig(data_path / "ratio_loss_fit.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	# --- deriv plt.show()

	deriv_axs.legend(bbox_to_anchor=(0.5, -0.3), loc='lower center', ncol=7)
	deriv_axs.set_xlim(freqs_array[start], freqs_array[-1])
	deriv_axs.set_xlabel("Frequency (kHz)")

	# Create energy top axis
	second_axis = deriv_axs.secondary_xaxis("top", 
		functions=(
			partial(energy_calc, f_rev=f_rev, harmonic=harmonic), # type: ignore
			partial(freq_calc, f_rev=f_rev, harmonic=harmonic)# type: ignore
			)
		)
	second_axis.set_xlabel('Energy (GeV)')

	# prevent scientific notation axes
	deriv_axs.ticklabel_format(useOffset=False)
	second_axis.ticklabel_format(useOffset=False)

	plt.show()

	return None
# ------------------------------------------------------------------------------------------------------
def plot_ODB() -> None:

	fig, axs = plt.subplots(2, 2, figsize=(8,6), layout="tight")

	fig.suptitle("ODB size and offset")

	axs[0,0].plot(ODB_data["X_size"])
	axs[0,1].plot(ODB_data["X_offset"])
	axs[1,0].plot(ODB_data["Y_size"])
	axs[1,1].plot(ODB_data["Y_offset"])

	axs[0,0].set_title(r"X beam size")
	axs[0,1].set_title(r"X beam offset")
	axs[1,0].set_title(r"Y beam size")
	axs[1,1].set_title(r"Y beam offset")

	axs[0,0].set_ylabel(r"X beam size ($\mu$m)")
	axs[0,1].set_ylabel(r"X beam offset ($\mu$m)")
	axs[1,0].set_ylabel(r"Y beam size ($\mu$m)")
	axs[1,1].set_ylabel(r"Y beam offset ($\mu$m)")

	plt.savefig(os.path.join(data_path, "ODB.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	plt.show()

	return None
# ------------------------------------------------------------------------------------------------------
def plot_SR_BPMs_around_kicker() -> None:

	# Plot SR BPM 10 before and after kicker
	fig, axs = plt.subplots(2, 1, figsize=(5,8), layout="tight")
	fig.suptitle("SR10/11 BPMs\nbefore and after kicker")

	colors = ['coral', 'coral', 'darkslateblue', 'darkslateblue']
	alphas = [0.2, 1, 1, 0.2]


	for bpm_index, bpm in enumerate(["10:5", "10:6", "10:7", "11:1"]):
		for attribute_index, attribute in enumerate(["x_position", "y_position"]):
			pos = np.array(getattr(sr_bpms, attribute)[bpm])
			pos = pos - np.mean(pos[:100])
			axs[attribute_index].plot(
				minutes, 
				pos, 
				label=bpm, 
				color=colors[bpm_index], 
				alpha=alphas[bpm_index]
				)

	axs[0].set_title("x_position change")
	axs[1].set_title("y_position change")
	for ax in [0,1]:
		axs[ax].legend()
		axs[ax].set_xlabel("minutes")
		axs[ax].set_ylabel("nm")

	shade_kicker_off(axs)

	plt.savefig(sr_path / "kicker_before_and_after.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	# --- Angle
	yaw, pitch = sr_bpms.calculate_angles(loop_around=True)
	fig, axs = plt.subplots(2, 1, figsize=(5,8), layout="tight")
	fig.suptitle("Angle through SR10/11 BPMs\nbefore and after kicker")

	colors = ["coral", "black", "darkslateblue"]
	alphas = [0.2, 1, 0.2]

	for bpms_index, bpms in enumerate(["10:5|10:6", "10:6|10:7", "10:7|11:1"]):
		# calculate change
		yaw_change = (yaw[bpms] - np.mean(yaw[bpms][:100])) 
		pitch_change = (pitch[bpms] - np.mean(pitch[bpms][:100]))
		axs[0].plot(
			minutes, 
			yaw_change,
			label=bpms,
			color=colors[bpms_index],
			alpha=alphas[bpms_index],
			linewidth=1	
		)
		axs[1].plot(
			minutes, 
			pitch_change,
			label=bpms,
			color=colors[bpms_index],
			alpha=alphas[bpms_index],
			linewidth=1	
		)

	axs[0].set_title("change in yaw")
	axs[1].set_title("change in pitch")
	for ax in [0,1]:
		axs[ax].legend()
		axs[ax].set_xlabel("minutes")
		axs[ax].set_ylabel(f"{mu}rad")

	shade_kicker_off(axs)

	plt.savefig(sr_path / "kicker_yaw_pitch.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
	plt.show()
# ------------------------------------------------------------------------------------------------------
def plot_SR_BPMs_around_MX3_IVU() -> None:

	# --- Position
	fig, axs = plt.subplots(2, 1, figsize=(5,8), layout="tight")
	fig.suptitle("SR03/04 BPMs\nbefore and after MX3 IVU")

	colors = ['green', 'green', 'purple', 'purple']
	alphas = [0.2, 1, 1, 0.2]

	for bpm_index, bpm in enumerate(["3:6", "3:7", "4:1", "4:2"]):
		for attribute_index, attribute in enumerate(["x_position", "y_position"]):
			pos = np.array(getattr(sr_bpms, attribute)[bpm])
			pos = pos - np.mean(pos[:100])
			axs[attribute_index].plot(
				minutes, 
				pos, 
				label=bpm, 
				color=colors[bpm_index], 
				alpha=alphas[bpm_index],
				linewidth=1
				)

	axs[0].set_title("x_position change")
	axs[1].set_title("y_position change")
	for ax in [0,1]:
		axs[ax].legend()
		axs[ax].set_xlabel("minutes")
		axs[ax].set_ylabel("nm")

	shade_kicker_off(axs)

	plt.savefig(sr_path / "MX3_IVU_before_and_after.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
	
	# --- Angle
	yaw, pitch = sr_bpms.calculate_angles(loop_around=True)
	mx3_IVU_missteer: list[str] = []
	missteer		: list[float] = [0, 0]

	print("---Max missteer (yaw, pitch) through MX3 IVU---")
	for bpms in ["3:6|3:7", "3:7|4:1", "4:1|4:2"]:
		for index, angle in enumerate([yaw, pitch]):
			angle_change 		= angle[bpms] - np.mean(angle[bpms][:100])
			angle_maxabs 		= np.max(np.abs(angle_change))
			angle_maxabs_index	= np.argmax(np.abs(angle_change))
			angle_maxabs_sign 	= np.sign(angle_change[angle_maxabs_index])
			missteer[index] 	= np.copysign(angle_maxabs, angle_maxabs_sign)

		missteer_str = f"Between SR BPMs {bpms}: yaw={missteer[0]:+0.3f} {mu}rad, pitch={missteer[1]:+0.3f} {mu}rad"
		mx3_IVU_missteer.append(missteer_str)
		print(missteer_str)

	# save deviations .txt
	with open(sr_path / "mx3_IVU_misteer.txt", "w", encoding="utf-8") as f:
		for line in mx3_IVU_missteer:
			f.write(line + "\n")

	fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(5,8), layout="tight")
	fig.suptitle("Angle through SR03/04 BPMs\nbefore and after MX3 IVU")

	colors = ["green", "black", "purple"]
	alphas = [0.2, 1, 0.2]

	for bpms_index, bpms in enumerate(["3:6|3:7", "3:7|4:1", "4:1|4:2"]):
		# calculate change
		yaw_change = yaw[bpms] - np.mean(yaw[bpms][:100])
		pitch_change = pitch[bpms] - np.mean(pitch[bpms][:100])
		axs[0].plot(
			minutes, 
			yaw_change,
			label=bpms,
			color=colors[bpms_index],
			alpha=alphas[bpms_index],
			linewidth=1	
		)
		axs[1].plot(
			minutes, 
			pitch_change,
			label=bpms,
			color=colors[bpms_index],
			alpha=alphas[bpms_index],
			linewidth=1	
		)


	axs[0].set_title("change in yaw")
	axs[1].set_title("change in pitch")
	for ax in axs:
		ax.legend()
		ax.set_xlabel("minutes")
		ax.set_ylabel(f"{mu}rad")

	shade_kicker_off(axs)

	plt.savefig(sr_path / "MX3_IVU_yaw_pitch.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)


	plt.show()
# ------------------------------------------------------------------------------------------------------
def plot_MX3_BPMs() -> None: 

	# --- colour palette
	color = plt.cm.inferno(np.linspace(start=0, stop=1, num=6)) #type: ignore
	plt.rcParams["axes.prop_cycle"] = cycler("color", color)

	# --- max deviation in x,y on MX3
	mx3_deviations: list[str] 	= []
	deviation: list[float] 		= [0,0]


	print("---Max deviations in x,y on MX3---")
	for bpm in mx3_bpms.x_position:
		for index, position in enumerate(["x_position", "y_position"]):
			pos 				= getattr(mx3_bpms, position)
			pos_array			= np.array(pos[bpm])
			pos_change 			= pos_array - np.mean(pos_array[:100])
			pos_maxabs 			= np.max(np.abs(pos_change))
			pos_maxabs_index 	= np.argmax(np.abs(pos_change))
			pos_maxabs_sign		= np.sign(pos_change[pos_maxabs_index])
			deviation[index]	= np.copysign(pos_maxabs, pos_maxabs_sign)

		deviation_str = f"MX3 BPM {bpm}: x={deviation[0]:+0.2f} {mu}m, y={deviation[1]:+0.2f} {mu}m"
		mx3_deviations.append(deviation_str)
		print(deviation_str)

	# save deviations .txt
	with open(mx3_path / "max_devations.txt", "w", encoding="utf-8") as f:
		for line in mx3_deviations:
			f.write(line + "\n")
	
	# --- plots x_pos, y_pos, intensity
	fig, axs = plt.subplots(3, 1, figsize=(5,10), layout="constrained")
	fig.suptitle(f"MX3 BPMs")

	for index, attribute in enumerate(["x_position", "y_position", "intensity"]):

		attr = getattr(mx3_bpms, attribute)
		axs[index].set_title(f"{attribute} change")
		
		for bpm, value in attr.items():
			value_array = np.array(value)
			value_offset = value_array - np.mean(value_array[:100])
			
			axs[index].plot(minutes, value_offset, linewidth=1, linestyle='-', label=bpm)
			axs[index].set_ylabel(r"$\mu$m")
			axs[index].legend(ncols=2, fontsize=9, handlelength=1, loc="upper right")

			# create inset with just angle through IVU
			if bpm == "4":
				axs_inset = inset_axes(axs[index], width="30%", height="30%", loc="upper center")
				axs_inset.plot(
				minutes, 
				value_offset,
				color=color[4],
				label=bpm,
				linewidth=1
				)
				# remove x_ticks
				axs_inset.tick_params(
					axis="x",
					which="both",
					bottom = False,
					labelbottom = False
				)
				shade_kicker_off(axs_inset, label=False)
		# adjusted ylims to fit in 
		ylims = axs[index].get_ylim()
		axs[index].set_ylim(ylims[0], ylims[1]*1.3)

	shade_kicker_off(axs)
	
	# Third plot (intensity)
	axs[2].set_ylabel(r"nA")
	axs[2].set_xlabel(r"Time (minutes)")
	axs[2].tick_params("x", rotation=90)
	
	plt.savefig(mx3_path / "all_MX3_DBPM_positions.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	# --- angle
	yaw, pitch = mx3_bpms.calculate_angles()

	fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(5,8), layout="compressed")
	fig.suptitle("Steer through MX3 PDS")

	for index, angle in enumerate([yaw, pitch]):
		for bpms_index, bpms in enumerate(angle):
			# calculate change
			angle_change = angle[bpms] - np.mean(angle[bpms][:100])
			axs[index].plot(
				minutes, 
				angle_change,
				color=color[bpms_index+1],
				label=bpms,
				linewidth=1	
			)
			if bpms == "3|4":
				axs_inset = inset_axes(axs[index], width="30%", height="30%", loc="upper center")
				axs_inset.plot(
				minutes, 
				angle_change,
				color=color[4],
				label=bpms,
				linewidth=1
				)
				# remove x_ticks
				axs_inset.tick_params(
					axis="x",
					which="both",
					bottom = False,
					labelbottom = False
				)
				shade_kicker_off(axs_inset, label=False)
		
	shade_kicker_off(axs)

	axs[0].set_title("change in yaw")
	axs[1].set_title("change in pitch")
	for ax in axs:
		ax.legend(ncols=2, fontsize=9, handlelength=1, loc="upper right")
		ax.set_xlabel("minutes")
		ax.set_ylabel(f"{mu}rad")

	shade_kicker_off(axs)

	plt.savefig(mx3_path / "MX3_PDS_yaw_pitch.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	plt.show()

	return None
# ------------------------------------------------------------------------------------------------------
def plot_MX3_at_sample() -> None:

	# --- just BPM 4 (goni / sample)
	bpm = "4"

	fig, axs = plt.subplots(2, 1, figsize=(4,8), layout="tight")
	fig.suptitle("MX3 BPM at goni/sample\n(BPM4)")

	for index, attribute in enumerate(["x_position", "y_position"]):
		data = getattr(mx3_bpms, attribute)[bpm]
		data = np.array(data) - np.mean(data[:100])
		axs[index].plot(minutes, data, linewidth=1, color="purple")
		axs[index].set_xlabel("minutes")
		axs[index].set_ylabel(r"$\mu$m")
		axs[index].set_title(f"{attribute} change")

	shade_kicker_off(axs)

	plt.savefig(bpm_path / "MX3" / "at_goni_sample.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

	plt.show()

	return None	
# ------------------------------------------------------------------------------------------------------
def plot_all_BPMs() -> None:
	index = 0
	attribute = None

	BPM_classes = [sr_bpms, tbpms, mx3_bpms]
	BPM_groups = ["SR", "TBPMs", "MX3"]

	for BPMs, group_name in zip(BPM_classes, BPM_groups):
		
		fig, axs = plt.subplots(3, 1, figsize=(4,10), layout="tight")
		fig.suptitle(f"{group_name} BPMs")

		try:
			for index, attribute in enumerate(["x_position", "y_position", "intensity"]):

				if hasattr(BPMs, attribute):

					attr = getattr(BPMs, attribute)
					axs[index].set_title(f"{attribute} change")
					
					for key, value in attr.items():
						# norm_value = np.array(value)/np.max(value)
						value_array = np.array(value)
						value_offset = value_array - np.mean(value_array[:100])
						# Convert SR BPMs from nm --> um
						if group_name == "SR" and attribute in ["x_position", "y_position"]:
							value_offset *= 1e-3
						
						axs[index].plot(minutes, value_offset, linewidth=0.5, linestyle='-', label=key)
						axs[index].set_ylabel(r"$\mu$m")
						if not group_name == "SR":
							axs[index].legend()
			
			# Third plot (intensity)
			axs[index].set_ylabel(r"a.u.")
			axs[index].set_xlabel(r"Time (minutes)")
			axs[index].tick_params("x", rotation=90)

		
		except NameError:
			continue

		if group_name == "MX3" and attribute == "intensity":
			axs[index].set_ylabel(r"nA")

	plt.show()

	return None
# ------------------------------------------------------------------------------------------------------
def shade_kicker_off(axes, label: bool = True) -> None:
	"""
	Shade kicker off region for each plot
	"""
	# if only one axis passed, cast to list of length 1
	if not hasattr(axes, "__len__"):
		axes = [axes]
	for axs in axes:
		axs.axvspan(xmin=0, xmax=minutes[99], ymin=0, ymax=1, color="black", alpha=0.1)
		if label:
			axs.text(
				x=0, y=1.05, s="kicker off", 
				horizontalalignment="left", 
				verticalalignment="center", 
				transform=axs.transAxes, 
				color="black", alpha=0.3
			)

if __name__ == "__main__":
	# plot_SR_BPMs_around_kicker()
	plot_SR_BPMs_around_MX3_IVU()
	# plot_MX3_BPMs()
