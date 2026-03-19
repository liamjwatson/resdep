"""
Detect the alignment of the fill pattern (as seen by the BbB) to the ADC clock of the Libera BLMs
This is done with a regular fill pattern and the smallest possible SUM_ADC window, which is swept
over all possible ADC delays (offsets).
Then, the minimum in the beam losses (vs. ADC offset) should correspond to the empty bunches.
*i.e* this script should replicate the fill pattern as loss vs ADC offset.

Workflow
--------
- Import relevant PVs (BLMs)
- Config ADC mask (of sector 11) to smallest (I think its 4?)
- collect beam loss for every offset (86/4 = 21.5? points) for idk 1-5s dwell time.
- ADC_offset stored as list[int], blm.loss stored in usual way dict[str(sector): list[float](loss)]
- plot loss vs offset
- automatically calculate np.where(np.min(loss)) and spit out something sensible to inform adc_counter_window and offset for resdep
* Notes on adc_counter_window:
* - unless the empty buckets are at the edges or in the middle, a nice 50/50 adc_counter_window split doesn't work
* - if one half of the windows is underfilled (contains the empty buckets):
* - you need to increase this window by 30 bunches (= 7 ADC cycles) and subsequently reduce the other (full) window by the same amount
* - goes from 180/120 bunch split (60 missing bunches in second window for e.g.) to 150/150 split (for 300 full buckets)
"""

import sys
import os
import warnings
import epics
import datetime
import time
from typing import Any, Literal, Union
import traceback, logging
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import json
from scipy.ndimage import gaussian_filter1d

from resdep.epicsBLMs import BLMs # Libera BLM python class, stores states, dicts, functions
# from progressBars import printProgressBar


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#

# --- constants
log_frequency = 10 # Hz
dwell_time = 5 # s
data_points_per_bin = log_frequency * dwell_time 
# Hard-coding this for first run debugging
# This can be changed later to blm.init_t0_interval_expected['11']
SUM_DEC = 86
buckets_per_cycle = 360/SUM_DEC
cycles_per_bucket = 1/buckets_per_cycle
# format: [offset_1, window_1, offset_2, window_2]
calculated_adc_counter_windows: list[int] = []
# format start:end, e.g. "0:150"
depolarised_bunches: str = "" 
depolarised_bunch_start: int
depolarised_bunch_end: int
# initialise adc cycle at loss min > SUM_DEC for error checking
adc_cycle_at_loss_min: int
bucket_at_loss_min: int
FPM_Y_minimum_bucket: int
# linspace for buckets
buckets = np.arange(start=1, stop=360+1, step=1)

# define inits
set_adc_offset: int = 0
set_adc_window: int = 5
window_centre = (set_adc_window-1)//2
# select counting mode; 0: differential, 1: normal (thresholding)
set_counting_mode: int = 0

projected_end_time = (SUM_DEC - set_adc_window) * dwell_time
print("Projected experiment duration: {0:1.1f} minutes.".format(projected_end_time/60))
response = input("Do you want to continue? y/n?\n")
if not response == "y":
    print("Exiting...")
    sys.exit()


print("Initialising PVs...")

# --- assign PVs : BLMs 
blm = BLMs()
blm.get_loss_PVs()
# blm.get_sumdec_adc_mask_PVs()
# blm.get_init_sumdec_adc_masks()
blm.get_adc_counter_mask_PVs()
blm.get_init_adc_counter_masks()
time.sleep(2)
blm.get_decimation()
time.sleep(2)


# --- assign PVs: current
dcct = epics.pv.get_pv('SR11BCM01:CURRENT_MONITOR', connect=True)
# --- assign PVs: IGPF:Y FPM and bucket shift
# this is in Acc. Sub systems -> Optical Diag B/L -> ODB FPM
FPM_Y_PV = epics.pv.get_pv("SR00BBB01FPM02:FILL_PATTERN_ABS_WAVEFORM_MONITOR", connect=True)
bucket_shift_Y_PV = epics.pv.get_pv("SR00BBB01FPM02:BUCKET_SHIFT_SP", connect=True)
bucket_shift_Y : Union[int, None] = bucket_shift_Y_PV.get() # int
FPM_Y_offset_array: Union[npt.NDArray[np.float64], None] = FPM_Y_PV.get() # NDArray[np.float64]
time.sleep(0.5)
if FPM_Y_offset_array is not None:
    FPM_Y_offset: list[float] = FPM_Y_offset_array.tolist()
else:
    FPM_Y_offset = []
    warnings.warn("Fill pattern monitor PV returned None. Depolarised bunch calculations won't run.")
FPM_Y_original:  list[float] = []


print("PVs grabbed!")

# --- init save path (format: Data\YYYY-mm-dd\HHMM+'h'\) e.g. 'Data\2025-09-25\0900h\'
start_datetime 	= datetime.datetime.now()
date_str 	= start_datetime.strftime("%Y-%m-%d")
hours_str 	= start_datetime.strftime("%H%Mh")
seconds_str = start_datetime.strftime("%Ss")
try:
    os.makedirs(os.path.join("fill_pattern_alignment", "Data", date_str, hours_str), mode=0o777, exist_ok=False)
    data_path = os.path.join("fill_pattern_alignment", "Data", date_str, hours_str)
except OSError: 
    # if you run the script again in the same minute, it appends seconds to the path name
    os.makedirs(os.path.join("fill_pattern_alignment", "Data", date_str, hours_str, seconds_str), mode=0o777)
    data_path = os.path.join("fill_pattern_alignment", "Data", date_str, hours_str, seconds_str)
	
# --- init save vectors
ADC_offset  : list[int] = []
beam_losses : dict[str, list[float]] = {}
# create an dictionary that has keys (sector, section), and an np.array with average beam loss per ADC cycle
replicated_fill_pattern : dict[str, npt.NDArray[np.float64]] = {}
for key in blm.adc_counter_loss_1:
    beam_losses[key] = []
    replicated_fill_pattern[key] = np.zeros([SUM_DEC-set_adc_window+1, 2])

# get nominal current
current = dcct.get()
time.sleep(0.5)

metadata: dict[str, Any] = {
    "log frequency": log_frequency,
    "dwell time": dwell_time,
    "data points per bin": data_points_per_bin,
    "initial adc offset": set_adc_offset,
    "initial adc window": set_adc_window,
    "bucket shift IGPF:Y": bucket_shift_Y,
    "current": current,
    "start time": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
}
	
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def main() -> None:
    """
    Sweeps over ADC offset for minimum ADC window. \\
	Stores ADC_offset vector and blm.loss for every sector. \\
    Bins (usually) 5 s of data, stores average beam loss per ADC cycle
    in replicated_fill_pattern dict with {sector,section} keys
    """

    # global variable assignment since i'm unable to pass variables in a PV callback
    global set_adc_offset, set_adc_window

    # --- assign PVs: injection trigger
    injection_trigger = epics.pv.get_pv("TS01EVG01:INJECTION_MODE_STATUS", connect=True, callback=(onValueChange))

    time.sleep(1)

    # --- update decimation
    blm.apply_full_decimation()
    time.sleep(1)

    print("Applying ADC masks...")

    # apply inits
    for key in blm.adc_counter_offset_1:
        # reduce window first to reduce chance of errors
        blm.adc_counter_window_1[key].put(set_adc_window, use_complete=True)
        blm.adc_counter_offset_1[key].put(set_adc_offset, use_complete=True)
        blm.counting_mode[key].put(set_counting_mode, use_complete=True)
    # wait for all puts to complete
    for key in blm.sumdec_adc_mask_offset:
        while not all(
            [blm.adc_counter_window_1[key].put_complete,
             blm.adc_counter_offset_1[key].put_complete,
             blm.counting_mode[key].put_complete]
        ):
            time.sleep(0.01)

    time.sleep(1)

    loop_counter = 0

    last_data_call = time.time()

    try: 
        print("|--------------------------------------------|")
        print("|----------- BEGINNING EXPERIMENT -----------|")
        print("|--------------------------------------------|")
        print("Stepping over ADC cycles and recording data...")

        # loop while (offset + window) < SUM_DEC
        while (set_adc_offset + set_adc_window) <= SUM_DEC:

            if time.time() >= last_data_call + 1/log_frequency:

                # advance loop counter
                loop_counter +=1

                # record data (at log_frequency, usually 10 Hz)
                for key in blm.loss:
                    beam_losses[key].append(blm.adc_counter_loss_1[key].get())

                # after 1--5 seconds, advance offset
                if loop_counter == data_points_per_bin: 

                    # advance window offset
                    set_adc_offset += 1
                    # ensure while loop breaks first ahead of applying 
                    # offset larger than SUM_DEC
                    if (set_adc_offset + set_adc_window) > SUM_DEC:
                        break
                    # apply new offset
                    for key in blm.adc_counter_offset_1:
                        blm.adc_counter_offset_1[key].put(set_adc_offset, use_complete=True)
                    # wait for all puts to complete
                    for key in blm.adc_counter_offset_1:
                        while not blm.adc_counter_offset_1[key].put_complete:
                            time.sleep(0.01)

                    # # update progress bar
                    # printProgressBar(iteration=set_adc_offset+1, total=SUM_DEC)
                    
                    # update console every 10 offsets
                    if set_adc_offset % 10 == 0:
                        print(f"ADC offset = {set_adc_offset}...")

                    # reset loop counter
                    loop_counter = 0

                last_data_call = time.time()
                
            time.sleep(0.01)

    finally:
        print("|--------------------------------------------|")
        print("|------------- SWEEP FINISHED ! -------------|")
        print("|--------------------------------------------|")

        end_datetime: datetime.datetime = datetime.datetime.now()
        # exp_duration: datetime.timedelta = end_datetime - start_datetime
        metadata["end time"] = end_datetime.strftime("%Y-%m-%d %H:%M:%S"),

        blm.restore_inits(mode="adc_counter_masks")
        blm.restore_inits(mode="decimation")

        bin_data()
        
        calculate_adc_counter_windows(sector="8", method="loss_minimum")
        calculate_adc_counter_windows(sector="8", method="integrated_half")

        save_data()

        # Remove callback to trigger
        try: 
            injection_trigger.remove_callback(0)
        except Exception:
            logging.error(traceback.format_exc())

        plot_data(sectors="all")

        print("Experiment done!")
       
    return None

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def bin_data() -> None:

    try:

        bins = len(beam_losses["11B"])//data_points_per_bin

        print(f"data_points_per_bin={data_points_per_bin}")
        print(f"bins={bins}")

        for i in range(0, bins, 1):
            for key in beam_losses:
                binned_data = np.mean(beam_losses[key][i*data_points_per_bin:(i+1)*data_points_per_bin])
                replicated_fill_pattern[key][i] = [i, binned_data]

    except Exception:
        logging.error(traceback.format_exc())

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def calculate_adc_counter_windows(sector: str, method: Literal["loss_minimum", "integrated_half"] = "loss_minimum") -> None:
    """
    Calculates the offsets and window lengths of the two counter windows for a specific sector \\
    **Note**: this only works for one sector, since there is no way to make the ADC windows wrap around T0. \\
    Thus, the 'half' of the beam that the ADC windows capture informs the bunches that should be depolarised by the BbB, \\
    and said half is unlikely to line up with the bunch numbers (*i.e.* unlikely to be bunches 1--180). \\
    For now, uses the straight as the reference, but could in the future average the windows between the straight and the bend.
    \\
    \\
    Due to the restrictions of the windows to T0 and the phase shifting of the fill pattern as a function of sector, the calculations \\
    of charge equavlent windows are a little tricky to think about. There are basically two different conditions:
    1. The fill pattern is centred:
    
        ||   _____________   ||
        ||  |             |  ||
        ||__|             |__||
    
    in which case, the windows should just be from each edge to the centre (simple). \\
    OR,
    
    2. The fill pattern is not centred:

        ||__________      __||      ||__      __________||       ||_______      _______||
        ||          |    |  ||  OR  ||  |    |          ||   OR  ||       |    |       ||
        ||          |____|  ||      ||  |____|          ||       ||       |____|       ||

    in which case, the length of the windows depends on which side the empty buckets lie.

    To calculate if the pattern is in the centre, we can determine the edges of the fill pattern from the loss minumum. \\
    We will call these the start and end, to not confuse left and right when considering the phase shift of the fill pattern.
    
    The pattern is in the centre if, in reference to the mid point of the empty buckets, either the start or end of the fill pattern \\
    exceeds the bounds of SUM_DEC. You can think of this as the reciprocal lattice tranlation vector G for Brillouin zones. \\
    So we can match this case against where the start and end are calculated as within the bounds of SUM_DEC (not centred) 

    We require exactly 150 *filled* buckets on each side (in each window). For the centred case (1), we simply move the diving line \\
    with the midpoint of the fill pattern so that is split 150:150 every time, no matter the distribution of the empty buckets. \\
    Note that the centre of the fill pattern is just the pi/2 phase shift of the minimum.

    For the non-centred case (2), there are two sub-cases. The first, where the empty buckets are fully enclosed in one of the windows, \\
    and the *special* case, where the empty buckets are centred and exactly split the fill pattern 150:150. In the special case, the diving line \\
    can be anywhere in the centre unfilled 60. When it's not in the centre, there will be less than 150 filled buckets on one side, \\
    and so the line will be locked at 180 +- 30 to keep the split even. These two non-centred cases can be combined since the line can be anywhere \\
    in the empty buckets for the special case, which includes 180 +- 30.

    Updates (global scope)
    -------
    calculated_adc_counter_windows : list[int]
        list containing counters 1 & 2 window and offset settings for the given sector \\
        Values are a list of [offset_1, window_1, offset_2, window_2]
    
    depolarised_bunches : list[int]
        list containing the start:stop range of bunches to be depolarised using the BbB
        This is basically a conversion from the ADC cycles (window length and pos) to bunch number
    """

    # global calculated_adc_counter_windows, depolarised_bunches, adc_cycle_at_loss_min, bucket_at_loss_min, FPM_Y_minimum_bucket, depolarised_bunch_start, depolarised_bunch_end, FPM_Y_original
    global calculated_adc_counter_windows

    

    try:
          
        # calculate original fill pattern by undoing offset
        if FPM_Y_offset is not None:
                FPM_Y_original = FPM_Y_offset
        if bucket_shift_Y is not None:
            for i in range(bucket_shift_Y):
                FPM_Y_original.insert(0, FPM_Y_original.pop(-1))
        
        dividing_line = 0
        
        loss_minimum                    = np.min(replicated_fill_pattern[f"{sector}B"][:,1])
        adc_cycle_at_loss_min_index 	= np.where(replicated_fill_pattern[f"{sector}B"][:,1] == loss_minimum)[0].tolist()[0]
        adc_cycle_at_loss_min 		 	= int(replicated_fill_pattern[f"{sector}B"][adc_cycle_at_loss_min_index,0])
        bucket_at_loss_min  			= int(adc_cycle_at_loss_min*buckets_per_cycle)

        print(f"ADC cycle at loss minimum = {adc_cycle_at_loss_min}")
        print(f"bucket at loss minimum = {bucket_at_loss_min}")
        
        if method == "loss_minimum":
            print("# --- Mode: loss minimum --- #")
            # case (0): minimum (offset) is not captured due to finite window size
            if (adc_cycle_at_loss_min  == window_centre) or (adc_cycle_at_loss_min == (SUM_DEC - window_centre - 1)):
                # Here, the loss minimum is not captured, but I don't know if I can really do anything about it
                # I think the best course of action would be to assume that the fill pattern is perfectly centred
                # That way, the determination is at best window_centre/2 cycles out, not otherwise at max window_centre cycles.
                dividing_line = SUM_DEC//2

            # case (1): centred fill pattern
            elif (adc_cycle_at_loss_min <= 30*cycles_per_bucket) or (adc_cycle_at_loss_min >= 330*cycles_per_bucket):
                # dividing line is the centre of the fill pattern = loss min phase flipped pi/2
                dividing_line: int = int(np.abs(adc_cycle_at_loss_min - 180*cycles_per_bucket))
            
            # case (2): Empty buckets are on the left: 
            elif (adc_cycle_at_loss_min <= 150*cycles_per_bucket):
                # see notes above
                dividing_line: int = int(210*cycles_per_bucket)

            # case (3): Empty buckets are on the right:
            elif (adc_cycle_at_loss_min > 150*cycles_per_bucket):
                # see notes above
                dividing_line: int = int(150*cycles_per_bucket)
            
        elif method == "integrated_half":
            print("# --- Mode: integrated half --- #")
            # integrate loss
            integrated_loss = np.sum(replicated_fill_pattern[f"{sector}B"][:,1])
            cumulative_loss = np.cumsum(replicated_fill_pattern[f"{sector}B"][:,1])
            
            # weighted left half
            dividing_line = np.where(cumulative_loss < integrated_loss//2)[0].tolist()[-1]
        
        else:
            ValueError("Incorred mode.")

        # --- calculations 
        # format: [offset_1, window_1, offset_2, window_2]
        calculated_adc_counter_windows = [0, dividing_line, dividing_line, (SUM_DEC - dividing_line)]
        bucket_offset_1, bucket_window_1, bucket_offset_2, bucket_window_2 = [int(buckets_per_cycle*adc_cycle) for adc_cycle in calculated_adc_counter_windows]

        # FPM_Y minimum
        FPM_Y_minimum_bucket = int(buckets[np.where(FPM_Y_original == np.min(FPM_Y_original))[0].tolist()[0]])
        print(f"FPM_Y min bucket = {FPM_Y_minimum_bucket}")

        bucket_offset_1 += int(FPM_Y_minimum_bucket - bucket_at_loss_min)
        bucket_offset_2 += int(FPM_Y_minimum_bucket - bucket_at_loss_min)
        # After aligning the empty buckets, are the starts of the windows within 1:360?
        # If not, loop in circular buffer.
        if (bucket_offset_1 < 1) or (bucket_offset_1 > 360):
            bucket_offset_1 = (bucket_offset_1 - 1) % 360 + 1
        if (bucket_offset_2 < 1) or (bucket_offset_2 > 360):
            bucket_offset_2 = (bucket_offset_2 - 1) % 360 + 1

        # The start of one window is the end of the other.
        depolarised_bunch_start = bucket_offset_1
        depolarised_bunch_end 	= bucket_offset_2-1
        depolarised_bunches = f"{depolarised_bunch_start}:{depolarised_bunch_end}"

        print("Calculated adc_counter windows, format: [offset_1, window_1, offset_2, window_2]")
        print(calculated_adc_counter_windows)
        print("Corresponding depolarised bunches for BbB:")
        print(depolarised_bunches)

    except Exception:
        logging.error(traceback.format_exc())

    return None


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def save_data() -> None:

    try:

        print("Saving data...")
        
        # --- metadata
        with open(os.path.join(data_path, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        # --- replicated fill pattern
        # NOTE: np.ndarray is not JSON serialisable. 
        # Have to convert to a list of lists.
        # To restore, use: codecs.open(file_path, 'r', encoding='utf-8').read()
        
        # first convert to list of list and store in temp dict
        replicated_fill_pattern_JSON : dict[str, list[list[float]]] = {}
        for key in replicated_fill_pattern:
            replicated_fill_pattern_JSON[key] = replicated_fill_pattern[key].tolist()
        # then save (hopefully...)
        with open(os.path.join(data_path, "replicated_fill_pattern.json"), "w") as f:
            json.dump(replicated_fill_pattern_JSON, f)

        # --- raw beamloss without binning?
        # beam losses, as .json:
        with open(os.path.join(data_path, "beam_losses.json"), "w") as f:
            json.dump(beam_losses, f)

        # --- FPM_Y
        if FPM_Y_offset is not None:
            with open(os.path.join(data_path, "FPM_Y.txt"), "w") as f:
                for value in FPM_Y_offset:
                    f.write(str(value) + '\n')

        print("Data saved!")

    except Exception:
		# Logs the error appropriately. 
        logging.error(traceback.format_exc())

    return None

# -------------------------------------------------------------------------------------------------------------------------------
# Plot data
def plot_data(sectors: Literal["all", "11"]) -> None:

	# original non-reversed settings are correct in refernce to the 
	# direction in which the buckets are shifted with the bucket_shift_Y
	# positive number means the fill pattern moves left with respect to the
	# revolution window.

	global FPM_Y_offset

	try: 
		# depolarised bunches
		offset_1, window_1, offset_2, window_2 = calculated_adc_counter_windows

		# plot FPM
		fig, axs = plt.subplots(1,2, figsize=(6,3), constrained_layout=True)
		axs[0].plot(buckets, FPM_Y_offset, marker='o')
		axs[0].set_xlim([1,360])
		axs[0].set_xticks([1, 60, 120, 180, 240, 300, 360])
		axs[0].set_title("FPM_Y offset")
		axs[0].set_xlabel("Bunch number")

		axs[1].plot(buckets, FPM_Y_original, marker='o')
		axs[1].set_xlim([1,360])
		axs[1].set_xticks([1, 60, 120, 180, 240, 300, 360])
		axs[1].set_title("FPM_Y original")
		axs[1].set_xlabel("Bunch number")

		# fill between
		if (depolarised_bunch_start < depolarised_bunch_end):
			# 1 to start
			axs[1].fill_between(
				x=buckets[0:depolarised_bunch_start], 
				y1=FPM_Y_original[0:depolarised_bunch_start], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="blue")
			# start to end
			axs[1].fill_between(
				x=buckets[depolarised_bunch_start:depolarised_bunch_end], 
				y1=FPM_Y_original[depolarised_bunch_start:depolarised_bunch_end], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="red")
			# end to 360
			axs[1].fill_between(
				x=buckets[depolarised_bunch_end:359], 
				y1=FPM_Y_original[depolarised_bunch_end:359], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="blue")
		elif (depolarised_bunch_start > depolarised_bunch_end):
			# 1 to end
			axs[1].fill_between(
				x=buckets[0:depolarised_bunch_end], 
				y1=FPM_Y_original[0:depolarised_bunch_end], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="blue")
			# end to start
			axs[1].fill_between(
				x=buckets[depolarised_bunch_end:depolarised_bunch_start], 
				y1=FPM_Y_original[depolarised_bunch_end:depolarised_bunch_start], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="red")
			# start to 360
			axs[1].fill_between(
				x=buckets[depolarised_bunch_start:359], 
				y1=FPM_Y_original[depolarised_bunch_start:359], 
				y2=np.min(FPM_Y_original), 
				alpha=0.2, 
				color="blue")

		
		if sectors == "11":

			print("Plotting data...")

			straight 	= np.array(replicated_fill_pattern["11A"])
			bend 		= np.array(replicated_fill_pattern["11B"])

			# Straight on top, bend on bottom
			fig, axs = plt.subplots(2,2, figsize=(6,6), constrained_layout=True)

			# plot raw data
			sigma = 0.1
			axs[0,0].plot(gaussian_filter1d(beam_losses["11A"], sigma), marker='o', color='orange')
			axs[1,0].plot(gaussian_filter1d(beam_losses["11B"], sigma), marker='o', color='orange')

			axs[0,0].set_title("Raw 11A")
			axs[1,0].set_title("Raw 11B")


			axs[0,1].plot(straight[:,0], straight[:,1], marker='o')
			axs[1,1].plot(bend[:,0], bend[:,1], marker='o')


			# fill between
			axs[0,1].fill_between(x=straight[0:offset_2+1,0], y1=straight[0:offset_2+1,1], y2=np.min(straight[:,1]), alpha=0.2, color="red")
			axs[0,1].fill_between(x=straight[offset_2:-1,0], y1=straight[offset_2:-1,1], y2=np.min(straight[:,1]), alpha=0.2, color="blue")
			axs[1,1].fill_between(x=bend[0:offset_2+1,0], y1=bend[0:offset_2+1,1], y2=np.min(bend[:,1]), alpha=0.2, color="red")
			axs[1,1].fill_between(x=bend[offset_2:-1,0], y1=bend[offset_2:-1,1], y2=np.min(bend[:,1]), alpha=0.2, color="blue")
	

			axs[0,1].set_title("Replicated Fill Pattern\n11 A (straight)")
			axs[1,1].set_title("11 B (bend)")

			for i in range(2):
				axs[i,1].set_xlabel("ADC cycle")
				axs[i,1].set_ylabel("Average beam loss")

			# plt.savefig(os.path.join(data_path, "BLM_fill_pattern_sector_11.png"),  dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
			print("Data plotted!")

			plt.show()

		elif sectors == "all":
			# create a new figure for each sector.
			for sector in range(1, 14+1, 1):

				# Straight on top, bend on bottom
				fig, axs = plt.subplots(2, 2, figsize=(6,6), constrained_layout=True)

				# plot raw data
				sigma = 4
				axs[0,0].plot(gaussian_filter1d(beam_losses[f"{sector}A"], sigma), marker='o', color='orange')
				axs[1,0].plot(gaussian_filter1d(beam_losses[f"{sector}B"], sigma), marker='o', color='orange')

				axs[0,0].set_title(f"Raw {sector}A")
				axs[1,0].set_title(f"Raw {sector}B")


				straight 	= np.array(replicated_fill_pattern[f"{sector}A"])
				bend 		= np.array(replicated_fill_pattern[f"{sector}B"])

				axs[0,1].plot(straight[:,0], straight[:,1], marker='o')
				axs[1,1].plot(bend[:,0], bend[:,1], marker='o')

				axs[0,1].set_title(f"Replicated Fill Pattern\n{sector} A (straight)")
				axs[1,1].set_title(f"{sector} B (bend)")

				for i in range(2):
					axs[i,1].set_xlabel("ADC cycle")
					axs[i,1].set_ylabel("Average beam loss")

			# plt.savefig(os.path.join(data_path, "BLM_fill_pattern_sector_11.png"),  dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

			plt.show()

			print("Data plotted!")

	except Exception:
		logging.error(traceback.format_exc())

	return None

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def onValueChange(pvname=None, value=None, host=None, **kws):

    global set_adc_offset, set_adc_window

    # if value == 1:
    # Fake injection

    # if value == 2:
    # Gun injection

    if value == 2:
        print(f"current adc_offset = {set_adc_offset}")

        print("Injection detected! Sleeping...")
        time.sleep(10)

        print("Awake :) Continuing...")

        # # reset ADC windows and offsets
        # for key in blm.sumdec_adc_mask_offset:
        #     blm.sumdec_adc_mask_offset[key].put(set_adc_offset, use_complete=True)
        # # wait for all puts to complete
        # for key in blm.sumdec_adc_mask_offset:
        #     while not blm.sumdec_adc_mask_offset[key].put_complete:
        #         time.sleep(0.05)

        # print("done reapplying windows!")

# Run the experiment
main()
