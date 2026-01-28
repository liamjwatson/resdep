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
from tunes import listen_to_tunes # custom listening function
from epicsBLMs import BLMs # Libera BLM python class, stores states, dicts, functions  
from epicsScrapers import Scraper 

# --- Constants
f_rev 	: float = 1.38799e3 # kHz
# * Fractional Betatron Tunes
# End User Run Machine Parameters (2025-09-28)
v_x 	: float = 0.289148 	# 13.29
v_y 	: float = 0.21626 	# 5.219
v_x_var : float = 0
v_y_var : float = 0

v_x, v_y, v_x_var, v_y_var = listen_to_tunes()


# Grab masterRF from EPICS
# if disconnected, .get() will return none and f_rev with throw exception
masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR')
masterRFact: Union[float, None] = masterRF.get(timeout=1)			# Hz
try:
	f_rev: float = 1e-3 * masterRFact/360 	# kHz # pyright: ignore[reportOperatorIssue] 
except TypeError: # ^ masterRFact might be None
	print("Could not grab master RF from EPICS (weird?). Using default f_rev")


# --- exp variables
direction 					: str	 = 'Y'		# 'X' or 'Y'
tune 						: float	 = v_y 		# v_x or v_y
harmonic 					: int	 = 0		# int >= 0
set_kicker_amp 				: float	 = 0.01 		# %
no_scraper_duration 		: float  = 30 		# seconds
baseline_duration 			: int	 = 30 		# seconds
exp_duration				: int	 = 3 * 60 	# seconds
set_drive_pattern 			: str	 = "1:180"		# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_feedback_mask 			: str	 = "!1:180"	# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_acquisition_mask_SRAM 	: str	 = "!1:180"		# 'num', 'start:stop', '!num' for not num / range, or '!' for all. Should be same as drive pattern. 
set_acquisition_mask_BRAM 	: str	 = "!1:180"	# 'num', 'start:stop', '!num' for not num / range, or '!' for all
set_sweep_period 			: float	 = 1e3 		# us
tune_variance 				: float	 = 1e-4
# if tunes_from_BbB and tune == v_x:
	# tune_variance = v_x_var 
# if tunes_from_BbB and tune == v_y:
	# tune_variance = v_y_var 

# --- Scrapers
set_scraper_upper	: float  = 20.35 	# mm, Default = 20.35, set = 21.50
set_scraper_lower	: float  = 14.20 	# mm, Default = 14.20, set = ???
set_scraper_inner	: float  = 33.50 	# mm, Default = 24.01, set = 34.50

# --- ADC counter masks
set_adc_counter_offset_1: int = 0
set_adc_counter_window_1: int = 8
set_adc_counter_offset_2: int = 8
set_adc_counter_window_2: int = 8


# --- blm DECAY Vgc and att values
# set_decay_Vgc_11A: int = 30
# set_decay_Vgc_11B: int = 30
# set_decay_att_11A: int = 30
# set_decay_att_11B: int = 30


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
print("Initialising PVs...")

# --- assign PVs: BbB Drive
sweep_freq 		= epics.pv.get_pv(f"IGPF:{direction}:DRIVE:FREQ", connect=True)
sweep_span 		= epics.pv.get_pv(f"IGPF:{direction}:DRIVE:SPAN", connect=True)
sweep_period 	= epics.pv.get_pv(f"IGPF:{direction}:DRIVE:PERIOD", connect=True)
kicker_amp 		= epics.pv.get_pv(f"IGPF:{direction}:DRIVE:AMPL", connect=True)
pattern 		= epics.pv.get_pv(f"IGPF:{direction}:DRIVE:PATTERN", connect=True)

# --- assign PVs: current
dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR')

# --- assign PVs: Drive mask
feedback_mask 			= epics.pv.get_pv(f"IGPF:{direction}:FB:PATTERN", connect=True)
acquisition_mask_SRAM 	= epics.pv.get_pv(f"IGPF:{direction}:SRAM:ACQ:PATTERN", connect=True)
acquisition_mask_BRAM 	= epics.pv.get_pv(f"IGPF:{direction}:BRAM:ACQ:PATTERN", connect=True)
# grab initial BbB feedback values to reset on exit
init_feedback_mask 			: Union[str, Any] = feedback_mask.get()
init_acquisition_mask_SRAM 	: Union[str, Any] = acquisition_mask_SRAM.get()
init_acquisition_mask_BRAM 	: Union[str, Any] = acquisition_mask_BRAM.get()

# --- assign PVs : BLMs 
blm = BLMs()
blm.get_loss_PVs()
blm.get_adc_counter_mask_PVs()
time.sleep(2) # give all the PVs a sec to catch up
blm.get_init_adc_counter_masks()
blm.get_settings_PVs()
time.sleep(2) # give all the PVs a sec to catch up
blm.get_init_settings()

# --- assign PVs: scrapers (up, down, left, right)
upper_scraper = Scraper(direction="UPPER")
upper_scraper.connect()
# Scraper Positions as from 12/09/2023: 
#     Upper = 20.35 mm
#     Lower = 14.20 mm
#     Inner = 24.01 mm

# --- assign PVs: ODB beam size and position
ODB_PVs: dict[str, Any] = {}
ODB_PVs["X_size"] 		= epics.pv.get_pv("SR10BM02IMG01:X_SIZE_MONITOR", connect=True)
ODB_PVs["X_offset"] 	= epics.pv.get_pv("SR10BM02IMG01:X_OFFSET_MONITOR", connect=True)
ODB_PVs["Y_size"] 		= epics.pv.get_pv("SR10BM02IMG01:Y_SIZE_MONITOR", connect=True)
ODB_PVs["Y_offset"] 	= epics.pv.get_pv("SR10BM02IMG01:Y_OFFSET_MONITOR", connect=True)

print("PVs grabbed!")

# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
start_datetime 	= datetime.datetime.now()
date_str 	= start_datetime.strftime("%Y-%m-%d")
hours_str 	= start_datetime.strftime("%H%Mh")
seconds_str = start_datetime.strftime("%Ss")
try:
	os.makedirs(os.path.join("drive_betatron", "Data", date_str, hours_str), exist_ok=False)
	data_path = os.path.join("drive_betatron", "Data", date_str, hours_str)
except OSError: 
	# if you run the script again in the same minute, it appends seconds to the path name
	os.makedirs(os.path.join("drive_betatron", "Data", date_str, hours_str, seconds_str))
	data_path = os.path.join("drive_betatron", "Data", date_str, hours_str, seconds_str)


# --- init save vectors
timestamps_datetime : list[datetime.datetime] = []
timestamps_str 		: list[str] = []
current 			: list[Union[str, None]] = []
beam_losses			: dict[str, list[float]] = {}
beam_loss_window_1 	: dict[str, list[float]] = {}
beam_loss_window_2 	: dict[str, list[float]] = {}
for key in blm.loss:
	beam_losses[key] = []
	beam_loss_window_1[key] = []
	beam_loss_window_2[key] = []
ODB_data : dict[str, list[float]] = {}
for key in ODB_PVs:
	ODB_data[key] = []
metadata: dict[str, Any] = {
	"direction": direction, 
	"fractional tune": tune,
	"f_rev (kHz)": f_rev,
	"resonant frequency (kHz)": res_freq,
	"harmonic": harmonic, 
	"kicker amp (%)": set_kicker_amp, 
	"drive pattern": set_drive_pattern, 
	"initial feedback mask": init_feedback_mask,
	"initial acquisition mask (SRAM)": init_acquisition_mask_SRAM,
	"initial acquisition mask (BRAM)": init_acquisition_mask_BRAM,
	"set feedback mask": set_feedback_mask,
	"set acquisition mask (SRAM)": set_acquisition_mask_SRAM,
	"set acquisition mask (BRAM)": set_acquisition_mask_BRAM,
	"scraper UPPER init pos": upper_scraper.init_pos,
	"scraper UPPER set pos" : set_scraper_upper,
	"baseline duration (no scraper)": no_scraper_duration,
	"baseline duration (s)": baseline_duration,
	"experiment duration (s)": exp_duration,
	"start time": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
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


		# # Log data without kicker drive OR SCRAPER enabled for beam loss baseline for 10 s
		# start_time: float = time.time()
		# print("Collecting baseline data WITHOUT SCRAPERS (or kicker) for 10 s...")
		# while (time.time() - start_time) < no_scraper_duration:
		# 	# Nothing goes here... we log at 2 Hz
		# 	time.sleep(0.5)
		# 	# log data at 2 Hz (only relevant to above sleep time)
		# 	log_data()
		# print("Done!")

		# init liberaBLM ADC windows
		print("Changing adc_counter_masks...")
		for key in blm.adc_counter_offset_1:
			blm.adc_counter_offset_1[key].put(set_adc_counter_offset_1)
			blm.adc_counter_window_1[key].put(set_adc_counter_window_1)
			blm.adc_counter_offset_2[key].put(set_adc_counter_offset_2)
			blm.adc_counter_window_2[key].put(set_adc_counter_window_2)

		# init scrapers (put in)
		# Do each scraper individually, a bit safer
		upper_scraper.move(position=set_scraper_upper)

		# change BLM Vgc and atten
		# These are reset on exit
		# print("Changing BLM settings...")
		# blm.decay_Vgc['11A'].put()
		# blm.decay_Vgc['11B'].put()
		# blm.decay_att['11A'].put(set_decay_att_11A)
		# blm.decay_att['11B'].put(set_decay_att_11B)
		# print("BLM settings changed!")


		# Log data without kicker drive enabled for beam loss baseline for 10 s
		start_time: float = time.time()
		print("Collecting baseline data for {0} s...".format(int(baseline_duration)))
		while (time.time() - start_time) < baseline_duration:
			# Nothing goes here... we log at 2 Hz
			time.sleep(0.5)
			# log data at 2 Hz (only relevant to above sleep time)
			log_data()

		# init masks
		print("Changing BbB feedback masks...")
		feedback_mask.put(set_feedback_mask)
		acquisition_mask_SRAM.put(set_acquisition_mask_SRAM)
		acquisition_mask_BRAM.put(set_acquisition_mask_BRAM)

		# init kicker drive
		print("\nTurning on kicker...")
		sweep_span.put(set_sweep_span)		
		sweep_period.put(set_sweep_period)	
		pattern.put(set_drive_pattern)
		sweep_freq.put(res_freq)
		kicker_amp.put(set_kicker_amp)

		last_update_call: float = time.time()

		# start experiment 
		print(f"Collecting driven data for {exp_duration} s...")
		while (time.time() - start_time) <= (exp_duration + baseline_duration):
			# Nothing goes here... we just sit driving at the betatron tune
			time.sleep(0.5)
			# log data at 2 Hz (only relevant to above sleep time)
			log_data()

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
		print("Kicker amp => OFF!")
		# move scrapers back
		upper_scraper.moveOut()
		print("Restoring BbB masks...")
		feedback_mask.put(init_feedback_mask)
		acquisition_mask_SRAM.put(init_acquisition_mask_SRAM)
		acquisition_mask_BRAM.put(init_acquisition_mask_BRAM)
		print("BbB masks restored!")
		# ADC masks and blm settings (Vgc, att)
		blm.restore_inits(mode='adc_counter_masks')
		# cleanup
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
	current.append(dcct.get())			# A
	for key in blm.loss:
		beam_losses[key].append(blm.loss[key].get())	# Counts
		beam_loss_window_1[key].append(blm.adc_counter_loss_1[key].get())
		beam_loss_window_2[key].append(blm.adc_counter_loss_2[key].get())
	for key in ODB_data:
		ODB_data[key].append(ODB_PVs[key].get()) # um
	

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

	# ODB size and offset
	with open(os.path.join(data_path, 'ODB_data.json'), "w") as f:
		json.dump(ODB_data, f)

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