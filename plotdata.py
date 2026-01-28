from typing import Any
import json
import numpy as np
import matplotlib.pyplot as plt 
import os
from scipy.ndimage import gaussian_filter1d

# --- consts
f_rev 		= 1.38799e3 			# kHz
g 			= 2.0023193043609236
a_g 		= (g - 2)/2
m_e 		= 9.109383713928e-31 	# kg
c 			= 299792458				# m/s
e 			= 1.602176634e-19		# C

# --- import data
data_path = os.path.join('Data', '2025-11-09', '1533h')
# metadata json
with open(os.path.join(data_path, 'metadata.json'), 'r') as f:
	metadata = json.load(f)
f.close()
# freqs txt
freqs = []
with open(os.path.join(data_path, 'freqs.txt'), 'r') as f:
	for line in f.readlines():
		freqs.append(float(line)/1e3)	# Hz -> kHz
f.close()
freqs = np.array(freqs)
# current txt
current = []
with open(os.path.join(data_path, 'current.txt'), 'r') as f:
	for line in f.readlines():
		current.append(float(line))
f.close()
# beam_losses json
with open(os.path.join(data_path, 'beam_losses.json'), 'r') as f:
	beam_losses = json.load(f)
f.close()
# beam_losses adc window 1
with open(os.path.join(data_path, 'adc_counter_loss_1.json'), 'r') as f:
	beam_loss_window_1 = json.load(f)
f.close()
# beam_losses adc window 2
with open(os.path.join(data_path, 'adc_counter_loss_2.json'), 'r') as f:
	beam_loss_window_2 = json.load(f)
f.close()



# Assign metadata to variables:
harmonic = metadata['harmonic']



# --- plot data
fig, axs = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# plot normalised data:
norm_beam_losses = {}
for index, key in enumerate(beam_losses):
	norm_beam_losses[key] = gaussian_filter1d(beam_losses[key]/np.max(beam_losses[key]), 2)
	if index % 2 == 0:
		axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', label=key)
	else:
		axs[0].plot(freqs, norm_beam_losses[key] - 0.15*index, '-', color='k', label=key)	
	axs[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
axs[0].set_title('All sectors')
axs[0].set_xlabel('frequency (kHz)')

# Create energy top axis
def energy_calc(freq):
	return (freq/f_rev - harmonic + 6) * m_e*c**2/(e*a_g*1e9)
def freq_calc(energy):
	return f_rev * (energy*1e9*e*a_g/(m_e*c**2) + harmonic - 6)
second_axis = axs[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
second_axis.set_xlabel('Energy (GeV)')

# plot just sector 11 (normalised)
axs[1].plot(freqs, norm_beam_losses['11A'], '-', label='11A')
axs[1].plot(freqs, norm_beam_losses['11B'] + 0.15, '-', label='11B')
axs[1].legend(loc='lower right')
axs[1].set_title('Sector 11')



# # --- plot data - current normalised
# fig2, axs2 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # --- normalise to current
# beam_losses_Inorm = {}
# for key in beam_losses:
# 	beam_losses_Inorm[key] = np.array(beam_losses[key])/(np.array(current)**2)

# # plot normalised data:
# for index, key in enumerate(beam_losses):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs2[0].plot(freqs, beam_losses_Inorm[key]/np.max(beam_losses_Inorm[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs2[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs2[0].set_title('All sectors (current normalised)')

# second_axis2 = axs2[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis2.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs2[1].plot(freqs, beam_losses_Inorm['11A']/np.max(beam_losses_Inorm['11A']), '-', label='11A')
# axs2[1].plot(freqs, beam_losses_Inorm['11B']/np.max(beam_losses_Inorm['11B']) + 0.15, '-', label='11B')
# axs2[1].legend(loc='lower right')
# axs2[1].set_title('Sector 11 (current normalised)')

plt.show()

# ----------------------------------- #
# ------	ADC counter loss 	----- #
# ----------------------------------- #
#


freqs_array = np.array(freqs)

# # --- plot data
# fig3, axs3 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)


# # plot normalised data:
# for index, key in enumerate(beam_loss_window_1):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs3[0].plot(freqs_array, beam_loss_window_1[key]/np.max(beam_loss_window_1[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs3[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs3[0].set_title('ADC counter loss 1 - All sectors')
# axs3[0].set_xlabel('frequency (kHz)')

# # Create energy top axis
# second_axis = axs3[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs3[1].plot(freqs_array, beam_loss_window_1['11A']/np.max(beam_loss_window_1['11A']), '-', label='11A')
# axs3[1].plot(freqs_array, beam_loss_window_1['11B']/np.max(beam_loss_window_1['11B']) + 0.15, '-', label='11B')
# axs3[1].legend(loc='lower right')
# axs3[1].set_title('Sector 11')

# # plt.savefig(os.path.join(data_path, "ADC_counter_loss_1.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)


# # --- plot data
# fig4, axs4 = plt.subplots(1,2, figsize=(16,8), constrained_layout=True)

# # plot normalised data:
# for index, key in enumerate(beam_loss_window_2):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', label=key)
# 	else:
# 		axs4[0].plot(freqs_array, beam_loss_window_2[key]/np.max(beam_loss_window_2[key]) - 0.15*index, '-', color='k', label=key)	
# 	axs4[0].legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs4[0].set_title('ADC counter loss 2 - All sectors')
# axs4[0].set_xlabel('frequency (kHz)')

# # Create energy top axis
# second_axis = axs4[0].secondary_xaxis("top", functions=(energy_calc, freq_calc))
# second_axis.set_xlabel('Energy (GeV)')

# # plot just sector 11 (normalised)
# axs4[1].plot(freqs_array, beam_loss_window_2['11A']/np.max(beam_loss_window_2['11A']), '-', label='11A')
# axs4[1].plot(freqs_array, beam_loss_window_2['11B']/np.max(beam_loss_window_2['11B']) + 0.15, '-', label='11B')
# axs4[1].legend(loc='lower right')
# axs4[1].set_title('Sector 11')

# # plt.savefig(os.path.join(data_path, "adc_counter_loss_2.png"), dpi=300, bbox_inches='tight', facecolor='white', transparent=False)




# ----------------------------------- #
# ------		Ratio Loss  	----- #
# ----------------------------------- #


# ratio_loss: dict[str, Any] = {}

# for key in beam_loss_window_1:
# 	ratio_loss[key] = np.array(beam_loss_window_1[key])/np.array(beam_loss_window_2[key])

# fig5, axs5 = plt.subplots(figsize=(16,8), constrained_layout=True)

# for index, key in enumerate(ratio_loss):
# 	# Colour straight, make corresponding arc black
# 	if index % 2 == 0:
# 		axs5.plot(freqs_array, ratio_loss[key] - 0.01*index, '-', label=key)
# 	else:
# 		axs5.plot(freqs_array, ratio_loss[key] - 0.01*index, '-', color='k', label=key)	
# 	axs5.legend(bbox_to_anchor=(0.5, -0.2), loc='lower center', ncol=7)
# axs5.set_title('ADC counter loss 2 - All sectors')
# axs5.set_xlabel('frequency (kHz)')


# plt.show()
