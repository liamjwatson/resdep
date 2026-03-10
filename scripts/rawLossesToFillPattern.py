"""
Solely plotting code for alignBLMtoFillPattern.py | timeAlginment.py Classes

Bins loss data for each ADC window/offset
"""

import os
import json
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import logging, traceback
from typing import Literal
from scipy.ndimage import gaussian_filter1d

# -------------------------------------------------------------------------------------------------------------------------------
# import data

# data path
date_str = "2026-02-22"
time_str = "0738h"
current_path = os.getcwd()
parent_path = os.path.dirname(current_path)
data_path = os.path.join(parent_path, "fill_pattern_alignment", "Data", date_str, time_str)

# import metadata
with open(os.path.join(data_path, "metadata.json"), "r") as f:
	metadata = json.load(f)

# import data 
with open(os.path.join(data_path, "beam_losses.json"), "r") as f:
	beam_losses = json.load(f)

FPM_Y_offset: list[float] = []
with open(os.path.join(data_path, "FPM_Y.txt"), "r") as f:
	for line in f.readlines():
		FPM_Y_offset.append(float(line))

# --- load variable names and formats:


data_points_per_bin = metadata["data points per bin"]
bins = len(beam_losses["11B"])//data_points_per_bin

replicated_fill_pattern: dict[str, npt.NDArray[np.float64]] = {}
for key in beam_losses:
	replicated_fill_pattern[key] = np.zeros([bins, 2])

bucket_shift_Y = metadata["bucket shift IGPF:Y"]
set_adc_window = metadata["initial adc window"]
window_centre = (set_adc_window-1)//2

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
# FPM_Y_original (unshifted)
# calculate original fill pattern by undoing offset
FPM_Y_original = FPM_Y_offset.copy()
for i in range(bucket_shift_Y):
	FPM_Y_original.insert(0, FPM_Y_original.pop(-1))


SUM_DEC = 86
buckets_per_cycle = 360/SUM_DEC
cycles_per_bucket = 1/buckets_per_cycle


# -------------------------------------------------------------------------------------------------------------------------------
# control main
def main() -> None:

	bin_data()

	calculate_adc_counter_windows(sector="11", method="loss_minimum")

	plot_data(sectors="11")
	
	calculate_adc_counter_windows(sector="11", method="integrated_half")

	plot_data(sectors="11")

	return None

# -------------------------------------------------------------------------------------------------------------------------------
# Bin data
def bin_data() -> None:

	print(f"data_points_per_bin={data_points_per_bin}")
	print(f"bins={bins}")

	for i in range(0, bins, 1):
		for key in beam_losses:
			binned_data = np.mean(beam_losses[key][i*data_points_per_bin:(i+1)*data_points_per_bin])
			replicated_fill_pattern[key][i] = [i+window_centre, binned_data]

	return None

# for key in beam_losses:
# 	for i in range(0,num_offsets,1):
# 		replicated_fill_pattern[key].append([i, np.mean(beam_losses[key][(i):(i+data_points_per_bin)])])

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
def calculate_adc_counter_windows(sector: str, method: Literal["loss_minimum", "integrated_half"] = "loss_minimum") -> None:
	"""
	Calculates the offsets and window lengths of the two counter windows for a specific sector \\
	**Note**: this only works for one sector, since there is no way to make the ADC windows wrap around T0. \\
	Thus, the 'half' of the beam that the ADC windows capture informs the bunches that should be depolarised by the BbB, \\
	and said half is unlikely to line up with the bunch numbers (*i.e.* unlikely to be bunches 1--180). \\
	For now, uses the bend as the reference, but could in the future average the windows between the straight and the bend.
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

	Updates (class scope)
	-------
	calculated_adc_counter_windows : list[int]
		list containing counters 1 & 2 window and offset settings for the given sector \\
		Values are a list of [offset_1, window_1, offset_2, window_2]

	depolarised_bunches : list[int]
		list containing the start:stop range of bunches to be depolarised using the BbB
		This is basically a conversion from the ADC cycles (window length and pos) to bunch number
	"""

	# global calculated_adc_counter_windows, depolarised_bunches, adc_cycle_at_loss_min, bucket_at_loss_min, FPM_Y_minimum_bucket, depolarised_bunch_start, depolarised_bunch_end
	global calculated_adc_counter_windows, depolarised_bunch_start, depolarised_bunch_end


	dividing_line = 0

	try:
		
		loss_minimum 			: float = np.min(replicated_fill_pattern[f"{sector}B"][:,1])
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

# run the script
main()
