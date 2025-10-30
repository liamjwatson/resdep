from typing import Any, Union
import epics
import time
import datetime
import os
import json
import csv
import warnings
import sys
from matplotlib.pylab import f
import matplotlib.pyplot as plt
import numpy as np
import traceback
from epicsBLMs import epicsBLMs

# --- Constants
# * Fractional spin tune
v_s 		: float = 0.833 				# 6.833
v_s303GeV 	: float = 0.876 				# 6.876, based on if the beam energy is 3.03 GeV 
# End User Run Machine Parameters (2025-09-28)
v_x 	: float = 0.289148 				# 13.29
v_y 	: float = 0.21626 				# 5.219
#
f_rev 	: float = 1.38799e3 			# kHz
g 		: float = 2.0023193043609236
a_g 	: float = (g - 2)/2
m_e 	: float = 9.109383713928e-31 	# kg
c 		: float = 299792458				# m/s
e 		: float = 1.602176634e-19		# C

# --- exp variables
direction 			: str 	= 'Y'		# 'X' or 'Y'
tune 				: float = v_s303GeV # v_s, v_x, or v_y (... or v_s303GeV)
harmonic 			: int 	= 0			# int >= 0
bounds 				: float = 0.3/100	# input %, output decimal
set_kicker_amp 		: float = 1 		# % (0-1)
set_drive_pattern 	: str 	= '!'		# 'start:stop' or '!' for all
set_sweep_span 		: float = 0			# kHz
set_sweep_period 	: float = 0 		# us
sweep_rate 			: float = 10		# Hz/s
sweep_step_size 	: float = 0.5 		# Hz - minimum allowable = 0.5
# --- Scrapers
set_scraper_upper	: float  = 22.00 	# mm
# --- ADC counter masks
set_adc_counter_offset_1: int = 0
set_adc_counter_window_1: int = 8
set_adc_counter_offset_2: int = 8
set_adc_counter_window_2: int = 8


# --- input handling
if direction not in ['X', 'Y', 'Z']:
	raise ValueError("direction must be one of 'X', 'Y' or 'Z'.")
if tune >= 1:
	raise ValueError("tune must be a fractional value.")
if not isinstance(harmonic, int) or harmonic < 0:
	raise ValueError("harmonic must be a positive integer.")
if not 0 <= set_kicker_amp <= 1:
	raise ValueError('set_kicker_amp must be between 0 and 1.')
if not isinstance(set_drive_pattern, str):
	raise TypeError("set_drive_pattern must be a string of format 'start:stop' or '!' meaning all bunches.\nSee Section 5.3 of the iGp12 manual: https://confluence.synchrotron.org.au/confluence/display/AP/BBB+Feedback?preview=/405733507/405733502/iGp12.pdf#BBBFeedback-TechnicalManual.1")
if set_sweep_span < 0:
	raise ValueError('set_sweep_span must be greater than or equal to 0 Hz.')
if sweep_rate <= 0:
	raise ValueError("sweep_rate must be positive and non-zero.")
if sweep_rate > 10:
	warnings.warn("sweep_rate exceeds 10 Hz/s - the dwell time might be too short to effectively depolarise.")
	response = input("Do you want to continue? (y/n): ").strip().lower()
	if not response == 'y':
		sys.exit()
if sweep_step_size < 0.5:
	raise ValueError("sweep_step_size must be larger than 0.5 Hz.")

# Grab masterRF from EPICS
# if disconnected, .get() will return none and f_rev with throw exception
masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR')
masterRFact: Union[float, None] = masterRF.get(timeout=1)			# Hz
try:
	f_rev: float = 1e-3 * masterRFact/360 	# kHz # pyright: ignore[reportOperatorIssue] 
except TypeError: # ^ masterRFact might be None
	print("Could not grab master RF from EPICS (weird?). Using default f_rev")

# --- calcs
intrinsic_res_freq 	: float = f_rev * (tune + 0)							# 0th order, kHz
res_freq		   	: float = f_rev * (tune + harmonic)						# harmoinc order, kHz
if tune in [v_s, v_s303GeV]:
	expected_energy 		: float 		= (tune+6) * m_e * c**2 / (a_g * e)		# eV
	expected_energy_bounds 	: float 		= expected_energy * bounds				# eV
	expected_energy_limits 	: list[float] 	= [expected_energy-expected_energy_bounds, expected_energy+expected_energy_bounds] # eV
	freq_bounds				: float			= f_rev*((tune+6)*bounds)				# kHz
else:
	freq_bounds 			: float 		= intrinsic_res_freq * bounds			# kHz
sweep_limits 	: list[float] 	= [res_freq-freq_bounds, res_freq+freq_bounds] 	# kHz
set_sweep_freq 	: float 		= sweep_limits[0] 								# sweep start, kHz
sweep_range 	: float 		= freq_bounds*2									# kHz
sweep_steps 	: float 		= int(sweep_range*1e3//sweep_step_size) 
sweep_time 		: float 		= sweep_range*1e3/sweep_rate 					# s
dwell_time 		: float 		= sweep_step_size / sweep_rate 					# s
print('Estimated sweep time {0}'.format(time.strftime('%H:%M"%S', time.gmtime(sweep_time))))

response = input("Run the experiment? (y/n): ").strip().lower()
if not response == 'y':
	sys.exit()

# --------------------------------------------------------------------------------------------------------------------
# --- assign PVs : BLMs 
blm = epicsBLMs()
blm.get_loss_PVs()
blm.get_adc_counter_mask_PVs()
time.sleep(2) # give all the PVs a sec to catch up
blm.get_init_adc_counter_masks()
# blm.inits_to_json(mode='adc_counter_masks')

# --- assign PVs : drive
sweep_freq_act 	= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:FREQ_ACT')
sweep_freq 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:FREQ')
sweep_span 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:SPAN')
sweep_period 	= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:PERIOD')
kicker_amp 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:AMPL')
pattern 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:PATTERN')

# --- assign PVs: current
dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR')

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

# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
start_time 	= datetime.datetime.now()
date_str 	= start_time.strftime("%Y-%m-%d")
hours_str 	= start_time.strftime("%H%Mh")
seconds_str = start_time.strftime("%Ss")
try:
	os.makedirs(os.path.join('Data', date_str, hours_str), exist_ok=False)
	data_path = os.path.join('Data', date_str, hours_str)
except OSError: 
	# if you run the script again in the same minute, it appends seconds to the path name
	os.makedirs(os.path.join('Data', date_str, hours_str, seconds_str))
	data_path = os.path.join('Data', date_str, hours_str, seconds_str)

# --- init save vectors
freqs				: list[Union[float, None]] = []
current				: list[Union[float, None]] = []
timestamps_datetime	: list[datetime.datetime] = []
timestamps_str		: list[str] = []
beam_losses			: dict[str, list[float]] = {}
beam_loss_window_1 	: dict[str, list[float]] = {}
beam_loss_window_2 	: dict[str, list[float]] = {}
for key in blm.loss:
	beam_losses[key] = []
	beam_loss_window_1[key] = []
	beam_loss_window_2[key] = []
projected_end_time: datetime.datetime = start_time + datetime.timedelta(seconds=sweep_time)
metadata: dict[str, Any] = {
	'direction': direction, 
	'duration': time.strftime('%H:%M:%S', time.gmtime(sweep_time)), 
	'fractional tune': tune,
	'f_rev': f_rev,
	'bounds (%)': bounds, 
	'frequency bounds (kHz)': freq_bounds, 
	'harmonic': harmonic, 
	'sweep limits (kHz)': sweep_limits, 
	'kicker amp (%)': set_kicker_amp, 
	'drive pattern': set_drive_pattern, 
	'sweep rate (Hz/s)': sweep_rate, 
	'sweep step size (Hz)': sweep_step_size, 
	'sweep span (kHz)': set_sweep_span, 
	'sweep period (us)': set_sweep_period, 
	'scraper UPPER init pos': scrapers['UPPER', 'init_pos'],
	'scraper LOWER init pos': scrapers['LOWER', 'init_pos'],
	'scraper OUTER init pos': scrapers['OUTER', 'init_pos'],
	'scraper INNER init pos': scrapers['INNER', 'init_pos'],
	'scraper UPPER set pos' : set_scraper_upper,
	'start time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
	'projected end time': projected_end_time.strftime("%Y-%m-%d %H:%M:%S")
}

# --------------------------------------------------------------------------------------------------------------------
#
def main():
	"""
	Resonant depolarisation experiment, uses kicker to depolarise bunches, and measures the corresponding beam loss.
	
	Workflow
	--------
		1. Initialises kicker (drive) panel with set amplitude and frequency
		2. Slowly steps through the requested energy (frequency) range 
		...(typically at 10 Hz/s, physically updates drive frequency in 0.5 Hz steps)
		3. Reads the beam loss for every monitor and drive frequency (readback at 1 Hz)
		4. Updates progress to stdout every n_minutes
		5. Turns off kicker drive and resets BLM gain voltages and attenuations, scrapers
		...saves and plots data on experiment end or KeyboardInterrupt

	To be implemented
	-----------------
		1. Changing the adc_counts_offset and _window to record beam loss on the polarised and 
		...depolarised parts of the beam separately
		2. The ratio of the depolarised/polarised beam losses will then normalise out spurrious depolarisation events,
		...e.g. ID gap changes, magnet instabilities, etc.

	"""
	print('\nBeginning Resonant Depolarisation experiment! Metadata:...')
	for key, value in metadata.items():
		print(f"{key}: {value}")

	try:
		# init start time
		log_frequency	: float = 2 			# Hz
		last_log_call	: float = time.time()
		last_update_call: float = time.time()
		n_minutes		: int = 5

		# init liberaBLM ADC windows
		for key in blm.adc_counter_offset_1:
			blm.adc_counter_offset_1[key].put(set_adc_counter_offset_1)
			blm.adc_counter_window_1[key].put(set_adc_counter_window_1)
			blm.adc_counter_offset_2[key].put(set_adc_counter_offset_2)
			blm.adc_counter_window_2[key].put(set_adc_counter_window_2)

		# ! BLM settings - not currently implemented
		# change BLM Vgc and atten
		# These are reset on exit
		# e.g.
		# blm_atten_decay_PVs['11A'].put(30)
		# blm_atten_decay_PVs['11B'].put(30)

		# init scrapers (in)
		scrapers['UPPER', 'sp'].put(set_scraper_upper)
		last_move_time = time.time()
		while scrapers['UPPER', 'motion_status'] == 1:
			time.sleep(0.5)
			# exit loop if motor takes longer than two minutes to move
			if (time.time() - last_move_time) >= 120: # seconds
				print(f"WARNING! UPPER scraper took more than two minutes to move. Continuing...")
				break

		# init kicker drive
		sweep_span.put(set_sweep_span) 		# kHz
		sweep_period.put(set_sweep_period)	# us
		pattern.put(set_drive_pattern)
		set_sweep_freq = sweep_limits[0] 	# kHz
		kicker_amp.put(set_kicker_amp)		# %

		# --- Sweep frequency by stepping through kicker drive frequency setpoint in loop
		while set_sweep_freq < (sweep_limits[-1] + sweep_step_size):
			sweep_freq.put(set_sweep_freq)			# kHz
			set_sweep_freq += sweep_step_size*1e-3 	# kHz
			time.sleep(dwell_time) # propto sweep rate with frequency step

			# --- Call log_data() at 1 Hz 
			if (time.time() - last_log_call) >= 1/log_frequency:
				# ? Later implementation -- turn off kicker for 1s before data collection to damp driven betatron oscillations
				# NOTE this doubles experiment time and will have to be updated in the metadata / print statement
				# kicker_amp.put(0)
				# time.sleep(1)
				log_data()
				last_log_call = time.time()
				# kicker_amp.put(set_kicker_amp)

			# --- Send progress update to the user every n minutes:
			if (time.time() - last_update_call) >= (n_minutes * 60):
				time_elapsed: datetime.timedelta = datetime.datetime.now() - start_time
				progress_update(time_elapsed)
				last_update_call = time.time()

	except KeyboardInterrupt:
		print("\nInterrupted! Kicker amp => OFF, BLM settings => restored, move scrapers back, Saving data...")
	
	finally:
		# turn off kicker
		kicker_amp.put(0)
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
		# restore epicsBLM window settings - change to 'all' for blm settings as well
		blm.restore_inits(mode='adc_counter_masks')
		# cleanup
		save_data()
		plot_all_data()
		plot_data(data=beam_losses, filename='Loss_all_sectors')
		plot_data(data=beam_losses, current_normalised=True, filename='Loss_all_sectors_current_normalised')
		plot_data(data=beam_loss_window_1, filename='Loss_window_1')
		plot_data(data=beam_loss_window_2, filename='Loss_window_2')
		print('\nExperiment finished!')

# --------------------------------------------------------------------------------------------------------------------
#
# --- PV logger operating at 1 Hz
def log_data():
	"""
	Appends PV values to python lists at log_frequency Hz. \\
	Stored in memory until save_data() is called.
	"""
	timestamp = datetime.datetime.now()
	timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
	timestamps_datetime.append(timestamp)
	timestamps_str.append(timestamp_str)
	freqs.append(sweep_freq_act.get()) 				# kHz
	current.append(dcct.get())						# A
	for key in blm.loss:
		beam_losses[key].append(blm.loss[key].get())	# Counts
		beam_loss_window_1[key].append(blm.adc_counter_loss_1[key].get())
		beam_loss_window_2[key].append(blm.adc_counter_loss_2[key].get())

# --------------------------------------------------------------------------------------------------------------------
#
# --- send log / print every n minutes as update
def progress_update(time_elapsed: datetime.timedelta):
	"""
	Prints elapsed time, expected experiment run time, and progress (percentage) complete to stdout

	Parameters
	----------
	time_elapsed : datetime.timedelta
		Timedelta between start time and now
	"""
	percentage_complete = int(100*time_elapsed.total_seconds()//sweep_time)
	print("\n{0} elapsed of {1} ({2}%)...".format(str(time_elapsed).split(".")[0], time.strftime('%H:%M:%S', time.gmtime(sweep_time)), percentage_complete))


# --------------------------------------------------------------------------------------------------------------------
#
# populate final values and save metadata
def save_data():
	"""
	Saves PV data to text, json and csv files depending on structure \\
	Also append entime to metadata and saves to json. \\
	Save path is Data/{YYYY-mm-dd}/{HHHHh}/ \\
	*e.g.* Data/2025-10-20/0900h/
	"""
	del metadata['projected end time']
	end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	metadata.update({'end time': end_time, 'Last sweep frequency': set_sweep_freq})
	with open(os.path.join(data_path, 'metadata.json'), 'w') as f:
		json.dump(metadata, f)
	

	# freqs as txt
	with open(os.path.join(data_path, 'freqs.txt'), 'w') as f:
			for value in freqs:
				f.write(str(value) + '\n')
	
	# current as txt
	with open(os.path.join(data_path, 'current.txt'), 'w') as f:
			for value in current:
				f.write(str(value) + '\n')

	# timestamps as txt
	with open(os.path.join(data_path, 'timestamps.txt'), 'w') as f:
			for value in timestamps_str:
				f.write(value + '\n')

	# beam losses, as both .json:
	with open(os.path.join(data_path, 'beam_losses.json'), 'w') as f:
		json.dump(beam_losses, f)

	# adc counter loss 1
	with open(os.path.join(data_path, 'adc_counter_loss_1.json')) as f:
		json.dump(blm.adc_counter_loss_1, f)

	# adc counter loss 2
	with open(os.path.join(data_path, 'adc_counter_loss_2.json')) as f:
		json.dump(blm.adc_counter_loss_2, f)
	
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
# Format energy to freq conversion for plotting
def energy_calc(freq):
	return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9)
def freq_calc(energy):
	return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)

# --------------------------------------------------------------------------------------------------------------------
#
def plot_all_data():
	"""
	Plots every BLM against frequency and energy (conversion from frequency, plotted on top axis
	"""
	try:
		# convert to array
		freqs_array = np.array(freqs)

		# --- plot data
		fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# plot normalised data:
		for index, key in enumerate(beam_losses):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs[0].plot(freqs_array, beam_losses[key]/np.max(beam_losses[key]) - 0.15*index, '-', label=key)
			else:
				axs[0].plot(freqs_array, beam_losses[key]/np.max(beam_losses[key]) - 0.15*index, '-', color='k', label=key)	
			axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs[0].set_title('All sectors')
		axs[0].set_xlabel('frequency (kHz)')

		second_axis = axs[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis.set_xlabel('Energy (GeV)')

		# plot just sector 11 (normalised)
		axs[1].plot(freqs_array, beam_losses['11A']/np.max(beam_losses['11A']), '-', label='11A')
		axs[1].plot(freqs_array, beam_losses['11B']/np.max(beam_losses['11B']) + 0.15, '-', label='11B')
		axs[1].legend(loc='lower right')
		axs[1].set_title('Sector 11')

		plt.savefig(os.path.join(data_path, "All_sectors_beam_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)



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
				axs2[0].plot(freqs_array, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', label=key)
			else:
				axs2[0].plot(freqs_array, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', color='k', label=key)	
			axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs2[0].set_title('All sectors (current normalised)')

		second_axis2 = axs2[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis2.set_xlabel('Energy (GeV)')

		# plot just sector 11 (normalised)
		axs2[1].plot(freqs_array, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
		axs2[1].plot(freqs_array, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
		axs2[1].legend(loc='lower right')
		axs2[1].set_title('Sector 11 (current normalised)')

		plt.savefig(os.path.join(data_path, "current_normalised_all_sectors_beam_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

		plt.show()


		# ----------------------------------- #
		# ------	ADC counter loss 	----- #
		# ----------------------------------- #
		#

		# --- plot data
		fig3, axs3 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# plot normalised data:
		for index, key in enumerate(blm.adc_counter_loss_1):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs3[0].plot(freqs_array, blm.adc_counter_loss_1[key]/np.max(blm.adc_counter_loss_1[key]) - 0.15*index, '-', label=key)
			else:
				axs3[0].plot(freqs_array, blm.adc_counter_loss_1[key]/np.max(blm.adc_counter_loss_1[key]) - 0.15*index, '-', color='k', label=key)	
			axs3[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs3[0].set_title('ADC counter loss 1 - All sectors')
		axs3[0].set_xlabel('frequency (kHz)')

		# Create energy top axis
		second_axis = axs3[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis.set_xlabel('Energy (GeV)')

		# plot just sector 11 (normalised)
		axs3[1].plot(freqs_array, blm.adc_counter_loss_1['11A']/np.max(blm.adc_counter_loss_1['11A']), '-', label='11A')
		axs3[1].plot(freqs_array, blm.adc_counter_loss_1['11B']/np.max(blm.adc_counter_loss_1['11B']) + 0.15, '-', label='11B')
		axs3[1].legend(loc='lower right')
		axs3[1].set_title('Sector 11')

		plt.savefig(os.path.join(data_path, "ADC_counter_loss_1.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
		
		
		# --- plot data
		fig4, axs4 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# plot normalised data:
		for index, key in enumerate(blm.adc_counter_loss_2):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs4[0].plot(freqs_array, blm.adc_counter_loss_2[key]/np.max(blm.adc_counter_loss_2[key]) - 0.15*index, '-', label=key)
			else:
				axs4[0].plot(freqs_array, blm.adc_counter_loss_2[key]/np.max(blm.adc_counter_loss_2[key]) - 0.15*index, '-', color='k', label=key)	
			axs4[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs4[0].set_title('ADC counter loss 2 - All sectors')
		axs4[0].set_xlabel('frequency (kHz)')

		# Create energy top axis
		second_axis = axs4[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis.set_xlabel('Energy (GeV)')

		# plot just sector 11 (normalised)
		axs4[1].plot(freqs_array, blm.adc_counter_loss_2['11A']/np.max(blm.adc_counter_loss_2['11A']), '-', label='11A')
		axs4[1].plot(freqs_array, blm.adc_counter_loss_2['11B']/np.max(blm.adc_counter_loss_2['11B']) + 0.15, '-', label='11B')
		axs4[1].legend(loc='lower right')
		axs4[1].set_title('Sector 11')

		plt.savefig(os.path.join(data_path, "adc_counter_loss_2.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
	
	# Dont stop if plotting goes wrong
	finally:
		pass
#
# --------------------------------------------------------------------------------------------------------------------
def plot_data(data: dict[str, list[float]], current_normalised: bool = False, filename: str = 'default'):
	"""
	Plots every BLM against frequency and energy (conversion from frequency, plotted on top axis)

	Parameters
	----------
	data: dict[str, list[float]]
		Beam loss data which is a dictonary, containing loss for each sector and section
	current_normalised: bool
		Switch for (beam) current normalisation (yes/no)
	filename: str
		Filename for saving the plot .png
	"""
	try:
		# convert to array
		freqs_array = np.array(freqs)

		# --- normalise data
		data_norm = {}
		if current_normalised:
			data_current_norm = {}
			for key in data:
				data_current_norm[key] = np.array(data[key])/(np.array(current)**2)
				data_norm[key] = data_current_norm[key]/np.max(data_current_norm[key])
		else:
			for key in data:
				data_norm[key] = data[key]/np.max(data[key])
		
		
		# --- plot data
		fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

		# plot normalised data:
		
		for index, key in enumerate(data_norm):
			# Colour straight, make corresponding arc black
			if index % 2 == 0:
				axs[0].plot(freqs_array, data_norm[key] - 0.15*index, '-', label=key)
			else:
				axs[0].plot(freqs_array, data_norm[key] - 0.15*index, '-', color='k', label=key)	
			axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs[0].set_title('All sectors')
		axs[0].set_xlabel('frequency (kHz)')

		# Create energy top axis
		second_axis = axs[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis.set_xlabel('Energy (GeV)')

		# plot just sector 11 (normalised)
		axs[1].plot(freqs_array, data_norm['11A'], '-', label='11A')
		axs[1].plot(freqs_array, data_norm['11B'] + 0.15, '-', label='11B')
		axs[1].legend(loc='lower right')
		axs[1].set_title('Sector 11')

		# if no filename, pass datetime stamp
		if filename == 'default':
			filename = datetime.datetime.now().strftime("%y%m%d_%H%M%S")

		plt.savefig(os.path.join(data_path, filename, '.png'), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
	
	finally:
		# I dont want the code to finish if plotting throws an error
		pass
#
# Initiate experiment
main()