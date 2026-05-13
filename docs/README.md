# Resonant Depolarisation
## Purpose

## Physics
$$
    P_0 = \frac{W_{\uparrow\downarrow}-W_{\downarrow\uparrow}}{W_{\uparrow\downarrow}+W_{\downarrow\uparrow}} = \frac{8}{5\sqrt{3}} = 92.38\%
$$

$$
    E 
    =
    \left(
        \frac{f_\mathrm{rdp}}{f_\mathrm{rev}} \mp n 
    \right)
    \frac{m_e c^2}{a_g},
    \quad \text{where} \quad
    f_\mathrm{rdp} 
    = 
    f_\mathrm{rev} \left(
        [a_g \gamma] \pm n
    \right)
$$

## Code workflow

# SimpleGUI

## Overview
A simple graphical user interface (GUI) for use during user beam before there is a built-in GUI for Kubili. Intended used by operators and physics staff to regularly measure the beam energy. Consists of a results panel (left hand side), a control panel (right hand side), and both progress and status bars. 

The abort button on the control panel sends a fail-safe abort request to the threaded resdep worker. Depending on the status or progress of the experiment, the abort request may not be executed immediately. The status bar should provide more info on the pending abort.

## Automatic scans
When enabled, resdep experiments will run (by default unless specified) every hour after the previous has finished (approx. every 1.5 hours). When first switching to enable, an experiment will try to run immediately.

Every time an automatic scan is triggered, it will first check *if* it can run. The current requirements are:

- Machine in 'user beam' mode
- \> 150 mA beam current
- Beam polarisation is > 95% (relative, absolute is approximately 86%)
    - This involves making sure sufficient time has passed to build up polarisation from the last scan, or from a recently injected unpolarised beam.

If the automatic scan *cannot* run, it starts a timer for an hour (or specified time between scans) and then checks again. The minimum time between scans is 39 minutes which is exactly how long it takes to build up 95% polarisation from a unpolarised beam.

The experiment parameters for the automatic scans are:
- Kicker strength = 50%
- Energy bounds = 0.05 % (3.0300 to 3.0325 GeV)
- Fractional spin tune = 0.879
- First harmonic
- Forward sweep
- Sweep rate = 0.5 Hz/s
- Sweep step size = 0.5 Hz
- PV log frequency = 10 Hz

## Manual scans
### Normal scan
Uses the same default settings for the experiment as the automatic scans, but can be manually triggered.

### Wide search
Is used when there are strange issues with the machine and it is suspected that the beam energy has drifted significantly. Is not intended to be used routinely.

Has an increased frequency (energy) range of 0.35% [3.02 GeV to 3.04 GeV] over which it scans. Takes approximately 2 hours to complete. Warns the user that they may drive betatron tunes ***if*** they have drifted from their typical values. Dangerous tune range:
- $\nu_y = [0.097, 0.145]$, and
- $\nu_y = [0.855, 0.903]$