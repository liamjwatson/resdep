import json
import numpy as np
import matplotlib.pyplot as plt 
import os
import datetime
from scipy.ndimage import gaussian_filter1d

# --- consts
f_rev 		= 1.38799e3 			# kHz
g 			= 2.0023193043609236
a_g 		= (g - 2)/2
m_e 		= 9.109383713928e-31 	# kg
c 			= 299792458				# m/s
e 			= 1.602176634e-19		# C

# %%
# --- import data
data_path = os.path.join('drive_betatron', 'Data', '2025-10-20', '1926h')
# metadata json
with open(os.path.join(data_path, 'metadata.json'), 'r') as f:
	metadata = json.load(f)
f.close()
# timestamps txt
timestamps = []
with open(os.path.join(data_path, 'timestamps.txt'), 'r') as f:
	for line in f.readlines():
		timestamps.append(datetime.datetime.strptime(line[:-1], "%Y-%m-%d %H:%M:%S"))	# have to remove \n
f.close()
timestamp_array = np.array(timestamps)
seconds = np.arange(0, len(timestamps), 1)
# current txt
current = []
with open(os.path.join(data_path, 'current.txt'), 'r') as f:
	for line in f.readlines():
		current.append(float(line))
f.close()
current_array = np.array(current)
# beam_losses json
with open(os.path.join(data_path, 'beam_losses.json'), 'r') as f:
	beam_losses = json.load(f)
f.close()

# %%

# # --- plot current decay
# fig, ax = plt.subplots(figsize=(8,4), constrained_layout=True)

# # fit line
# m, c = np.polyfit(x=seconds[30:60], y=current_array[30:60], deg=1)
# ax.plot(seconds[:60], current_array[:60])
# ax.plot(seconds[30:60], m*seconds[30:60] + c)

# # subtract fit
# fig, ax = plt.subplots(figsize=(8,4), constrained_layout=True)
# ax.plot(seconds[:60], current_array[:60] - (m*seconds[:60] + c))


exp_delay = metadata['baseline duration (s)']

# --- plot data
fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# plot normalised data:
norm_beam_losses = {}
for index, key in enumerate(beam_losses):
	norm_beam_losses[key] = gaussian_filter1d(beam_losses[key]/np.max(beam_losses[key]), 1)
	if index % 2 == 0:
		axs[0].plot(seconds, norm_beam_losses[key] - 0.15*index, '-', label=key)
	else:
		axs[0].plot(seconds, norm_beam_losses[key] - 0.15*index, '-', label=key)	
	axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
axs[0].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
axs[0].set_title('All sectors')
axs[0].set_xlabel('seconds')

# plot just sector 11 (normalised)
axs[1].plot(seconds, norm_beam_losses['11A'], '-', label='11A')
axs[1].plot(seconds, norm_beam_losses['11B'] + 0.15, '-', label='11B')
axs[1].axvline(x=exp_delay, ymin=0, ymax=1, linestyle='--', color='k', alpha=0.7)
axs[1].legend(loc='lower right')
axs[1].set_title('Sector 11')





# # --- plot data - current normalised
# fig2, axs2 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # --- normalise to current
# beam_losses_Inorm = {}
# for key in beam_losses:
# 	beam_losses_Inorm[key] = np.array(beam_losses[key])/(current_array**2)

# # plot normalised data:
# norm_beam_losses = {}
# for index, key in enumerate(beam_losses):
# 	norm_beam_losses[key] = gaussian_filter1d(beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]), 0.1)
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs2[0].plot(seconds, norm_beam_losses[key] - 0.15*index, '-', label=key)
# 	else:
# 		axs2[0].plot(seconds, norm_beam_losses[key] - 0.15*index, '-', color='k', label=key)	
# 	axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs2[0].set_title('All sectors (current normalised)')

# # plot just sector 11 (normalised)
# axs2[1].plot(seconds, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
# axs2[1].plot(seconds, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
# axs2[1].legend(loc='lower right')
# axs2[1].set_title('Sector 11 (current normalised)')


plt.show()
# %%
