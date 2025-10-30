from typing import Union, Any
import epics
import time
import datetime
import os
import json
import csv
import sys
import warnings
import logging
import traceback
import matplotlib.pyplot as plt
import numpy as np
# from liberaComms import LiberaBLM

# --- Constants
f_rev 	: float = 1.38799e3 # kHz
# * Fractional Betatron Tunes
# End User Run Machine Parameters (2025-09-28)
v_x 	: float = 0.289148 	# 13.29
v_y 	: float = 0.21626 	# 5.219
v_x_var : float = 0
v_y_var : float = 0

# --------------------------------------------------------------------------------------------------------------------
#
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

# get tunes from BbB?
tunes_from_BbB: bool = False

response = input("Use betatron tunes from BbB? (y/n): ").strip().lower()
if response == 'y':
	v_x, v_y, v_x_var, v_y_var = listen_to_tunes()
	tunes_from_BbB = True
	
response = input("Do you want to calculate f_rev from master RF? (y/n): ")
if response == 'y':
	masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR')
	masterRFact: Union[float, Any] = masterRF.get()			# Hz
	if masterRFact is not None:
		f_rev: float = 1e-3 * masterRFact/360 	# kHz
	else:
		raise ValueError("masterRF.get() returned 'None'. Exiting...")


# --- exp variables
direction 					: str	 = 'Y'		# 'X' or 'Y'
tune 						: float	 = v_y 		# v_x or v_y
harmonic 					: int	 = 0		# int >= 0
set_kicker_amp 				: float	 = 0.05 		# %
baseline_duration 			: int	 = 30 		# seconds
exp_duration				: int	 = 5 * 60 	# seconds
set_drive_pattern 			: str	 = '200:220'		# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_feedback_mask 			: str	 = "!200:220"	# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_acquisition_mask_SRAM 	: str	 = "200:220"		# 'num', 'start:stop', '!num' for not num / range, or '!' for all. Should be same as drive pattern. 
set_acquisition_mask_BRAM 	: str	 = "200:220"	# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_sweep_period 			: float	 = 1e3 		# us
set_scraper_upper			: float  = 22.00 	# mm
tune_variance 				: float	 = 1e-4
# if tunes_from_BbB and tune == v_x:
	# tune_variance = v_x_var 
# if tunes_from_BbB and tune == v_y:
	# tune_variance = v_y_var 

# --- calcs
intrinsic_res_freq 	= f_rev * (tune + 0)		# 0th order, kHz
res_freq		   	= f_rev * (tune + harmonic) # harmoinc order, kHz
set_sweep_span 		= tune_variance	* res_freq	# kHz

warnings.warn("You are driving a betatron resonance and may dump beam!")
response = input("Do you want to continue? (y/n): ").strip().lower()
if not response == 'y':
	sys.exit()

# --------------------------------------------------------------------------------------------------------------------
#
# --- assign PVs: BbB Drive
sweep_freq 		= epics.pv.get_pv('IGPF:'+direction+':DRIVE:FREQ')
sweep_span 		= epics.pv.get_pv('IGPF:'+direction+':DRIVE:SPAN')
sweep_period 	= epics.pv.get_pv('IGPF:'+direction+':DRIVE:PERIOD')
kicker_amp 		= epics.pv.get_pv('IGPF:'+direction+':DRIVE:AMPL')
pattern 		= epics.pv.get_pv('IGPF:'+direction+':DRIVE:PATTERN')

# --- assign PVs: current
dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR')

# --- assign PVs: Drive mask
feedback_mask 			= epics.pv.get_pv("IGPF:"+direction+":FB:PATTERN")
acquisition_mask_SRAM 	= epics.pv.get_pv("IGPF:"+direction+":SRAM:ACQ:PATTERN")
acquisition_mask_BRAM 	= epics.pv.get_pv("IGPF:"+direction+":BRAM:ACQ:PATTERN")
# grab initial BbB feedback values to reset on exit
init_feedback_mask 			: Union[str, Any] = feedback_mask.get()
init_acquisition_mask_SRAM 	: Union[str, Any] = acquisition_mask_SRAM.get()
init_acquisition_mask_BRAM 	: Union[str, Any] = acquisition_mask_BRAM.get()

# --- assign PVs : BLMs 
blmPVs = {}
# loop over all sectors
for i in range(1,14+1,1):
	# Collect both straight ('A') and arc ('B') BLMs
	for letter in ['A', 'B']:
		blmPVs[str(i)+letter] = epics.pv.get_pv(f'SR{i:02d}BLM01:SIGNALS_SA_'+letter+'_MONITOR')

# --- assign PVs: scrapers (up, down, left, right)
scrapers: dict[tuple[str, ...], Any] = {}
for scraper in ['UPPER', 'LOWER', 'OUTER', 'INNER']: # alias [up, down, left, right]
	scrapers[scraper, 'pos'] 			= epics.pv.get_pv(f"SR11SCR01:{scraper}_POSITION_MONITOR") 
	scrapers[scraper, 'sp'] 			= epics.pv.get_pv(f"SR11SCR01:{scraper}_POSITION_SP") 
	scrapers[scraper, 'motion_status'] 	= epics.pv.get_pv(f"SR11SCR01:{scraper}_MOTION_STATUS") 
	scrapers[scraper, 'init_pos'] 		= scrapers[scraper, 'pos'].get() # float
# Scraper Positions as from 12/09/2023: 
#     Upper = 20.35 mm
#     Lower = 14.20 mm
#     Inner = 24.01 mm

# --- assign PVs : BLM settings
# --- assign PVs : BLM settings
# ! currently not implemented (esp in main())
# blm = epicsBLMs()
# blm.get_loss_PVs()
# blm.get_settings_PVs()
# blm.get_init_settings()



# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
if not os.path.isdir('drive_betatron'):
	os.mkdir('drive_betatron')
if not os.path.isdir(os.path.join('drive_betatron', 'Data')):
	os.mkdir(os.path.join('drive_betatron', 'Data'))
start_datetime = datetime.datetime.now()
date_str = start_datetime.strftime("%Y-%m-%d")
hours_str = start_datetime.strftime("%H%Mh")
seconds_str = start_datetime.strftime("%Ss")
if not os.path.isdir(os.path.join('drive_betatron','Data', date_str)):
	os.mkdir(os.path.join('drive_betatron', 'Data', date_str))
if not os.path.isdir(os.path.join('drive_betatron', 'Data', date_str, hours_str)):
	os.mkdir(os.path.join('drive_betatron', 'Data', date_str, hours_str))
	data_path = os.path.join('drive_betatron', 'Data', date_str, hours_str)
else: 
	# if you run the script again in the same minute, it appends seconds to the path name
	os.mkdir(os.path.join('drive_betatron', 'Data', date_str, hours_str, seconds_str))
	data_path = os.path.join('drive_betatron', 'Data', date_str, hours_str, seconds_str)

# --- init save vectors
timestamps_datetime: list[datetime.datetime] = []
timestamps_str: list[str] = []
current: list[str] = []
beam_losses: dict[str, list[float]] = {}
for key in blmPVs:
	beam_losses[key] = []
metadata: dict[str, Any] = {
	'direction': direction, 
	'fractional tune': tune,
	'f_rev (kHz)': f_rev,
	'resonant frequency (kHz)': res_freq,
	'harmonic': harmonic, 
	'kicker amp (%)': set_kicker_amp, 
	'drive pattern': set_drive_pattern, 
	'initial feedback mask': init_feedback_mask,
	'initial acquisition mask (SRAM)': init_acquisition_mask_SRAM,
	'initial acquisition mask (BRAM)': init_acquisition_mask_BRAM,
	'set feedback mask': set_feedback_mask,
	'set acquisition mask (SRAM)': set_acquisition_mask_SRAM,
	'set acquisition mask (BRAM)': set_acquisition_mask_BRAM,
	'scraper UPPER init pos': scrapers['UPPER', 'init_pos'],
	'scraper LOWER init pos': scrapers['LOWER', 'init_pos'],
	'scraper OUTER init pos': scrapers['OUTER', 'init_pos'],
	'scraper INNER init pos': scrapers['INNER', 'init_pos'],
	'scraper UPPER set pos' : set_scraper_upper,
	'baseline duration (s)': baseline_duration,
	'experiment duration (s)': exp_duration,
	'start time': start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
}

# --------------------------------------------------------------------------------------------------------------------
#
def main():
	"""
	Betatron tune driving experiment, uses kicker to drive betatron modes, and measures the corresponding beam loss.
	
	Workflow
	--------
		1. Initialises kicker (drive) panel with set amplitude, frequency and frequency sweep range
		2. Sits at these driving values for the set duration of the experiment
		3. Reads the beam loss for every monitor and drive frequency (readback at 1 Hz)
		4. Turns off kicker drive and resets BLM gain voltages and attenuations, scrapers,
		...saves and plots data on experiment end or KeyboardInterrupt

	To be implemented
	-----------------
		1. Update progress every n minutes or so
		2. Changing the adc_counts_offset and _window to record beam loss on the driven and 
		...pristine parts of the beam separately


	"""
	try:

		# init scrapers (in)
		scrapers['UPPER', 'sp'].put(set_scraper_upper)
		last_move_time = time.time()
		while scrapers['UPPER', 'motion_status'] == 1:
			time.sleep(0.5)
			# exit loop if motor takes longer than two minutes to move
			if (time.time() - last_move_time) >= 120: # seconds
				print(f"WARNING! UPPER scraper took more than two minutes to move. Continuing...")
				break

		# Log data without kicker drive enabled for beam loss baseline for 10 s
		start_time: float = time.time()
		print("\nCollecting baseline data for {0} s...".format(int(baseline_duration)))
		while (time.time() - start_time) < baseline_duration:
			# Nothing goes here... we log at 1 Hz
			time.sleep(1)
			# log data at 1 Hz (only relevant to above sleep time)
			log_data()

		# ! libera BLM currently not implemented
		# init libera+ windows
		# libera.put_adc_windows(
		# 	adc_offset_1=set_adc_offset_1, 
		# 	adc_window_1=set_adc_window_1, 
		# 	adc_offset_2=set_adc_offset_2, 
		# 	adc_window_2=set_adc_window_2,)

		# ! BLM settings - also not currently implemented
		# change BLM Vgc and atten
		# These are reset on exit
		# e.g.
		# blm_atten_decay_PVs['11A'].put(30)
		# blm_atten_decay_PVs['11B'].put(30)

		# Drive betatron after 10 s
		# init masks
		feedback_mask.put(set_feedback_mask)
		acquisition_mask_SRAM.put(set_acquisition_mask_SRAM)
		acquisition_mask_BRAM.put(set_acquisition_mask_BRAM)

		# init kicker drive
		sweep_span.put(set_sweep_span)		
		sweep_period.put(set_sweep_period)	
		pattern.put(set_drive_pattern)
		sweep_freq.put(res_freq)
		kicker_amp.put(set_kicker_amp)

		last_update_call: float = time.time()

		# start experiment 
		print("\nTurning on kicker...")
		while (time.time() - start_time) <= (exp_duration + baseline_duration):
			# Nothing goes here... we just sit driving at the betatron tune
			time.sleep(1)
			# log data at 1 Hz (only relevant to above sleep time)
			log_data()

			# ! This log is not working for now
			# --- Send progress update to the user every 60 s:
			if (time.time() - last_update_call) >= 60:
				time_elapsed : float = time.time() - start_time
				progress_update(time_elapsed)
				last_update_call = time.time()


	except KeyboardInterrupt:
		print("\nInterrupted! Kicker amp => OFF, BbB masks => reset, Saving data...")

	finally:
		# Turn off kicker
		kicker_amp.put(0)
		# Reset BbB masks
		feedback_mask.put(init_feedback_mask)
		acquisition_mask_SRAM.put(init_acquisition_mask_SRAM)
		acquisition_mask_BRAM.put(init_acquisition_mask_BRAM)
		# ! restore blm settings to init values -- to be added
		# move scrapers back
		try:
			for scraper in ['UPPER', 'LOWER', 'OUTER', 'INNER']:
				last_move_time: float = time.time()
				scrapers[scraper, 'sp'].put(scrapers[scraper, 'init_pos'])
				# Wait until the current scraper has stopped moving before moving the next one
				while scrapers[scraper, 'motion_status'] == 1:
					time.sleep(0.5)
					# exit loop if motor takes longer than two minutes to move
					if (time.time() - last_move_time) >= 120: # seconds
						print(f"WARNING! {scraper} scraper took more than two minutes to move. Continuing...")
						break
		except Exception:
			print(traceback.format_exc())
		finally: 
			print("scrapers put back -- remove try block if no errors")
		save_data()
		plot_data()
		print('\nExperiment finished!')

# --------------------------------------------------------------------------------------------------------------------
#		
# --- PV logger operating at 1 Hz
def log_data():
	"""
	Appends PV values to python lists at 1 Hz. \\
	Stored in memory until save_data() is called.
	"""
	timestamp = datetime.datetime.now()
	timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
	timestamps_datetime.append(timestamp)
	timestamps_str.append(timestamp_str)
	current_readback: Union[float, Any] = dcct.get()
	if current_readback is not None:
		current.append(current_readback)			# A
	for key in blmPVs:
		beam_losses[key].append(blmPVs[key].get())	# Counts

# --------------------------------------------------------------------------------------------------------------------
#
# --- send log / print every n minutes as update
def progress_update(time_elapsed: float):
	"""
	Prints elapsed time, expected experiment run time, and progress (percentage) complete to stdout

	Parameters
	----------
	time_elapsed : datetime.timedelta
		Timedelta between start time and now
	"""
	percentage_complete = int(100*time_elapsed//exp_duration)
	print("{:.2f} minutes elapsed of {:.0f} minutes ({:}%)...".format(time_elapsed/60, exp_duration/60, percentage_complete))

# --------------------------------------------------------------------------------------------------------------------
#
def save_data():
	"""
	Saves PV data to text, json and csv files depending on structure \\
	Also append entime to metadata and saves to json. \\
	Save path is drive_betatron/Data/{YYYY-mm-dd}/{HHHHh}/ \\
	*e.g.* drive_betatron/Data/2025-10-20/0900h/
	"""
	# populate final values and save metadata
	end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	metadata.update({'end time': end_time})
	with open(os.path.join(data_path, 'metadata.json'), 'w') as f:
		json.dump(metadata, f)
		
	# timestamps as txt
	with open(os.path.join(data_path, 'timestamps.txt'), 'w') as f:
		for value in timestamps_str:
			f.write(value + '\n')

	# current as txt
	with open(os.path.join(data_path, 'current.txt'), 'w') as f:
		for value in current:
			f.write(str(value) + '\n')

	# beam losses, as both .json:
	with open(os.path.join(data_path, 'beam_losses.json'), 'w') as f:
		json.dump(beam_losses, f)

	# ... and .csv:
	bl_keys = list(beam_losses.keys())
	bl_rows = zip(*[beam_losses[key] for key in bl_keys])
	with open(os.path.join(data_path, 'beam_losses.csv'), "w", newline="") as f:
		writer = csv.writer(f)
		writer.writerow(bl_keys)  # headers
		writer.writerows(bl_rows) # values

	print("\n Data saved!")


# --------------------------------------------------------------------------------------------------------------------
#
def plot_data():
	"""
	Plots every BLM against time
	"""
	try:
		# calculate timestamp at which the kicker turns on
		exp_delay = start_datetime + datetime.timedelta(seconds=baseline_duration)

		# --- plot data
		fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# plot normalised data:
		for index, key in enumerate(beam_losses):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs[0].plot(timestamps_datetime, beam_losses[key]/np.max(beam_losses[key]) - 0.15*index, '-', label=key)
			else:
				axs[0].plot(timestamps_datetime, beam_losses[key]/np.max(beam_losses[key]) - 0.15*index, '-', color='k', label=key)	
			axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs[0].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
		axs[0].set_title('All sectors')

		# plot just sector 11 (normalised)
		axs[1].plot(timestamps_datetime, beam_losses['11A']/np.max(beam_losses['11A']), '-', label='11A')
		axs[1].plot(timestamps_datetime, beam_losses['11B']/np.max(beam_losses['11B']) + 0.15, '-', label='11B')
		axs[1].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
		axs[1].legend(loc='lower right')
		axs[1].set_title('Sector 11')

		plt.savefig(os.path.join(data_path, "All_sectors_beam_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)



		# --- plot data
		fig2, axs2 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# --- normalise to current
		beam_losses_Inorm = {}
		for key in beam_losses:
			beam_losses_Inorm[key] = np.array(beam_losses[key])/(np.array(current)**2)

		# plot normalised data:
		for index, key in enumerate(beam_losses):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs2[0].plot(timestamps_datetime, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', label=key)
			else:
				axs2[0].plot(timestamps_datetime, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', color='k', label=key)	
			axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs2[0].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
		axs2[0].set_title('All sectors (current normalised)')

		# plot just sector 11 (normalised)
		axs2[1].plot(timestamps_datetime, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
		axs2[1].plot(timestamps_datetime, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
		axs2[1].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
		axs2[1].legend(loc='lower right')
		axs2[1].set_title('Sector 11 (current normalised)')

		plt.savefig(os.path.join(data_path, "current_normalised_all_sectors_beam_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

		plt.show()
	
	# Catch all exceptions raised by bad plotting code.
	# This is so we can preceed with drive_betatron() finally statement without exciting here on exception.
	except Exception:
		# Logs the error appropriately. 
		logging.error(traceback.format_exc())

# --------------------------------------------------------------------------------------------------------------------
#
# start experiment
main()