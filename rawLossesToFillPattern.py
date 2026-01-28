"""
Solely plotting code for alignBLMtoFillPattern.py | timeAlginment.py Classes

Bins loss data for each ADC window/offset
"""

import os
import json
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d

# -------------------------------------------------------------------------------------------------------------------------------
# import data

# data path
date_str = '2026-01-29'
time_str = "0800h"
data_path = os.path.join("fill_pattern_alignment", "Data", date_str, time_str)

# import metadata
with open(os.path.join(data_path, "metadata.json"), "r") as f:
	metadata = json.load(f)

# import data 
with open(os.path.join(data_path, "beam_losses.json"), "r") as f:
	beam_losses = json.load(f)

# -------------------------------------------------------------------------------------------------------------------------------
# Bin data

data_points_per_bin = metadata["data points per bin"]
bins = len(beam_losses["11B"])//data_points_per_bin

replicated_fill_pattern: dict[str, npt.NDArray[np.float64]] = {}
for key in beam_losses:
	replicated_fill_pattern[key] = np.zeros([bins, 2])

print(f"data_points_per_bin={data_points_per_bin}")
print(f"bins={bins}")

for i in range(0, bins, 1):
	for key in beam_losses:
		binned_data = np.mean(beam_losses[key][i*data_points_per_bin:(i+1)*data_points_per_bin])
		replicated_fill_pattern[key][i] = [i, binned_data]

# for key in beam_losses:
# 	for i in range(0,num_offsets,1):
# 		replicated_fill_pattern[key].append([i, np.mean(beam_losses[key][(i):(i+data_points_per_bin)])])

# -------------------------------------------------------------------------------------------------------------------------------
# Plot data

sectors = "all"

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

# elif sectors == "all":
#     # create a new figure (window) for each sector. This is 14 plots...
#     for sector in range(1,14+1,1):
#         # Straight on top, bend on bottom
#         fig, axs = plt.subplots(2,1, figsize=(16,8), constrained_layout=True)
        
#         axs[0].plot(replicated_fill_pattern[f"{sector}A"][:,0], replicated_fill_pattern[f"{sector}A"][:,1], marker='o')
#         axs[1].plot(replicated_fill_pattern[f"{sector}B"][:,0], replicated_fill_pattern[f"{sector}B"][:,1], marker='o')

#         axs[0].set_title(f"Replicated Fill Pattern\n{sector} A (straight)")
#         axs[1].set_title(f"{sector} B (bend)")

#         for i in range(2):
#             axs[i].set_xlabel("ADC cycle")
#             axs[i].set_ylabel("Average beam loss")

#         plt.savefig(os.path.join(data_path, f"BLM_fill_pattern_sector_{sector}.png"),  dpi=300, bbox_inches='tight', facecolor='white', transparent=False)

#     print("Data plotted!")

#     plt.show()

