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
import epics
import datetime
import time
from typing import Any, Literal
import traceback, logging
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import json

from epicsBLMs import BLMs # Libera BLM python class, stores states, dicts, functions  
# from progressBars import printProgressBar


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#

# --- constants
log_frequency = 10 # Hz
dwell_time = 2 # s
data_points_per_bin = log_frequency * dwell_time 
# Hard-coding this for first run debugging
# This can be changed later to blm.init_t0_interval_expected['11']
SUM_DEC = 86

# define inits
set_adc_offset: int = 0
set_adc_window: int = 10
# select counting mode; 0: differential, 1: normal (thresholding)
set_counting_mode: int = 0

projected_end_time = (SUM_DEC) * dwell_time
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
    "Current": current,
    "start time": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
}
	
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def main() -> tuple[list[int], str]:
    """
    Sweeps over ADC offset for minimum ADC window. \\
	Stores ADC_offset vector and blm.loss for every sector. \\
    Bins (usually) 5 s of data, stores average beam loss per ADC cycle
    in replicated_fill_pattern dict with {sector,section} keys
    """

    # global variable assignment since i'm unable to pass variables in a PV callback
    global set_adc_offset, set_adc_window

    # --- assign PVs: injection trigger
    injection_trigger = epics.pv.get_pv("TS01EVG01:INJECTION_MODE_STATUS", connect=True, callback=onValueChange)

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

        blm.restore_inits(mode="decimation")
        blm.restore_inits(mode="adc_counter_masks")

        bin_data()
        
        calculated_adc_counter_windows, depolarised_bunches = calculate_adc_counter_windows(sector="11")

        save_data()

        # Remove callback to trigger
        try: 
            injection_trigger.remove_callback()
        except Exception:
            logging.error(traceback.format_exc())

        plot_data(sectors="all")

        print("Experiment done!")
       
    return calculated_adc_counter_windows, depolarised_bunches

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
def calculate_adc_counter_windows(sector: str) -> tuple[list[int], str]:
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

    Returns
    -------
    calculated_adc_counter_windows : list[int]
        list containing counters 1 & 2 window and offset settings for the given sector \\
        Values are a list of [offset_1, window_1, offset_2, window_2]
    
    depolarised_bunches : list[int]
        list containing the start:stop range of bunches to be depolarised using the BbB
        This is basically a conversion from the ADC cycles (window length and pos) to bunch number
    """

    # ! I must account for the fill pattern offset in the BBB!
    # ! Look for the epics GUI, there should be an offset PV
    # ! They just adjust it so that the fill pattern looks good on the big screens.

    # TODO: Look at the manual for ADC delay. Either need to time align the windows or 
    # TODO: do appropriate calculation of the correct "half" to depolarise, given now the window is 5/10 adc cycles.


    # format: [offset_1, window_1, offset_2, window_2]
    calculated_adc_counter_windows: list[int] = []
    # format start:end, e.g. "0:150"
    depolarised_bunches: str = "" 

    buckets_per_cycle = 360/86
    cycles_per_bucket = 1/buckets_per_cycle

    try:

        loss_minimum: float = np.min(replicated_fill_pattern[f"{sector}B"][:,1])

        adc_cycle_at_loss_min: int = np.where(replicated_fill_pattern[f"{sector}B"][:,1] == loss_minimum)[0].tolist()[0]

        print(f"ADC cycle at loss minimum = {adc_cycle_at_loss_min}")

        # case (1): centred fill pattern
        if (adc_cycle_at_loss_min <= 30*cycles_per_bucket) or (adc_cycle_at_loss_min >= 330*cycles_per_bucket):
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

        else:
            dividing_line = 0
            raise ArithmeticError("Issue calculating adc_windows. See function \"calculate_adc_counter_windows()\".")

        # format: [offset_1, window_1, offset_2, window_2]
        calculated_adc_counter_windows = [0, dividing_line, dividing_line, (86 - dividing_line)]

        depolarised_bunches = f"0:{int(dividing_line*buckets_per_cycle)}"

        print("Calculated adc_counter windows, format: [offset_1, window_1, offset_2, window_2]")
        print(calculated_adc_counter_windows)
        print("Corresponding depolarised bunches for BbB:")
        print(depolarised_bunches)

    except Exception:
        logging.error(traceback.format_exc())
    

    return calculated_adc_counter_windows, depolarised_bunches


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

        # --- backup, store each np.array as text with filename as key. 
        # Probably keep these in their own folder
        # for key in replicated_fill_pattern:
        #     np.savetxt(os.path.join(data_path, "individual_loss_files", f"{key}.txt"), replicated_fill_pattern[key], delimiter=',')

        # --- raw beamloss without binning?
        # beam losses, as .json:
        with open(os.path.join(data_path, 'beam_losses.json'), 'w') as f:
            json.dump(beam_losses, f)

        print("Data saved!")

    except Exception:
		# Logs the error appropriately. 
        logging.error(traceback.format_exc())

    return None

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def plot_data(sectors: Literal["all", "11"]) -> None:
    """
    Plots replicated_fill_pattern (average beam loss per ADC cycle) for all sectors just sector 11. 
    """
    try:
        
        print("Plotting data...")

        if sectors == "11":
            # Straight on top, bend on bottom            
            fig, axs = plt.subplots(2,1, figsize=(4,6), constrained_layout=True)

            axs[0].plot(replicated_fill_pattern["11A"][:,0], replicated_fill_pattern["11A"][:,1], marker='o')
            axs[1].plot(replicated_fill_pattern["11B"][:,0], replicated_fill_pattern["11B"][:,1], marker='o')

            axs[0].set_title("Replicated Fill Pattern\n11 A (straight)")
            axs[1].set_title(f"11 B (bend)\nwindow={set_adc_window}")

            for i in range(2):
                axs[i].set_xlabel("ADC cycle")
                axs[i].set_ylabel("Average beam loss")

            plt.savefig(os.path.join(data_path, "BLM_fill_pattern_sector_11.png"),  dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

            plt.show()


        elif sectors == "all":
            # create a new figure (window) for each sector. This is 14 plots...
            for sector in range(1,14+1,1):
                # Straight on top, bend on bottom
                fig, axs = plt.subplots(2,1, figsize=(4,6), constrained_layout=True)
                
                axs[0].plot(replicated_fill_pattern[f"{sector}A"][:,0], replicated_fill_pattern[f"{sector}A"][:,1], marker='o')
                axs[1].plot(replicated_fill_pattern[f"{sector}B"][:,0], replicated_fill_pattern[f"{sector}B"][:,1], marker='o')

                axs[0].set_title(f"Replicated Fill Pattern\n{sector} A (straight)")
                axs[1].set_title(f"{sector} B (bend)\nwindow={set_adc_window}")

                for i in range(2):
                    axs[i].set_xlabel("ADC cycle")
                    axs[i].set_ylabel("Average beam loss")

                plt.savefig(os.path.join(data_path, f"BLM_fill_pattern_sector_{sector}.png"),  dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

            plt.show()

        print("Data plotted!")

    except Exception:
		# Logs the error appropriately. 
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