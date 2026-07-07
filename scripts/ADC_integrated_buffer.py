"""
Test script to analyse the update / refresh frequency of the ADC integrated buffer.
If the integrated buffer is only outputting 16 values, do this:

root@libera:~# rw
root@libera:~# nano /opt/libera-ioc/db/blm_monitor.db     # this is a file that maps native MCI commands to EPICS PVs

find the ADC integrated signal: (ctrl+W "adc_integrated"):
"record(liberaSignal, "$(P):signals:adc_integrated") .... "
change field(NGRP, 16) to (NGRP, 86) and save the file

root@libera:~# ro
root@libera:~# /opt/etc/init.d/S80libera-ioc restart    # this will restart the IOC adapter
# you may also need to restart some user-end interface
"""

import time
import epics
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
import numpy as np

# import SR11 bend PV
sector = 3
SUMDEC_periods_PV = epics.pv.get_pv(f"SR{sector:02d}BLM01:decimation:sumdec_periods_sp", connect=True)
# set sumdec periods
SUMDEC_PERIODS = 20
SUMDEC_periods_PV.put(SUMDEC_PERIODS)
time.sleep(2)
# read int buffer
integrated_buffer_PV = epics.pv.get_pv(f"SR{sector:02d}BLM01:signals:adc_integrated.B", connect=True)
int_buff = integrated_buffer_PV.get(use_monitor=True)

plt.ion()
fig, axes = plt.subplots(figsize=(7,7), layout="tight")
fig.suptitle("ADC integrated buffer")
axes.set_xlabel("ADC cycle")
axes.set_ylabel("Integrated loss")

def interruptible_sleep(seconds: int):
    eyes_closed = time.time()
    while time.time() < (eyes_closed + seconds):
        time.sleep(0.1)

# plot in loop
loop_counter = 0
sleep_time = 10 # s
while True:
    integrated_buffer = gaussian_filter1d(integrated_buffer_PV.get(use_monitor=True), sigma=3)
    # integrated buffer is upside down, so flip and normalise
    integrated_buffer = integrated_buffer/np.max(integrated_buffer)
    integrated_buffer = -1 * integrated_buffer + 1
    time.sleep(0.1)
    if integrated_buffer is not None:
        axes.plot(integrated_buffer)
    fig.canvas.draw()
    fig.suptitle(f"ADC integrated buffer for sector {sector}\ndt = {loop_counter*sleep_time} s")
    fig.canvas.flush_events()
    loop_counter += 1

    # wait for 10 s
    interruptible_sleep(seconds=sleep_time)
