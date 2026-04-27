"""
Resonant depolarisation experiment (class) \\
Designed to called through one of the GUIs (resdepGUI, simpleGUI) \\
Can also be instanced and run natively in command line.
"""
"""
██████╗ ███████╗███████╗ ██████╗ ███╗   ██╗ █████╗ ███╗   ██╗████████╗  
██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗████╗  ██║╚══██╔══╝  
██████╔╝█████╗  ███████╗██║   ██║██╔██╗ ██║███████║██╔██╗ ██║   ██║     
██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╗██║██╔══██║██║╚██╗██║   ██║     
██║  ██║███████╗███████║╚██████╔╝██║ ╚████║██║  ██║██║ ╚████║   ██║     
╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝     
██████╗ ███████╗██████╗  ██████╗ ██╗      █████╗ ██████╗ ██╗███████╗ █████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██╔══██╗██╔════╝██╔══██╗██╔═══██╗██║     ██╔══██╗██╔══██╗██║██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║  ██║█████╗  ██████╔╝██║   ██║██║     ███████║██████╔╝██║███████╗███████║   ██║   ██║██║   ██║██╔██╗ ██║
██║  ██║██╔══╝  ██╔═══╝ ██║   ██║██║     ██╔══██║██╔══██╗██║╚════██║██╔══██║   ██║   ██║██║   ██║██║╚██╗██║
██████╔╝███████╗██║     ╚██████╔╝███████╗██║  ██║██║  ██║██║███████║██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║
╚═════╝ ╚══════╝╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
███████╗██╗  ██╗██████╗ ███████╗██████╗ ██╗███╗   ███╗███████╗███╗   ██╗████████╗
██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔══██╗██║████╗ ████║██╔════╝████╗  ██║╚══██╔══╝
█████╗   ╚███╔╝ ██████╔╝█████╗  ██████╔╝██║██╔████╔██║█████╗  ██╔██╗ ██║   ██║   
██╔══╝   ██╔██╗ ██╔═══╝ ██╔══╝  ██╔══██╗██║██║╚██╔╝██║██╔══╝  ██║╚██╗██║   ██║   
███████╗██╔╝ ██╗██║     ███████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║ ╚████║   ██║   
╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝                                                                           
"""

from dataclasses import dataclass, field
import platform
import builtins
from typing import Union, Any
import logging, traceback, warnings
import epics
import time, datetime
from pathlib import Path
import json
from matplotlib.backend_bases import FigureCanvasBase
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt 
from scipy.ndimage import gaussian_filter1d

from resdep.epicsBLMs import BLMs # Libera BLM python class, stores states, dicts, functions
from resdep.epicsBPMs import SR_BPMs, MX3_BPMs, TBPMs # BPM subclasses
from resdep._plotting import PlottingClass, Graph
from resdep._progressBars import printProgressBar


class ResonantDepolarisation():
	"""
	Resdep class that holds its own objects (constants, calculation, data) \\
	and member functions that run and plot the data.

	Is written to (optionally) take in additional Qt callback functionality, but is not required.
	"""

	# variables defined here change across all instances of ResonantDepolarisation.
	# We only expect one instance at a time
	
	# --- Constants
	g 			: float = 2.0023193043609236
	a_g 		: float = (g - 2)/2
	m_e 		: float = 9.109383713928e-31 	# kg
	c 			: float = 299792458				# m/s
	e 			: float = 1.602176634e-19		# C
	# * Fractional spin tune
	v_s 		: float = 0.833 				# 6.833
	v_s303GeV 	: float = 0.879 				# 6.879, based on if the beam energy is 3.0311 GeV 
	# End User Run Machine Parameters (2025-09-28)
	v_x 		: float = 0.289148 				# 13.29
	v_y 		: float = 0.21626 				# 5.219
	v_synch 	: float	= 0.00847				


	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	#
	def __init__(self, *, progress_callback=None, plot_callback=None, status_callback=None, data_path_callback=None, timer_callback=None, ADC_windows_callback=None) -> None:
		
		# --- init callbacks for Qt functionality
		self.progress_callback 		= progress_callback 	or (lambda *args, **kwargs: None)
		self.plot_callback 			= plot_callback 		or (lambda *args, **kwargs: None)
		self.status_callback 		= status_callback 		or (lambda *args, **kwargs: None)
		self.data_path_callback 	= data_path_callback 	or (lambda *args, **kwargs: None)
		self.timer_callback 		= timer_callback 		or (lambda *args, **kwargs: None)
		self.ADC_windows_callback 	= ADC_windows_callback 	or (lambda *args, **kwargs: None)
		self._abort_requested 		= False

		# --- init states
		self._injecting		: bool = False
		self._measuring_MX3	: bool = False

		# default f_rev. Will calculate f_rev from masterRF on experiment start 
		# (so we dont have any epics connection on GUI start)
		self.f_rev 	: float = 1.38799e3 # kHz

		# --- exp variables
		self.direction 			: str 	= 'Y'		# 'X' or 'Y'
		self.tune 				: float = self.v_s303GeV # v_s, or v_s303GeV
		self.harmonic 			: int 	= 1			# int >= 0
		self.bounds 			: float = 0.05/100	# input %, output decimal
		self.freq_shift			: float = 0			# shifting off calculated resonance, KHz
		self.set_kicker_amp 	: float = 0.5		# % (0-1)
		self.set_drive_pattern 	: str 	= "36:215"	# 'start:stop' or '!' for all. Start at '1' not '0'
		self.sweep_direction	: int	= 1			# forward = 1, backward = -1
		self.set_sweep_span 	: float = 0			# kHz
		self.set_sweep_period 	: float = 0 		# us
		self.sweep_rate 		: float = 5			# Hz/s
		self.sweep_step_size 	: float = 0.5 		# Hz - minimum allowable = 0.5
		self.fast_log_frequency	: int 	= 10		# data logging frequency (most variables), Hz
		self.slow_log_frequency	: int 	= 1			# data logging frequency (currently just ODB), Hz
		# ADC masks
		self.set_adc_counter_offset_1: int = 0
		self.set_adc_counter_window_1: int = 42
		self.set_adc_counter_offset_2: int = 42
		self.set_adc_counter_window_2: int = 44
		# select counting mode; 0: differential, 1: normal (thresholding)
		self.set_counting_mode		 : int = 0

		# initialise some data storage early for GUI plot purposes
		self.freqs						: list[float] = []
		self.beam_loss_window_1 		: dict[str, list[float]] = {}
		self.beam_loss_window_2 		: dict[str, list[float]] = {}
		self.res_freq 					: float = 1225

		# do calcs
		self.calculate_range()

		return None
	
	# *--------------------------------* #
	# *---------- Experiment ----------* #
	# *--------------------------------* #
	
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def start_experiment(self, ) -> None:
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

		try:
			if self.status_callback:
				self.status_callback("Status: Setting up PVs...")

			# --- start-up
			self.calcf_revfromMasterRF()
			self.calculate_range()
			self.load_PVs()
			self.config_save_files()

			self.injection_trigger.add_callback(callback=self.onValueChange)
			self.calculate_adc_counter_windows()

			# --- update decimation
			self.blm.apply_full_decimation()
			
			# --- apply masks
			self.blm.apply_adc_counter_masks(
				offset_1=self.set_adc_counter_offset_1, 
				window_1=self.set_adc_counter_window_1,
				offset_2=self.set_adc_counter_offset_2, 
				window_2=self.set_adc_counter_window_2,
				counting_mode=self.set_counting_mode
			)

			# init kicker drive
			self.sweep_freq.put(self.set_sweep_freq, use_complete=True)		# kHz
			self.sweep_span.put(self.set_sweep_span, use_complete=True) 	# kHz
			self.sweep_period.put(self.set_sweep_period, use_complete=True)	# us
			self.pattern.put(self.set_drive_pattern, use_complete=True)
			# wait for puts to complete
			while not all([
				self.sweep_freq.put_complete,
				self.sweep_span.put_complete,
				self.sweep_period.put_complete,
				self.pattern.put_complete,
			]):
				time.sleep(0.05)
				

			last_slow_log_call	: float = time.time()

			print("|--------------------------------------------|")
			print("|----------- BEGINNING EXPERIMENT -----------|")
			print("|---------- Resonant Depolarisation ---------|")
			print("|--------------------------------------------|")

			# ---------------------------------------------------------------------------------
			# --- Collect baseline data (BPMs)
			end = time.time() + 10
			if self.status_callback:
				self.status_callback("Status: Collecting baseline BPM data (10 s)...")
			else:
				print("Status: Collecting baseline BPM data (10 s)...")

			while time.time() <= end:
				now = time.time()
				self.fast_log_data()
				if (now - last_slow_log_call) >= 1/self.slow_log_frequency:
					self.slow_log_data()
					last_slow_log_call = time.time()
				# --- abort if signal is sent from GUI
				if self._abort_requested:
					if self.status_callback:
						self.status_callback("Status: Experiment interrupted!")
					# go to finally block
					raise KeyboardInterrupt
				
				time.sleep(1/self.fast_log_frequency)

			# --- turn on kicker, prep for frequency sweep
			self.kicker_amp.put(self.set_kicker_amp, use_complete=True)		# %
			while not self.kicker_amp.put_complete:
				time.sleep(0.05)

			last_kicker_call	: float = time.time()
			last_fast_log_call	: float = time.time()

			self.step: int = 0
			if self.status_callback:
				self.status_callback("Status: Running")
			if self.timer_callback:
				self.timer_callback()

			# ---------------------------------------------------------------------------------
			# --- Sweep frequency by stepping through kicker drive frequency setpoint in loop
			while self.step <= self.sweep_steps:

				# listen for injections
				now = time.time()

				# --- update kicker setpoint at sweep_frequency / step_size
				if (now - last_kicker_call) >= self.dwell_time:
					# update kicker setpoint
					self.step += 1
					self.set_sweep_freq += self.sweep_direction * self.sweep_step_size*1e-3 	# kHz
					self.sweep_freq.put(self.set_sweep_freq)			# kHz
					last_kicker_call = time.time()

				# --- Call fast_log_data() at fast_log_frequency Hz 
				if (now - last_fast_log_call) >= 1/self.fast_log_frequency:
					self.fast_log_data()
					last_fast_log_call = time.time()

				# --- Update progress bar, plot and ODB at 1 Hz
				if (now - last_slow_log_call) >= 1/self.slow_log_frequency:
					self.slow_log_data()
					# update progress to QtGUI 
					if self.progress_callback:
						self.progress_callback(self.step)
					else: # or std.out
						printProgressBar(iteration=self.step, total=self.sweep_steps, decimals=2)
					# push plot data to GUI
					if self.plot_callback:
						self.plot_callback(self.freqs, self.beam_loss_window_1, self.beam_loss_window_2)
					# reset trigger
					last_slow_log_call = time.time()

				# --- Sleep on injections
				if self._injecting:
					# turn off kicker
					self.kicker_amp.put(0)
					# update status to GUI
					if self.status_callback:
						self.status_callback("Status: Sleeping (injection)")

					self.interruptible_sleep(10)
					
					# turn kicker back on
					self.kicker_amp.put(self.set_kicker_amp, use_complete=True)
					while not self.kicker_amp.put_complete:
						time.sleep(0.05)
					# reset GUI status
					if self.status_callback:
						self.status_callback("Status: Running")
					# reset state
					self._injecting = False

				# --- abort if signal is sent from GUI
				if self._abort_requested:
					if self.status_callback:
						self.status_callback("Status: Experiment interrupted!")
					break

				# quick sleep so we keep listening for injections
				time.sleep(0.01)

		except Exception:
			logging.error(traceback.format_exc())
		
		finally:
			print("|--------------------------------------------|")
			print("|------------- EXPERIMENT DONE ! ------------|")
			print("|--------------------------------------------|")

			if self.status_callback:
				self.status_callback("Status: Cleaning up...")

			if self.progress_callback:
				self.progress_callback(self.sweep_steps)

			self.save_data()

			# turn off kicker
			self.kicker_amp.put(0, use_complete=True)
			print("Kicker set to off.")
			time.sleep(0.05)
			print("Waiting for kicker put_complete...")
			while not self.kicker_amp.put_complete:
				time.sleep(0.05)
			print("Kicker OFF!")

			self.injection_trigger.clear_callbacks()

			# restore epicsBLM window settings
			print("attempting to restore BLM inits...")
			self.blm.restore_inits(mode="adc_counter_masks")
			self.blm.restore_inits(mode="decimation")
			
			print('Done everything :)')

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def calculate_range(self, ) -> None:

		# --- calcs
		self.intrinsic_res_freq 	: float 		= self.f_rev * (self.tune + 0) + self.freq_shift				# 0th order, kHz
		self.res_freq		   		: float 		= self.f_rev * (self.tune + self.harmonic) + self.freq_shift	# harmoinc order, kHz
		self.expected_energy 		: float 		= (self.tune+6) * self.m_e * self.c**2 / (self.a_g * self.e) 	# eV
		self.expected_energy_bounds : float 		= self.expected_energy * self.bounds						 	# eV
		self.expected_energy_limits : list[float] 	= [self.expected_energy - self.expected_energy_bounds, self.expected_energy + self.expected_energy_bounds] # eV
		self.freq_bounds			: float			= self.f_rev*((self.tune + 6)*self.bounds)						# kHz
		self.sweep_limits 			: list[float] 	= [self.res_freq-self.freq_bounds, self.res_freq+self.freq_bounds] 	# kHz
		self.sweep_range 			: float 		= self.freq_bounds*2											# kHz
		self.sweep_steps 			: int 			= int(self.sweep_range*1e3//self.sweep_step_size) 
		self.sweep_time 			: float 		= self.sweep_range*1e3/self.sweep_rate 							# s
		self.dwell_time 			: float 		= self.sweep_step_size / self.sweep_rate 						# s
		if self.sweep_direction == -1:
			self.set_sweep_freq: float = self.sweep_limits[-1] 	# sweep start (higest frequency for backward scan), kHz
			self.sweep_end	  : float = self.sweep_limits[0]
		else:
			self.set_sweep_freq: float = self.sweep_limits[0]	# sweep start (lowest frequency for forward scan), kHz
			self.sweep_end	  : float = self.sweep_limits[-1]

		number_of_top_ups = self.sweep_time//137 # every 2'17"
		self.estimated_sweep_time: str = str(datetime.timedelta(seconds=int(self.sweep_time + 10*number_of_top_ups)))
		# print('Estimated sweep time {0}'.format(time.strftime('%H:%M"%S', time.gmtime(self.sweep_time))))

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def load_PVs(self, ) -> None:
		# --- BLMs 
		self.blm = BLMs()
		self.blm.get_loss_PVs()
		self.blm.get_adc_counter_mask_PVs()
		self.blm.get_init_adc_counter_masks()
		self.blm.get_decimation()
		self.blm.get_t2_trigger_delays()

		# --- BPMs
		# Storage ring
		self.sr_bpms = SR_BPMs()
		self.sr_bpms.connect()
		# TBPMs
		self.tbpms = TBPMs()
		self.tbpms.connect()
		# MX3
		if self._measuring_MX3:
			self.mx3_bpms = MX3_BPMs()
			self.mx3_bpms.connect()

		# --- drive
		self.sweep_freq_act = epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:FREQ_ACT', connect=True)
		self.sweep_freq 	= epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:FREQ', connect=True)
		self.sweep_span 	= epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:SPAN', connect=True)
		self.sweep_period 	= epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:PERIOD', connect=True)
		self.kicker_amp 	= epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:AMPL', connect=True)
		self.pattern 		= epics.pv.get_pv(f'IGPF:{self.direction}:DRIVE:PATTERN', connect=True)

		# --- current
		self.dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR', connect=True)

		# --- injection trigger
		self.injection_trigger = epics.pv.get_pv("TS01EVG01:INJECTION_MODE_STATUS", connect=True)

		# --- ODB beam size and position
		self.ODB_PVs: dict[str, Any] = {}
		self.ODB_PVs["X_size"] 		 = epics.pv.get_pv("SR10BM02IMG01:X_SIZE_MONITOR", connect=True)
		self.ODB_PVs["X_offset"] 	 = epics.pv.get_pv("SR10BM02IMG01:X_OFFSET_MONITOR", connect=True)
		self.ODB_PVs["Y_size"] 		 = epics.pv.get_pv("SR10BM02IMG01:Y_SIZE_MONITOR", connect=True)
		self.ODB_PVs["Y_offset"] 	 = epics.pv.get_pv("SR10BM02IMG01:Y_OFFSET_MONITOR", connect=True)\

		# --- SR/LCW/RF temperatures
		# initialise PV dicts
		self.RF601_LCW_temperature_PVs	: dict[str, Any] = {}
		self.RF602_LCW_temperature_PVs	: dict[str, Any] = {}
		self.RF701_LCW_temperature_PVs	: dict[str, Any] = {}
		self.RF702_LCW_temperature_PVs	: dict[str, Any] = {}
		
		self.RF601_body_temperature_PVs	: dict[str, Any] = {}
		self.RF602_body_temperature_PVs	: dict[str, Any] = {}
		self.RF701_body_temperature_PVs	: dict[str, Any] = {}
		self.RF702_body_temperature_PVs	: dict[str, Any] = {}

		self.magnet_temperature_PVs		: dict[str, Any] = {}
		self.tunnel_air_temperature_PVs	: dict[str, Any] = {}
		self.beam_pipe_temperature_PVs	: dict[str, Any] = {}
		self.slab_temperature_PVs		: dict[str, Any] = {}
		self.SUBH_temperature_PVs		: dict[str, Any] = {}

		self.temperature_PV_dicts = [
			self.RF601_LCW_temperature_PVs,
			self.RF602_LCW_temperature_PVs,
			self.RF701_LCW_temperature_PVs,
			self.RF702_LCW_temperature_PVs,
			self.RF601_body_temperature_PVs,
			self.RF602_body_temperature_PVs,
			self.RF701_body_temperature_PVs,
			self.RF702_body_temperature_PVs,
			self.magnet_temperature_PVs,
			self.tunnel_air_temperature_PVs,
			self.beam_pipe_temperature_PVs,
			self.slab_temperature_PVs,
			self.SUBH_temperature_PVs		
		]

		# grab PVs
		cavities = ["601", "602", "701", "702"]
		# RF LCW
		for cavity, PV_dict in zip(
			cavities,
			[self.RF601_LCW_temperature_PVs,
			self.RF602_LCW_temperature_PVs,
			self.RF701_LCW_temperature_PVs,
			self.RF702_LCW_temperature_PVs]
		):
			prefix = f"SR0{cavity[0]}RF0{cavity[-1]}"
			PV_dict[f"{prefix}RLD01:INLET_WATER_TEMP_MONITOR"]  = epics.pv.get_pv(f"{prefix}RLD01:INLET_WATER_TEMP_MONITOR", connect=True)
			PV_dict[f"{prefix}CIR01:INLET_WATER_TEMP_MONITOR"]  = epics.pv.get_pv(f"{prefix}CIR01:INLET_WATER_TEMP_MONITOR", connect=True)
			PV_dict[f"{prefix}KLY01:BODY_INLET_TEMP_MONITOR"]   = epics.pv.get_pv(f"{prefix}KLY01:BODY_INLET_TEMP_MONITOR", connect=True)
			PV_dict[f"{prefix}CAV01:INLET_TEMPERATURE_MONITOR"] = epics.pv.get_pv(f"{prefix}CAV01:INLET_TEMPERATURE_MONITOR", connect=True)
			
		# RF body
		for cavity, PV_dict in zip(
			cavities,
			[
			self.RF601_body_temperature_PVs,
			self.RF602_body_temperature_PVs,
			self.RF701_body_temperature_PVs,
			self.RF702_body_temperature_PVs]
		):
			prefix = f"SR0{cavity[0]}RF0{cavity[-1]}TES"
			for i in range(1, 14+1, 1):
				PV_dict[f"{prefix}{i:02d}:TEMPERATURE_MONITOR"] = epics.pv.get_pv(f"{prefix}{i:02d}:TEMPERATURE_MONITOR", connect=True)
			prefix = f"SR0{cavity[0]}RF0{cavity[-1]}CIR01"
			PV_dict[f"{prefix}:RF_TEMP_MONITOR"]  				= epics.pv.get_pv(f"{prefix}:RF_TEMP_MONITOR", connect=True)
			PV_dict[f"{prefix}:REGULATOR_TEMP_MONITOR"]  		= epics.pv.get_pv(f"{prefix}:REGULATOR_TEMP_MONITOR", connect=True)
			PV_dict[f"{prefix}:SHUNT_TEMP_MONITOR"]  			= epics.pv.get_pv(f"{prefix}:SHUNT_TEMP_MONITOR", connect=True)
			
		# magnets
		magnet_temperature_PV_names = [
			"SR01TES02:TEMPERATURE_MONITOR",
			"SR01TES05:TEMPERATURE_MONITOR",
			"SR01TES06:TEMPERATURE_MONITOR",
			"SR09TES07:TEMPERATURE_MONITOR",
			"SR09TES08:TEMPERATURE_MONITOR",
			"SR09TES11:TEMPERATURE_MONITOR",
			"SR12TES01:TEMPERATURE_MONITOR"
		]
		for PV_name in magnet_temperature_PV_names:
			self.magnet_temperature_PVs[PV_name] = epics.pv.get_pv(PV_name, connect=True)

		# tunnel air temp
		tunnel_air_temperature_PV_names = [
			"SR01TES03:TEMPERATURE_MONITOR",
			"SR06TES01:TEMPERATURE_MONITOR",
			"SR07TES01:TEMPERATURE_MONITOR"
		]
		for PV_name in tunnel_air_temperature_PV_names:
			self.tunnel_air_temperature_PVs[PV_name] = epics.pv.get_pv(PV_name, connect=True)

		# beam pipe
		beam_pipe_temperature_PV_names = [
			"SR08TES11:TEMPERATURE_MONITOR",
			"SR08TES12:TEMPERATURE_MONITOR"
		]
		for PV_name in beam_pipe_temperature_PV_names:
			self.beam_pipe_temperature_PVs[PV_name] = epics.pv.get_pv(PV_name, connect=True)

		# slab
		self.slab_temperature_PVs["SR04TES12:TEMPERATURE_MONITOR"] = epics.pv.get_pv("SR04TES12:TEMPERATURE_MONITOR", connect=True)

		# SUBH
		for i in range(1, 5+1, 1):
			PV_name = f"TEMP-SUBH{i:02d}-IN:TEMP_MONITOR"
			self.SUBH_temperature_PVs[PV_name] = epics.pv.get_pv(PV_name, connect=True)


		# initialise temperature dicts
		self.RF601_LCW_temperatures	: dict[str, float] = {}
		self.RF602_LCW_temperatures	: dict[str, float] = {}
		self.RF701_LCW_temperatures	: dict[str, float] = {}
		self.RF702_LCW_temperatures	: dict[str, float] = {}
		
		self.RF601_body_temperatures: dict[str, float] = {}
		self.RF602_body_temperatures: dict[str, float] = {}
		self.RF701_body_temperatures: dict[str, float] = {}
		self.RF702_body_temperatures: dict[str, float] = {}

		self.magnet_temperatures	: dict[str, float] = {}
		self.tunnel_air_temperatures: dict[str, float] = {}
		self.beam_pipe_temperatures	: dict[str, float] = {}
		self.slab_temperatures		: dict[str, float] = {}
		self.SUBH_temperatures		: dict[str, float] = {}

		self.temperature_value_dicts = [
			self.RF601_LCW_temperatures,
			self.RF602_LCW_temperatures,
			self.RF701_LCW_temperatures,
			self.RF702_LCW_temperatures,
			self.RF601_body_temperatures,
			self.RF602_body_temperatures,
			self.RF701_body_temperatures,
			self.RF702_body_temperatures,
			self.magnet_temperatures,
			self.tunnel_air_temperatures,
			self.beam_pipe_temperatures,
			self.slab_temperatures,
			self.SUBH_temperatures
		]

		self.temperature_save_file_names = [
			"RF601_LCW_temperatures.json",
			"RF602_LCW_temperatures.json",
			"RF701_LCW_temperatures.json",
			"RF702_LCW_temperatures.json",
			"RF601_body_temperatures.json",
			"RF602_body_temperatures.json",
			"RF701_body_temperatures.json",
			"RF702_body_temperatures.json",
			"magnet_temperatures.json",
			"tunnel_air_temperatures.json",
			"beam_pipe_temperatures.json",
			"slab_temperatures.json",
			"SUBH_temperatures.json"
		]

		# grab PV.value(s) - no need for .get()
		# loop over all PVs and their corresponding value dictionaries
		# have to zip and nest loop due to unique keys for each cavity
		for PV_dict, value_dict in zip(self.temperature_PV_dicts, self.temperature_value_dicts):
			for key, pv in PV_dict.items():
				value_dict[key] = pv.value

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def config_save_files(self, ) -> None:

		# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
		start_time 	= datetime.datetime.now()
		date_str 	= start_time.strftime("%Y-%m-%d")
		year_str 	= start_time.strftime("%Y")
		hours_str 	= start_time.strftime("%H%Mh")
		seconds_str = start_time.strftime("%Ss")
		hostname 	= platform.node()
		try:
			hostname.index("OPI")
			self.data_path = Path(f"/asp/usr/data/resdep/{year_str}/{date_str}/{hours_str}")
		except ValueError:
			current_path = Path.cwd()
			self.data_path = current_path / "data" / "resdep" / date_str / hours_str
		try:
			Path.mkdir(self.data_path, parents=True, exist_ok=False)
		except FileExistsError: 
			# if you run the script again in the same minute, it appends seconds to the path name
			self.data_path = self.data_path / seconds_str
			Path.mkdir(self.data_path, parents=True)

		if self.data_path_callback:
			self.data_path_callback(self.data_path)

		# --- logging to console and file
		if not self.plot_callback:
			# Create a logger
			logger = logging.getLogger('my_logger')
			logger.setLevel(logging.DEBUG)
			# Create a formatter to define the log format
			formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
			# Create a file handler to write logs to a file
			file_handler = logging.FileHandler(self.data_path / "logfile.log")
			file_handler.setLevel(logging.DEBUG)
			file_handler.setFormatter(formatter)
			# Create a stream handler to print logs to the console
			console_handler = logging.StreamHandler()
			console_handler.setLevel(logging.INFO)  # You can set the desired log level for console output
			console_handler.setFormatter(formatter)
			# Add the handlers to the logger
			logger.addHandler(file_handler)
			logger.addHandler(console_handler)

		# --- init save vectors
		self.freqs						: list[float] = []
		self.set_freqs					: list[float] = []
		self.current					: list[Union[float, None]] = []
		self.timestamps_datetime		: list[datetime.datetime] = []
		self.timestamps_str				: list[str] = []
		self.slow_timestamps_datetime	: list[datetime.datetime] = []
		self.slow_timestamps_str		: list[str] = []
		self.injections					: list[datetime.datetime] = []
		self.injections_str				: list[str] = []
		self.beam_loss_window_1 		: dict[str, list[float]] = {}
		self.beam_loss_window_2 		: dict[str, list[float]] = {}
		for key in self.blm.loss:
			self.beam_loss_window_1[key] = []
			self.beam_loss_window_2[key] = []
		self.ODB_data : dict[str, list[float]] = {}
		for key in self.ODB_PVs:
			self.ODB_data[key] = []
		self.projected_end_time: datetime.datetime = start_time + datetime.timedelta(seconds=self.sweep_time)
		self.metadata: dict[str, Any] = {
			"direction"				: self.direction, 
			"duration"				: time.strftime('%H:%M:%S', time.gmtime(self.sweep_time)), 
			"fractional tune"		: self.tune,
			"f_rev"					: self.f_rev,
			"bounds (%)"			: self.bounds, 
			"frequency bounds (kHz)": self.freq_bounds, 
			"harmonic"				: self.harmonic, 
			"sweep limits (kHz)"	: self.sweep_limits, 
			"kicker amp (%)"		: self.set_kicker_amp, 
			"drive pattern"			: self.set_drive_pattern, 
			"sweep direction"		: self.sweep_direction,
			"sweep rate (Hz/s)"		: self.sweep_rate, 
			"sweep step size (Hz)"	: self.sweep_step_size, 
			"sweep span (kHz)"		: self.set_sweep_span, 
			"sweep period (us)"		: self.set_sweep_period, 
			"start time"			: start_time.strftime("%Y-%m-%d %H:%M:%S"),
			"projected end time"	: self.projected_end_time.strftime("%Y-%m-%d %H:%M:%S")
		}
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def fast_log_data(self, ) -> None:
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
			self.timestamps_datetime.append(timestamp)
			self.timestamps_str.append(timestamp_str)
			freq: Union[float, None] = self.sweep_freq_act.get()
			if freq is not None:
				self.freqs.append(freq) # kHz
			else: 
				self.freqs.append(0) 	# still append something so that the vectors are the same size
			self.set_freqs.append(self.set_sweep_freq)
			self.current.append(self.dcct.get())						# A
			
			# BLMs
			for key in self.blm.loss:
				self.beam_loss_window_1[key].append(self.blm.adc_counter_loss_1[key].get())
				self.beam_loss_window_2[key].append(self.blm.adc_counter_loss_2[key].get())

			# BPMs
			self.sr_bpms.record_data()
			self.tbpms.record_data()
			if self._measuring_MX3:
				self.mx3_bpms.record_data()

		except Exception:
			logging.error(traceback.format_exc())

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def slow_log_data(self, ) -> None:
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
			self.slow_timestamps_datetime.append(slow_timestamp)
			self.slow_timestamps_str.append(slow_timestamp_str)
			for key in self.ODB_data:
				self.ODB_data[key].append(self.ODB_PVs[key].get()) # um

		except Exception:
			logging.error(traceback.format_exc())

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def calcf_revfromMasterRF(self, ) -> None:
		"""
		Calculate a more accurate (real-time) f_rev based off current Master RF  
		
		Returns
		-------
		self.f_rev: float
			revolution frequency
		"""
		# Grab masterRF from EPICS
		# if disconnected, .get() will return none and f_rev with throw exception
		masterRF = epics.pv.get_pv('SR00MOS01:FREQUENCY_MONITOR', connect=True)
		masterRFact: Union[float, None] = masterRF.get(timeout=5)			# Hz
		if masterRFact is not None:
			self.f_rev: float = 1e-3 * masterRFact/360 	# kHz 
		return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
	def calculate_adc_counter_windows(self, sector: int = 1) -> None:
		"""
		Calculates the offsets and window lengths of the two counter windows for a specific sector \\
		**Note**: this only works for one sector, since there is no way to make the ADC windows wrap around `T0`. \\
		Thus, the 'half' of the beam that the ADC windows capture informs the bunches that should be depolarised by the BbB, \\
		and said half is unlikely to line up with the bunch numbers (*i.e.* unlikely to be bunches 1--180). 
		
		Regardless of the shape / phase of the fill pattern seen by the BLM:
		
			┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
			│ ┌───────────┐ │    │─────────┐   ┌─│    │─┐   ┌─────────│    │─────┐   ┌─────│
			│ │           │ │    │         │   │ │    │ │   │         │    │     │   │     │
			│ │           │ │ OR │         │   │ │ OR │ │   │         │ OR │     │   │     │
			│─┘           └─│    │         └───┘ │    │ └───┘         │    │     └───┘     │
			└───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘

		we can simply integrate the fill pattern from the left until we reach exactly half of the area under the curve \\
		to split the beam into two *charge equivalent* halves. ADC windows can be calculated directly from the point which \\
		divides the beam into the charge eqivalent halves.
		
		From there, we can calculate the time / phase difference between the BLM and BbB system and calculate the bunches \\
		to be depolarised. Alignment is done by finding the minima of the fill pattern seen by each system and shifting \\
		the BbB by the difference between them.

		Attributes
		----------
		[set_adc_counter_offset_1, ...] <- calculated_adc_counter_windows : list[int]
			list containing counters 1 & 2 window and offset settings for the given sector \\
			Values are a list of `[offset_1, window_1, offset_2, window_2]`

		set_drive_pattern <- depolarised_bunches : str
			list containing the start:stop range of bunches to be depolarised using the BbB \\
			This is basically a conversion from the ADC cycles (window length and pos) to bunch number
		"""
		print("Status: Time aligning BLM ADC windows and BbB system...")

		SUM_DEC 			: int 	= 86
		SUMDEC_PERIODS 		: int 	= 50
		BUCKETS_PER_CYCLE 	: float = 360/SUM_DEC
		replicated_fill_pattern: npt.NDArray[np.floating]

		# --- BbB waveforms --- #
		SRAM_x_waveform_PV = epics.pv.get_pv("IGPF:X:SRAM:MEAN")
		SRAM_y_waveform_PV = epics.pv.get_pv("IGPF:Y:SRAM:MEAN")

		SRAM_x_waveform: Union[npt.NDArray[np.floating], None] = SRAM_x_waveform_PV.get()
		SRAM_y_waveform: Union[npt.NDArray[np.floating], None] = SRAM_y_waveform_PV.get()

		# --- BLM ---
		# set sumdec periods
		current_number_of_sumdec_periods: Union[float, None] = self.blm.init_sumdec_periods[f"{sector}"]
		if current_number_of_sumdec_periods is None:
			warnings.warn(f"sumdec_periods for sector={sector} returned None")
			return None
		if current_number_of_sumdec_periods < 20:
			self.blm.sumdec_periods[f"{sector}"].put(SUMDEC_PERIODS)
			if self.status_callback:
				self.status_callback("Status: Waiting for injection to update integrated buffer...")
			while not self._injecting:
				self.interruptible_sleep(1)
			if self.status_callback:
				self.status_callback("Status: Time aligning BLM ADC windows and BbB system...")


		replicated_fill_pattern = self.blm.integrated_buffer_loss[f"{sector}B"].get() 
		time.sleep(0.5)
		# integrated buffer is updside down, need to normalise 
		replicated_fill_pattern = replicated_fill_pattern/np.max(replicated_fill_pattern)
		# and flip
		replicated_fill_pattern = -1 * replicated_fill_pattern + 1
		# shift by T2 delay
		T2_delay = self.blm.init_t2_trigger_delays[f"{sector}"]
		if T2_delay is not None:
			T2_delay = int(T2_delay) % SUM_DEC
		else:
			warnings.warn(f"T2 delay for BLM in sector {sector} returned None")
		replicated_fill_pattern = np.concatenate((replicated_fill_pattern[T2_delay:], replicated_fill_pattern[:T2_delay]))

		# separate the fill pattern into two charge equivalent halves
		integrated_fill_pattern = np.sum(replicated_fill_pattern)
		cumsum_fill_pattern 	= np.cumsum(replicated_fill_pattern)
		dividing_line 			= int(np.flatnonzero(cumsum_fill_pattern < integrated_fill_pattern/2)[-1]) + 1
		# format: [offset_1, window_1, offset_2, window_2]
		calculated_adc_counter_windows: list[int] = [0, dividing_line, dividing_line, (SUM_DEC - dividing_line)]
		bucket_offset_1, bucket_window_1, bucket_offset_2, bucket_window_2 = [BUCKETS_PER_CYCLE*adc_cycle for adc_cycle in calculated_adc_counter_windows]

		# Middle empty buckets
		try:
			blm_middle_empty_bucket 	= self.find_middle_of_empty_buckets(fill_pattern=replicated_fill_pattern)
			if SRAM_x_waveform is not None and SRAM_y_waveform is not None:
				SRAM_x_middle_empty_bucket  = self.find_middle_of_empty_buckets(fill_pattern=SRAM_x_waveform)
				SRAM_y_middle_empty_bucket  = self.find_middle_of_empty_buckets(fill_pattern=SRAM_y_waveform)
				SRAM_middle_empty_bucket    = (SRAM_x_middle_empty_bucket + SRAM_y_middle_empty_bucket) // 2
			else:
				raise TypeError("SRAM x and/or y waveforms returned None")
		except ValueError: # if args_under_threshold is empty
			warnings.warn("Error finding the empty buckets in the fill pattern")
			return None

		print(f"BbB SRAM middle empty bucket={SRAM_middle_empty_bucket}")
		print(f"BLM middle empty bucket={blm_middle_empty_bucket}")
		# Shift the calculated depolarised bunches by the time offset between the BLM and BbB system (given by the difference in the min bucket)
		bucket_offset_1 = int(bucket_offset_1 + SRAM_middle_empty_bucket - blm_middle_empty_bucket)
		bucket_offset_2 = int(bucket_offset_2 + SRAM_middle_empty_bucket - blm_middle_empty_bucket)
		# After aligning the empty buckets, are the starts of the windows within 1:360?
		# If not, loop in circular buffer.
		if (bucket_offset_1 < 1) or (bucket_offset_1 > 360):
			bucket_offset_1 = (bucket_offset_1 - 1) % 360 + 1
		if (bucket_offset_2 < 1) or (bucket_offset_2 > 360):
			bucket_offset_2 = (bucket_offset_2 - 1) % 360 + 1

		# The start of one window is the end of the other.
		depolarised_bunch_start 	= bucket_offset_1 
		depolarised_bunch_end 		= bucket_offset_2-1
		depolarised_bunches: str 	= f"{depolarised_bunch_start}:{depolarised_bunch_end}"
		
		# update experiment settings
		self.set_drive_pattern = depolarised_bunches
		(self.set_adc_counter_offset_1,
			self.set_adc_counter_window_1,
			self.set_adc_counter_offset_2,
			self.set_adc_counter_window_2) = calculated_adc_counter_windows
		
		# update GUI
		if self.ADC_windows_callback:
			self.ADC_windows_callback(calculated_adc_counter_windows, depolarised_bunches)

		print("Calculated adc_counter windows, format: [offset_1, window_1, offset_2, window_2]")
		print(calculated_adc_counter_windows)
		print("Corresponding depolarised bunches for BbB:")
		print(depolarised_bunches)
		
		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def find_middle_of_empty_buckets(self, fill_pattern: npt.NDArray[np.floating]) -> int:
		"""
		Calculates the middle of the empty buckets in the fill pattern \\
		Used to align different fill pattern sources (BbB, BLMs) in time.

		Parameters
		----------
		fill_pattern: npt.NDArray[np.floating]
			Fill pattern / bunch train of the electron beam

		Returns
		-------
		middle_of_empty_buckets: int
			The argument of the middle of the empty buckets with respect to the input shape of `fill_pattern`
		"""

		boundary: int = len(fill_pattern)
		threshold = 0.6 * np.max(fill_pattern)
		args_under_threshold = np.flatnonzero(fill_pattern < threshold)
		# Account for empty buckets wraping around T0
		if any(args_under_threshold < 5) and any(args_under_threshold > boundary - 5):
			difference_in_args = args_under_threshold[1:] - args_under_threshold[:-1]
			jump_in_args = np.argmax(difference_in_args)
			# undo wrap around T0
			args_under_threshold[:jump_in_args+1] += boundary
		
		middle_empty_bucket_arg = int(np.mean(args_under_threshold)) % boundary

		return middle_empty_bucket_arg
    
	# *--------------------------------* #
	# *-------- Post-processing -------* #
	# *--------------------------------* #
	# --------------------------------------------------------------------------------------------------------------------
	def save_data(self, ) -> None:
		"""
		Saves PV data to text, json and csv files depending on structure \\
		Also append entime to metadata and saves to json. \\
		Save path is Data/{YYYY-mm-dd}/{HHHHh}/ \\
		*e.g.* Data/2025-10-20/0900h/
		"""

		try:
			print("Saving data...")

			# metadata
			del self.metadata['projected end time']
			end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			self.metadata.update({'end time': end_time, 'Last sweep frequency': self.set_sweep_freq})
			with open(self.data_path / 'metadata.json', 'w') as f:
				json.dump(self.metadata, f)
			
			# freqs as txt
			with open(self.data_path / 'freqs.txt', 'w') as f:
					for value in self.freqs:
						f.write(str(value) + '\n')
			with open(self.data_path / 'set_freqs.txt', 'w') as f:
					for value in self.set_freqs:
						f.write(str(value) + '\n')
			
			# current as txt
			with open(self.data_path / 'current.txt', 'w') as f:
					for value in self.current:
						f.write(str(value) + '\n')

			# timestamps as txt
			with open(self.data_path / 'timestamps.txt', 'w') as f:
					for value in self.timestamps_str:
						f.write(value + '\n')
			# slow timestamps as txt
			with open(self.data_path / 'slow_timestamps.txt', 'w') as f:
					for value in self.slow_timestamps_str:
						f.write(value + '\n')

			# adc counter loss 1
			with open(self.data_path / 'adc_counter_loss_1.json', 'w') as f:
				json.dump(self.beam_loss_window_1, f)
			# adc counter loss 2
			with open(self.data_path / 'adc_counter_loss_2.json', 'w') as f:
				json.dump(self.beam_loss_window_2, f)

			# ODB size and offset
			with open(self.data_path / 'ODB_data.json', "w") as f:
				json.dump(self.ODB_data, f)

			# injection timestamps as txt
			with open(self.data_path / 'injections.txt', 'w') as f:
					for value in self.injections_str:
						f.write(value + '\n')
						
			# temperatures (will need a separate folder)
			temperatures_path = self.data_path / "temperatures"
			Path.mkdir(temperatures_path)
			# each dict as its own .json
			for temperature_dict, save_file_name in zip(self.temperature_value_dicts, self.temperature_save_file_names):
				with open(temperatures_path / save_file_name, "w") as f:
					json.dump(temperature_dict, f)

			# --- BPMs
			# SR 
			sr_bpms_path = self.data_path / "BPMs" / "SR"
			Path.mkdir(sr_bpms_path, parents=True)
			self.sr_bpms.save_data(path=sr_bpms_path)

			# TBPMs
			tbpms_path = self.data_path / "BPMs" / "TBPMs"
			Path.mkdir(tbpms_path, parents=True)
			self.tbpms.save_data(path=tbpms_path)

			# MX3 
			if self._measuring_MX3:
				mx3_bpms_path = self.data_path / "BPMs" / "MX3"
				Path.mkdir(mx3_bpms_path, parents=True)
				self.mx3_bpms.save_data(path=mx3_bpms_path)


		except Exception:
			logging.error(traceback.format_exc())

		print("\n Data saved!")

		return None
	# ----------------------------------------------------------------------------------------------------------------------------------------------------	
	def plot_data(self, ) -> None:
		"""
		Plots loss ratio between polarised and depolarised bunches. \\
		Fits error function to sectors with compatible timing with BbB / FPM. \\
		Also plots ODB beam size and offset to check for any major disturbances.
		"""

		try:
			print("Attempting to plot ratio data...")
		
			sectors_to_fit: list[str] = ["1", "4", "8", "11", "12", "13"]
			processed_data = ProcessedData(resdep=self, sectors_to_fit=sectors_to_fit)
			processed_data.calculate_ratio_loss(sigma=5)
			
			graph = Graph()
			plotting = PlottingClass(resdep=self, processed_data=processed_data, graph=graph)
			plotting.plot_ratio_loss()
			plt.savefig(self.data_path / "ratio_loss.png", dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
			plt.show()

		except Exception:
			logging.error(traceback.format_exc())

		return None
	
	# *--------------------------------* #
	# *---------- PV callbacks --------* #
	# *--------------------------------* #
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def onValueChange(self, pvname=None, value=None, host=None, **kws):
		# * Cannot do .put() or .get() inside callback
		# It looks like .get() works but really I think it's simply getting PV.value which is cached.

		try:
			if value == 2:
				# record timestamp
				inj_time = datetime.datetime.now()
				inj_time_str = inj_time.strftime("%Y-%m-%d %H:%M:%S")
				self.injections.append(inj_time)
				self.injections_str.append(inj_time_str)

				# toggle state
				self._injecting = True

		except Exception:
			logging.error(traceback.format_exc())

	# *--------------------------------* #
	# *---------- GUI Signals ---------* #
	# *--------------------------------* #
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def request_abort(self, ) -> None:
		"""
		Changes the abort state to True, which will interrupt the experiment loop on the next iteration
		"""
		self._abort_requested = True
		return None
	# *--------------------------------* #
	# *----------- Utilities ----------* #
	# *--------------------------------* #
	# ----------------------------------------------------------------------------------------------------------------------------------------------------
	def interruptible_sleep(self, seconds: int) -> None:
		"""
		Sleeps over long periods of time, waking often to check states (abort for example)
		"""
		end = time.time() + seconds
		while time.time() < end:
			if self._abort_requested:
				return None
			# sleep quickly
			time.sleep(0.01)
		
		return None
	

# *--------------------------------* #
# *-------- Processed Data --------* #
# *--------------------------------* #
@dataclass
class ProcessedData():
	"""
	Class for storing processed/analysed/formatted data generated by resdep and associated _fitting and _plotting helper classes
	"""
	resdep 			: "ResonantDepolarisation"
	sectors_to_fit	: list[str]
	# defaults (if data is not passed on initialisation/instancing)
	freqs_array	: npt.NDArray[np.floating] 							= field(default=np.array([]))
	ratio_loss	: dict[str, npt.NDArray[np.floating]] 				= field(default_factory=dict)
	# plotting
	mask		: Union[npt.NDArray[np.bool_], "builtins.ellipsis"] 	= field(default=...) 
	# fitting
	y_model                       : dict[str, npt.NDArray[np.float64]] = field(default_factory=dict)
	fitted_beam_energy_frequencies: dict[str, float]                   = field(default_factory=dict)
	fitted_beam_energies          : dict[str, float]                   = field(default_factory=dict)
	fitted_beam_energy_stddevs    : dict[str, float]                   = field(default_factory=dict)
	fit_results                   : str                                = field(default="")
	# stats
	E0_mean         : Union[float, None] = field(default=None)
	E0_stddev       : Union[float, None] = field(default=None)
	E0_mean_sigfig  : Union[float, None] = field(default=None)
	E0_stddev_sigfig: Union[float, None] = field(default=None)

	# ------------------------------------------------------------------------------------------------------
	def calculate_ratio_loss(self, sigma: int) -> None:

		self.freqs_array = np.array(self.resdep.freqs)/1e3 # kHz

		for sector in self.sectors_to_fit:
			# add offset so no ratio is divide by zero 
			self.resdep.beam_loss_window_1[f"{sector}B"] = [value + 1 for value in self.resdep.beam_loss_window_1[f"{sector}B"]]
			self.resdep.beam_loss_window_2[f"{sector}B"] = [value + 1 for value in self.resdep.beam_loss_window_2[f"{sector}B"]]
			self.ratio_loss[f"{sector}B"] = np.array(self.resdep.beam_loss_window_1[f"{sector}B"])/np.array(self.resdep.beam_loss_window_2[f"{sector}B"])

		for sector in self.sectors_to_fit:
			# filter / bin
			self.ratio_loss[f"{sector}B"] = gaussian_filter1d(self.ratio_loss[f"{sector}B"], sigma)
			# set zero
			self.ratio_loss[f"{sector}B"] += np.min(self.ratio_loss[f"{sector}B"])
			# normalise
			self.ratio_loss[f"{sector}B"] *= 1/np.max(self.ratio_loss[f"{sector}B"])

		return None



if __name__ == "__main__":
	print("resdep.py contains a class file ResonantDepolarisation which ideally should be instanced in a top-level script and not directly run.")
	response = input("Do you want to run it directly? (y/n): ")

	if response == "y":
		resdep = ResonantDepolarisation()
		response = input("Use default settings? (y/n): ")

		if response == "y":
			print("#--- input experiment settings ---#")
			resdep.set_kicker_amp		= float(input("Kicker amplitude (% as decimal, 0->1): \n"))
			resdep.harmonic				= int(	input("Harmonic (int): \n"))
			resdep.bounds				= float(input("Energy Bounds (% as decimal, typically 0.0005): \n"))
			resdep.sweep_direction		= int(	input("Sweep direction (Forward == 1, backward == -1): \n"))
			resdep.sweep_rate			= float(input("Sweep rate (0.5 -- 10 Hz/s): \n"))
			resdep.sweep_step_size		= float(input("Sweep step size (lower limit = 0.5 Hz): \n"))

		resdep.start_experiment()
