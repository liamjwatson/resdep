from typing import Union, Any
import logging
import traceback
import epics
import time
import datetime
import os
import json
import warnings
import sys
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import numpy.typing as npt 
from scipy.ndimage import gaussian_filter1d
from scipy import stats, optimize


from epicsBLMs import BLMs # Libera BLM python class, stores states, dicts, functions  
from progressBars import printProgressBar
# import plottingModules
# from epicsScrapers import Scraper
# from alignBLMtoFillPattern import alignFillPattern

# --- Constants
# * Fractional spin tune
v_s 		: float = 0.833 				# 6.833
v_s303GeV 	: float = 0.879 				# 6.879, based on if the beam energy is 3.0311 GeV 
# End User Run Machine Parameters (2025-09-28)
v_x 	: float = 0.289148 				# 13.29
v_y 	: float = 0.21626 				# 5.219
v_synch : float	= 0.00847				

#
f_rev 	: float = 1.38799e3 			# kHz
g 		: float = 2.0023193043609236
a_g 	: float = (g - 2)/2
m_e 	: float = 9.109383713928e-31 	# kg
c 		: float = 299792458				# m/s
e 		: float = 1.602176634e-19		# C

# --- exp variables
direction 			: str 	= 'Y'		# 'X' or 'Y'
tune 				: float = v_s303GeV # v_s, or v_s303GeV
harmonic 			: int 	= 0			# int >= 0
bounds 				: float = 0.05/100	# input %, output decimal
set_kicker_amp 		: float = 0.5 		# % (0-1)
set_drive_pattern 	: str 	= "36:215"	# 'start:stop' or '!' for all. Start at '1' not '0'
sweep_direction		: int	= 1			# forward = 1, backward = -1
set_sweep_span 		: float = 0			# kHz
set_sweep_period 	: float = 0 		# us
sweep_rate 			: float = 5			# Hz/s
sweep_step_size 	: float = 0.5 		# Hz - minimum allowable = 0.5
fast_log_frequency	: int 	= 10		# data logging frequency (most variables), Hz
slow_log_frequency	: int 	= 1			# data logging frequency (currently just ODB), Hz
# ADC masks
set_adc_counter_offset_1: int = 0
set_adc_counter_window_1: int = 42
set_adc_counter_offset_2: int = 42
set_adc_counter_window_2: int = 44
# select counting mode; 0: differential, 1: normal (thresholding)
set_counting_mode: int = 0

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
	raise TypeError(
		"set_drive_pattern must be a string of format 'start:stop' or '!' meaning all bunches.\n"
		+ "See Section 5.3 of the iGp12 manual:" 
		+ "https://confluence.synchrotron.org.au/confluence/display/AP/BBB+Feedback?preview=/405733507/405733502/iGp12.pdf#BBBFeedback-TechnicalManual.1"
	)
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
masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR', connect=True)
masterRFact: Union[float, None] = masterRF.get(timeout=5)			# Hz
try:
	f_rev: float = 1e-3 * masterRFact/360 	# kHz # pyright: ignore[reportOperatorIssue] 
except TypeError: # ^ masterRFact might be None
	print("Could not grab master RF from EPICS (weird?). Using default f_rev")

# --- calcs
intrinsic_res_freq 		: float 		= f_rev * (tune + 0)							# 0th order, kHz
res_freq		   		: float 		= f_rev * (tune + harmonic)						# harmoinc order, kHz
expected_energy 		: float 		= (tune+6) * m_e * c**2 / (a_g * e)				# eV
expected_energy_bounds 	: float 		= expected_energy * bounds						# eV
expected_energy_limits 	: list[float] 	= [expected_energy-expected_energy_bounds, expected_energy+expected_energy_bounds] # eV
freq_bounds				: float			= f_rev*((tune+6)*bounds)						# kHz
sweep_limits 			: list[float] 	= [res_freq-freq_bounds, res_freq+freq_bounds] 	# kHz
sweep_range 			: float 		= freq_bounds*2									# kHz
sweep_steps 			: int 			= int(sweep_range*1e3//sweep_step_size) 
sweep_time 				: float 		= sweep_range*1e3/sweep_rate 					# s
dwell_time 				: float 		= sweep_step_size / sweep_rate 					# s
if sweep_direction == -1:
	set_sweep_freq		: float 		= sweep_limits[-1] 								# sweep start (higest frequency for backward scan), kHz
	sweep_end			: float 		= sweep_limits[0]
else:
	set_sweep_freq		: float 		= sweep_limits[0]								# sweep start (lowest frequency for forward scan), kHz
	sweep_end			: float 		= sweep_limits[-1]
print('Estimated sweep time {0}'.format(time.strftime('%H:%M"%S', time.gmtime(sweep_time))))

# ----------------------------------------------------------------------------------------------------------------------------------------------------
# Format energy to freq conversion for plotting
def energy_calc(freq) -> float:
	"""
	Frequency (kHz) -> energy (GeV) conversion
	"""
	return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9)
def freq_calc(energy) -> float:
	"""
	Energy (GeV) -> frequency (kHz) conversion
	"""
	return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)
def tune_calc(energy) -> float:
	"""
	Energy (GeV) to tune conversion
	"""
	return a_g * e * energy * 1e9 / (m_e * c**2)
# ----------------------------------------------------------------------------------------------------------------------------------------------------
#
def model(x, x0, s, A, c):
	"""
	Error function fitting model
	"""
	law = stats.norm(loc=x0, scale=s)
	return A * law.cdf(x) + c

# # --- resonance of competing tunes (betatron, synchrotron)
# print("Calculating and plotting competing tunes resonances (betatron, synchrotron)...")
# # plot these resonances around the expected depolarisation resonance
# fig, axs = plt.subplots(1, 1, figsize=(5,4), layout="tight")
# synchrotron_sidebands = [res_freq + i*(f_rev * v_synch) for i in [-2, -1, 1, 2]]
# for h in range(0,20,1):
# 	v_x_resonance = f_rev * (v_x + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
# 	v_y_resonance = f_rev * (v_y + h) # 300 Hz
# 	v_x_mirror_resonance = f_rev * ((1-v_x) + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
# 	v_y_mirror_resonance = f_rev * ((1-v_y) + h) # 300 Hz
# 	axs.axvline(x=v_x_resonance, ymin=0, ymax=0.7, color="blue", linestyle="-")
# 	axs.axvline(x=v_y_resonance, ymin=0, ymax=0.7, color="green", linestyle="-")
# 	axs.axvline(x=v_x_mirror_resonance, ymin=0, ymax=0.7, color="blue", alpha=0.5, linestyle="-.")
# 	axs.axvline(x=v_y_mirror_resonance, ymin=0, ymax=0.7, color="green", alpha=0.5, linestyle="-.")
# axs.axvline(x=res_freq, ymin=0, ymax=1, color="red", linewidth=2)
# for sideband in synchrotron_sidebands:
# 	axs.axvline(x=sideband, ymin=0, ymax=0.4, color="black", alpha=0.5, linestyle="dotted")
# fig.suptitle("Expected resonances\nwithin the scan range")
# axs.set_xlabel("frequency (kHz)")
# axs.set_xlim(sweep_limits[0], sweep_limits[-1])
# axs.set_yticks([])
# legend_elements = [
# 	Line2D([0], [0], color='red', linewidth=2, label=r"$v_\mathrm{s}$"),
# 	Line2D([0], [0], color='blue', linewidth=1, label=r"$v_x$"),
# 	Line2D([0], [0], color='green', linewidth=1, label=r"$v_y$"),
# 	Line2D([0], [0], color='black', linewidth=1, label=r"$v_\mathrm{synch}$", linestyle="dotted", alpha=0.5),
# 	Line2D([0], [0], color='blue', linewidth=1, label=r"mirror $v_x$", alpha=0.5, linestyle="-."),
# 	Line2D([0], [0], color='green', linewidth=1, label=r"mirror $v_y$", alpha=0.5, linestyle="-."),
# ]                         
# axs.legend(handles=legend_elements, ncols=2)
# # axs.legend([r"$v_\mathrm{s}$", r"$v_x$", r"$v_y$", r"$v_\mathrm{synch}$"])
# # Create energy top axis
# second_axis = axs.secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')
# plt.show(block=False)

response = input("Run the experiment? (y/n): ").strip().lower()
if not response == 'y':
	sys.exit()

# ----------------------------------------------------------------------------------------------------------------------------------------------------
# --- assign PVs : BLMs 
blm = BLMs()
blm.get_loss_PVs()
blm.get_adc_counter_mask_PVs()
blm.get_init_adc_counter_masks()
blm.get_decimation()


# --- assign PVs : drive
sweep_freq_act 	= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:FREQ_ACT', connect=True)
sweep_freq 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:FREQ', connect=True)
sweep_span 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:SPAN', connect=True)
sweep_period 	= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:PERIOD', connect=True)
kicker_amp 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:AMPL', connect=True)
pattern 		= epics.pv.get_pv(f'IGPF:{direction}:DRIVE:PATTERN', connect=True)

# --- assign PVs: current
dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR', connect=True)

# --- assign PVs: scrapers (up, down, left, right)
# upper_scraper = Scraper(direction="UPPER")
# upper_scraper.connect()

# --- assign PVs: ODB beam size and position
ODB_PVs: dict[str, Any] = {}
ODB_PVs["X_size"] 		= epics.pv.get_pv("SR10BM02IMG01:X_SIZE_MONITOR", connect=True)
ODB_PVs["X_offset"] 	= epics.pv.get_pv("SR10BM02IMG01:X_OFFSET_MONITOR", connect=True)
ODB_PVs["Y_size"] 		= epics.pv.get_pv("SR10BM02IMG01:Y_SIZE_MONITOR", connect=True)
ODB_PVs["Y_offset"] 	= epics.pv.get_pv("SR10BM02IMG01:Y_OFFSET_MONITOR", connect=True)

# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
start_time 	= datetime.datetime.now()
date_str 	= start_time.strftime("%Y-%m-%d")
hours_str 	= start_time.strftime("%H%Mh")
seconds_str = start_time.strftime("%Ss")
try:
	os.makedirs(os.path.join("Data", date_str, hours_str), exist_ok=False)
	data_path = os.path.join("Data", date_str, hours_str)
except OSError: 
	# if you run the script again in the same minute, it appends seconds to the path name
	os.makedirs(os.path.join("Data", date_str, hours_str, seconds_str))
	data_path = os.path.join("Data", date_str, hours_str, seconds_str)


# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename=os.path.join(data_path, "logfile.log"),
                    filemode='w')
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger().addHandler(console)


# --- init states
_injecting: bool = False

# --- init save vectors
freqs				: list[Union[float, None]] = []
set_freqs			: list[float] = []
current				: list[Union[float, None]] = []
timestamps_datetime	: list[datetime.datetime] = []
timestamps_str		: list[str] = []
slow_timestamps_datetime	: list[datetime.datetime] = []
slow_timestamps_str		: list[str] = []
injections			: list[datetime.datetime] = []
injections_str		: list[str] = []
beam_losses			: dict[str, list[float]] = {}
beam_loss_window_1 	: dict[str, list[float]] = {}
beam_loss_window_2 	: dict[str, list[float]] = {}
top_up_loss_window_1: dict[str, list[float]] = {}
top_up_loss_window_2: dict[str, list[float]] = {}
for key in blm.loss:
	beam_losses[key] = []
	beam_loss_window_1[key] = []
	beam_loss_window_2[key] = []
ODB_data : dict[str, list[float]] = {}
for key in ODB_PVs:
	ODB_data[key] = []
projected_end_time: datetime.datetime = start_time + datetime.timedelta(seconds=sweep_time)
metadata: dict[str, Any] = {
	"direction": direction, 
	"duration": time.strftime('%H:%M:%S', time.gmtime(sweep_time)), 
	"fractional tune": tune,
	"f_rev": f_rev,
	"bounds (%)": bounds, 
	"frequency bounds (kHz)": freq_bounds, 
	"harmonic": harmonic, 
	"sweep limits (kHz)": sweep_limits, 
	"kicker amp (%)": set_kicker_amp, 
	"drive pattern": set_drive_pattern, 
	"sweep direction": sweep_direction,
	"sweep rate (Hz/s)": sweep_rate, 
	"sweep step size (Hz)": sweep_step_size, 
	"sweep span (kHz)": set_sweep_span, 
	"sweep period (us)": set_sweep_period, 
	"start time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
	"projected end time": projected_end_time.strftime("%Y-%m-%d %H:%M:%S")
}
	# "scraper UPPER init pos": upper_scraper.init_pos,
	# "scraper UPPER set pos" : set_scraper_upper,

# ----------------------------------------------------------------------------------------------------------------------------------------------------
#
def main() -> None:
	"""
	Resonant depolarisation experiment, uses kicker to depolarise bunches, and measures the corresponding beam loss.
	
	Workflow
	--------
	- Initialises kicker (drive) panel with set amplitude and frequency
	- Slowly steps through the requested energy (frequency) range \\
	...(typically at 10 Hz/s, physically updates drive frequency in 0.5 Hz steps)
	- Configures the adc_counts_offset and _window to record beam loss on the polarised and \\
	...depolarised parts of the beam separately
	- The ratio of the depolarised/polarised beam losses will then normalise out spurrious depolarisation events, \\
	...e.g. ID gap changes, magnet instabilities, etc.
	- Reads the beam loss for every monitor and drive frequency (readback at 20 Hz)
	- Employs progress bar in std.out for live updates (1 Hz)
	- Turns off kicker drive and resets BLM gain voltages and attenuations, scrapers \\
	...saves and plots data on experiment end or KeyboardInterrupt

	To be implemented
	-----------------

	"""

	global set_sweep_freq, _injecting

	print('\nBeginning Resonant Depolarisation experiment! Metadata:...')
	for key, value in metadata.items():
		print(f"{key}: {value}")

	try:

		# --- assign PVs: injection trigger
		injection_trigger = epics.pv.get_pv("TS01EVG01:INJECTION_MODE_STATUS", connect=True, callback=(onValueChange))

		# --- update decimation
		blm.apply_full_decimation()
		
		# --- apply masks
		blm.apply_adc_counter_masks(
			offset_1=set_adc_counter_offset_1, 
			window_1=set_adc_counter_window_1,
			offset_2=set_adc_counter_offset_2, 
			window_2=set_adc_counter_window_2,
			counting_mode=set_counting_mode
		)

		# init scrapers (put in)
		# Do each scraper individually, a bit safer
		# upper_scraper.move(position=set_scraper_upper)

		# init kicker drive
		sweep_span.put(set_sweep_span, use_complete=True) 		# kHz
		sweep_period.put(set_sweep_period, use_complete=True)	# us
		pattern.put(set_drive_pattern, use_complete=True)
		kicker_amp.put(set_kicker_amp, use_complete=True)		# %
		# wait for puts to complete
		while not all([
			sweep_span.put_complete,
			sweep_period.put_complete,
			pattern.put_complete,
			kicker_amp.put_complete
		]):
			time.sleep(0.05)

		last_kicker_call	: float = time.time()
		last_fast_log_call	: float = time.time()
		last_slow_log_call	: float = time.time()

		print("|--------------------------------------------|")
		print("|----------- BEGINNING EXPERIMENT -----------|")
		print("|---------- Resonant Depolarisation ---------|")
		print("|--------------------------------------------|")
		print(" Progress:")
		# --- Sweep frequency by stepping through kicker drive frequency setpoint in loop
		step = 0
		# for step in range(0, sweep_steps, 1):
		while step <= sweep_steps:

			# listen for injections
			now = time.time()

			# --- update kicker setpoint at sweep_frequency / step_size
			if (now - last_kicker_call) >= dwell_time:
				# update kicker setpoint
				step += 1
				set_sweep_freq += sweep_direction * sweep_step_size*1e-3 	# kHz
				sweep_freq.put(set_sweep_freq)			# kHz
				last_kicker_call = time.time()

			# --- Call fast_log_data() at fast_log_frequency Hz 
			if (now - last_fast_log_call) >= 1/fast_log_frequency:
				# ? Later implementation -- turn off kicker for 1s before data collection to damp driven betatron oscillations
				# NOTE this doubles experiment time and will have to be updated in the metadata / print statement
				# kicker_amp.put(0)
				# time.sleep(1)
				fast_log_data()
				last_fast_log_call = time.time()
				# kicker_amp.put(set_kicker_amp)

			# --- Update progress bar at 1 Hz
			if (now - last_slow_log_call) >= 1/slow_log_frequency:
				slow_log_data()
				printProgressBar(iteration=step, total=sweep_steps, decimals=2)
				# time_elapsed: datetime.timedelta = datetime.datetime.now() - start_time
				# progress_update(time_elapsed)
				last_slow_log_call = time.time()

			# --- Sleep on injections
			if _injecting:
				# turn off kicker, sleep, turn it back on
				kicker_amp.put(0)
				time.sleep(10)
				kicker_amp.put(set_kicker_amp, use_complete=True)
				while not kicker_amp.put_complete:
					time.sleep(0.05)
				# reset state
				_injecting = False

			# quick sleep so we keep listening for injections
			time.sleep(0.01)

	except KeyboardInterrupt:
		print("\nInterrupted! Kicker amp => OFF.")
	
	finally:
		print("|--------------------------------------------|")
		print("|------------- EXPERIMENT DONE ! ------------|")
		print("|--------------------------------------------|")

		save_data()
		# turn off kicker
		# kicker_amp.put(0, use_complete=True)
		kicker_amp.put(0)
		time.sleep(0.05)
		# while not kicker_amp.put_complete:
		# 	time.sleep(0.05)
		# move scrapers back
		# upper_scraper.moveOut()	
		# restore epicsBLM window settings - change to 'all' for blm settings as well
		# blm.restore_inits(mode="adc_counter_masks")
		# blm.restore_inits(mode="decimation")

		top_up_normalisation(data_rate=fast_log_frequency)
		
		plot_data()
		print('Done everything :)')

	return None
		
# ----------------------------------------------------------------------------------------------------------------------------------------------------
#
# --- PV logger operating at fast_log_frequency Hz
def fast_log_data() -> None:

	"""
	Appends PV values to python lists at fast_log_frequency Hz. \\
	Stored in memory until save_data() is called.

	Saved Values
	------------
	- ADC window loss
	- Kicker frequency
	- Current
	- timestamps
	"""
	try:
		timestamp = datetime.datetime.now()
		timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
		timestamps_datetime.append(timestamp)
		timestamps_str.append(timestamp_str)
		freqs.append(sweep_freq_act.get()) 				# kHz
		set_freqs.append(set_sweep_freq)
		current.append(dcct.get())						# A
		for key in blm.loss:
			# beam_losses[key].append(blm.loss[key].get())	# Counts
			beam_loss_window_1[key].append(blm.adc_counter_loss_1[key].get())
			beam_loss_window_2[key].append(blm.adc_counter_loss_2[key].get())

	except Exception:
		logging.error(traceback.format_exc())

	return None

# ----------------------------------------------------------------------------------------------------------------------------------------------------
#
# --- PV logger operating at slow_log_frequency Hz
def slow_log_data() -> None:
	"""
	Appends PV values to python lists at slow_log_frequency Hz. \\
	Stored in memory until save_data() is called.

	Saved Values
	------------
	- ODB size and offset
	- Emittance monitors
	- timestamps
	"""
	try:
		slow_timestamp = datetime.datetime.now()
		slow_timestamp_str = slow_timestamp.strftime("%Y-%m-%d %H:%M:%S")
		slow_timestamps_datetime.append(slow_timestamp)
		slow_timestamps_str.append(slow_timestamp_str)
		for key in ODB_data:
			ODB_data[key].append(ODB_PVs[key].get()) # um

	except Exception:
		logging.error(traceback.format_exc())

	return None

# --------------------------------------------------------------------------------------------------------------------
#
def top_up_normalisation(data_rate:int) -> None:
	"""
	Normalises the data to the change in the 'charge equivalent' halves of the beam after top-up. \\
	Since the top-up happens to a single bunch, this creates a step change in the *ratio* of the \\
	charge equivalent windows, which looks very much like the depolarisation resonance. 
	"""

	if len(injections) == 0:
		print("No injections detected => no top-up normalisation applied.")
		return None

	# copy loss data to new dicts
	for key in blm.loss:
		top_up_loss_window_1[key] = beam_loss_window_1[key]
		top_up_loss_window_2[key] = beam_loss_window_2[key]
	
	# convert regular timestamps to type: numpy.datetime64
	injections_np: npt.NDArray[np.datetime64] = np.array(injections, dtype="datetime64")
	timestamps_np: npt.NDArray[np.datetime64] = np.array(timestamps_datetime, dtype="datetime64")

	n_seconds_to_average: int = 3
	last_index: int = len(timestamps_np)-1

	try:
		for inj_time in injections_np:
			# find index in dataset that matches (just before) injection time
			index = np.where([inj_time < timestamps_np])[0].tolist()[-1]
			# Make sure there is sufficient data available to average
			if (index == 0) or (index == last_index):
				# ignore injections at very start or end
				continue
			before = index - (n_seconds_to_average/data_rate)
			after  = index + (n_seconds_to_average/data_rate)
			if before < 0:
				before = 0
			if after > last_index:
				after = last_index
			# --- window 1
			for loss in top_up_loss_window_1.values():
				# take the average of the data before and after injection
				mean_before_inj = np.mean(loss[before:index])
				mean_after_inj  = np.mean(loss[index:after])
				# calculate scaling factor for which to scale the data AFTER injection to match that BEFORE injection
				scaling_factor = float(mean_before_inj/mean_after_inj)
				# scale ALL data after injection
				loss[index:] = [value * scaling_factor for value in loss[index:]]
			# --- window 2
			for loss in top_up_loss_window_2.values():
				# take the average of the data before and after injection
				mean_before_inj = np.mean(loss[before:index])
				mean_after_inj  = np.mean(loss[index:after])
				# calculate scaling factor for which to scale the data AFTER injection to match that BEFORE injection
				scaling_factor = float(mean_before_inj/mean_after_inj)
				# scale ALL data after injection
				loss[index:] = [value * scaling_factor for value in loss[index:]]

	except Exception:
		logging.error(traceback.format_exc())

		# ? The data should stop appending while sleeping, so I probably don't need the timedelta...
		# after injection (10s sleep)
		# after_inj = inj_time + datetime.timedelta(seconds=10) 
		

	return None

# --------------------------------------------------------------------------------------------------------------------
#
# populate final values and save metadata
def save_data() -> None:
	"""
	Saves PV data to text, json and csv files depending on structure \\
	Also append entime to metadata and saves to json. \\
	Save path is Data/{YYYY-mm-dd}/{HHHHh}/ \\
	*e.g.* Data/2025-10-20/0900h/
	"""

	try:
		del metadata['projected end time']
		end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		metadata.update({'end time': end_time, 'Last sweep frequency': set_sweep_freq})
		with open(os.path.join(data_path, 'metadata.json'), 'w') as f:
			json.dump(metadata, f)
		

		# freqs as txt
		with open(os.path.join(data_path, 'freqs.txt'), 'w') as f:
				for value in freqs:
					f.write(str(value) + '\n')
		with open(os.path.join(data_path, 'set_freqs.txt'), 'w') as f:
				for value in set_freqs:
					f.write(str(value) + '\n')
		
		# current as txt
		with open(os.path.join(data_path, 'current.txt'), 'w') as f:
				for value in current:
					f.write(str(value) + '\n')

		# timestamps as txt
		with open(os.path.join(data_path, 'timestamps.txt'), 'w') as f:
				for value in timestamps_str:
					f.write(value + '\n')

		# # beam losses, as .json:
		# with open(os.path.join(data_path, 'beam_losses.json'), 'w') as f:
		# 	json.dump(beam_losses, f)

		# ... and .csv:
		# bl_keys = list(beam_losses.keys())
		# bl_rows = zip(*[beam_losses[key] for key in bl_keys])
		# with open(os.path.join(data_path, 'beam_losses.csv'), "w", newline="") as f:
		# 	writer = csv.writer(f)
		# 	writer.writerow(bl_keys)  # headers
		# 	writer.writerows(bl_rows) # values

		# adc counter loss 1
		with open(os.path.join(data_path, 'adc_counter_loss_1.json'), 'w') as f:
			json.dump(beam_loss_window_1, f)
		# adc counter loss 2
		with open(os.path.join(data_path, 'adc_counter_loss_2.json'), 'w') as f:
			json.dump(beam_loss_window_2, f)

		# ODB size and offset
		with open(os.path.join(data_path, 'ODB_data.json'), "w") as f:
			json.dump(ODB_data, f)

		# injection timestamps as txt
		with open(os.path.join(data_path, 'injections.txt'), 'w') as f:
				for value in injections_str:
					f.write(value + '\n')

		with open(os.path.join(data_path, "top-up_loss_window_1.json"), "w") as f:
			json.dump(top_up_loss_window_1, f)
		with open(os.path.join(data_path, "top-up_loss_window_2.json"), "w") as f:
			json.dump(top_up_loss_window_2, f)

	except Exception:
		logging.error(traceback.format_exc())

	print("\n Data saved!")

	return None

# ----------------------------------------------------------------------------------------------------------------------------------------------------
def plot_data() -> None:
	"""
	Plots loss ratio between polarised and depolarised bunches. \\
	Fits error function to sectors with compatible timing with BbB / FPM. \\
	Also plots ODB beam size and offset to check for any major disturbances.
	"""
		
	# ----------------------------------- #
	# ------		Ratio Loss  	----- #
	# ----------------------------------- #

	try:
		ratio_loss: dict[str, Any] = {}
		freqs_array = np.array(freqs)
		fitted_beam_energy_frequencies: dict[str, float] = {}
		fitted_beam_energies: dict[str, float] = {}

		for key in beam_loss_window_1:
			ratio_loss[key] = np.array(beam_loss_window_1[key])/np.array(beam_loss_window_2[key])

		# fit is better when the data is centred on the resonance
		# TODO: Find an automagic way to find this part of the loss spectrum
		start: int = 5000 
		sigma: int = 10
		# Good sectors aligned with depolarised bunch windows (i.e. similar fill patterns to that observed in sector 11)
		sectors: list[str] = ["1", "4", "8", "11", "12", "13"]
		fig, axs = plt.subplots(1,1, figsize=(7,5))
		for sector in sectors:
			# filter / bin
			bend: npt.NDArray[np.float64] = gaussian_filter1d(ratio_loss[f"{sector}B"][start:], sigma)
			# set zero
			bend += np.min(bend)
			# normalise
			bend *= 1/np.max(bend)
			# plot
			axs.plot(freqs_array[start:], bend + 0.03 * float(sector), label=f"{sector}B")

			# -- do fit
			popt, pcov = optimize.curve_fit(model, freqs_array[start:], bend, p0=[1219, 1, 1, 1])
			y_model: npt.NDArray[np.float64] = model(freqs_array[start:], *popt)

			# -- calculate goodness of fit
			# residual sum of squares
			ss_res = np.sum((bend - y_model)**2)
			# total sum of squares
			ss_tot = np.sum((bend - np.mean(bend))**2)
			# r-squared
			r2 = 1 - (ss_res / ss_tot)

			# save in dicts
			fitted_beam_energy_frequencies[f"{sector}B"] = popt[0]  
			fitted_beam_energies[f"{sector}B"] = energy_calc(freq=popt[0])
			print(f"f0={fitted_beam_energy_frequencies[f'{sector}B']:0.3f}, E0={fitted_beam_energies[f'{sector}B']:0.5f}, r^2={r2}")

			# plot baseline
			axs.axhline(y=y_model[0] + 0.03 * float(sector), xmin=0, xmax=1, alpha=0.1, linestyle="--", color="black")
			# plot fit
			axs.plot(freqs_array[start:], y_model + 0.03 * float(sector), linestyle='--', color="red")

		axs.legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
		axs.set_xlim(freqs_array[start], freqs_array[-1])
		# Create energy top axis
		second_axis = axs.secondary_xaxis("top", functions=(energy_calc, freq_calc))
		second_axis.set_xlabel('Energy (GeV)')

		# define sig fig calc:
		def round_to_1(x) -> float:
			return np.round(x, -int(np.floor(np.log10(abs(x)))))

		# calculate 2* st.dev
		f_rdp_mean				: np.floating = np.mean(np.array(list(fitted_beam_energy_frequencies.values())))
		E0_mean					: np.floating = np.mean(np.array(list(fitted_beam_energies.values())))
		E0_stdev				: np.floating = 2*np.std(np.array(list(fitted_beam_energies.values())))
		E0_stdev_sigfig			: float 	  = round_to_1(E0_stdev)
		E0_mean_sigfig			: np.floating = np.round(E0_mean, -int(np.floor(np.log10(abs(E0_stdev)))))
		sideband_energy_shift	: np.floating = E0_mean - energy_calc(f_rdp_mean - f_rev*v_synch)
		expected_sidebands		: list[float] = [energy_calc(f_rdp_mean - 11.756), energy_calc(f_rdp_mean + f_rev*v_synch)]

		print(f"mean E0 = {E0_mean_sigfig} GeV" + u" \u00B1 " + f"{E0_stdev_sigfig*1e6:.0f} keV")
		print(f"Sidebands expected at " + u"(\u00B1" + f"{sideband_energy_shift*1e3:.2f} MeV): " + f"{expected_sidebands[0]:.4f}, {expected_sidebands[1]:.4f}")

		# shade region on plot
		axs.axvspan(xmin=freq_calc(E0_mean-E0_stdev), xmax=freq_calc(E0_mean+E0_stdev), alpha=0.1, color="black")

		plt.savefig(os.path.join(data_path, "ratio_loss.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

		plt.show()

	except Exception:
		logging.error(traceback.format_exc())


	# ----------------------------------- #
	# ------	ODB	beam size  	    ----- #
	# ----------------------------------- #

	try:
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

		plt.savefig(os.path.join(data_path, "ODB_size_and_offset.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

		plt.show()

	except Exception:
		logging.error(traceback.format_exc())

	return None
# ----------------------------------------------------------------------------------------------------------------------------------------------------
#
# --- send log / print every n minutes as update
def progress_update(time_elapsed: datetime.timedelta) -> None:
	"""
	# ! Depreciated !
	Prints elapsed time, expected experiment run time, and progress (percentage) complete to stdout

	Parameters
	----------
	time_elapsed : datetime.timedelta
		Timedelta between start time and now
	"""

	try:
		percentage_complete = int(100*time_elapsed.total_seconds()//sweep_time)
		print("\n{0} elapsed of {1} ({2}%)...".format(str(time_elapsed).split(".")[0], time.strftime('%H:%M:%S', time.gmtime(sweep_time)), percentage_complete))

	except Exception:
		logging.error(traceback.format_exc())

	return None
#
# ----------------------------------------------------------------------------------------------------------------------------------------------------
def onValueChange(pvname=None, value=None, host=None, **kws):
	# * Cannot do .put() or .get() inside callback
	# It looks like .get() works but really I think it's simply getting PV.value which is cached.

	global _injecting

	try:

		if value == 2:
			# record timestamp
			inj_time = datetime.datetime.now()
			inj_time_str = inj_time.strftime("%Y-%m-%d %H:%M:%S")
			injections.append(inj_time)
			injections_str.append(inj_time_str)

			# toggle state
			_injecting = True

	except Exception:
		logging.error(traceback.format_exc())

#
# Initiate experiment
main()