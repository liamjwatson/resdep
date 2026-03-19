# Resonant depolarisation

Beam energy diagnostic tool using resonant depolarisation at the Australian Synchrotron

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Description](#description)
- [Physics](#physics)
<!-- - [Contributing](#contributing) -->

## Installation

1. Clone this repo \
`git clone https://bitbucket.synchrotron.org.au/scm/~watsonl/resdep.git`
2. Navigate to the repo root durectory
3. Install with `pip` or `uv`: \
`pip install .` \
*or* \
`uv pip install -e .`

For installation on OPIs:
1. Clone the latest **tag**, which contains the latest source distribution (`.tar.gz` file) and corresponding binary distribution (wheel, `.whl` file) in `./dist`.
2. Either:  
a. **execute** `install_resdep.sh`, *or* \
b. Inside the folder, **run** \
`pip install $WHEEL_FILE_NAME.whl --find-links ./ --no-index --no-deps` \
where you replace `$WHEEL_FILE_NAME` with the name of the `.whl` file.

## Usage

**run** in `python`: \
`from resdep import resdepGUI`\
`resdepGUI.spawn()`

Without `pip install`, running as a script from the repo root: \
`ipython3 -m resdep.resdepGUI`


## Description

Sweeps the kicker drive frequency over a specified range and records beam loss on all the beam loss monitors (BLMs).

Current capabilities
- Sweeps kicker at up to 20 Hz, PV readback at 20 Hz (as fast as the network allows really)
- Fails-safe on keyboard.interrupt (reset drive amplitude to 0, takes out scrapers, saves all the data)
- Plots the data

## Physics

[Complete physics description found here](https://confluence.synchrotron.org.au/confluence/display/AP/Resonant+Depolarisation)

An accurate measurement (keV resolution) of the beam energy based on the electron polarisation resulting from synchrotron radiation.
- Electrons in the storage ring are polarised parallel or anti-parallel to the dipole magnet field direction (up)
- The Sokolov-Ternov effect states that with the emission of synchrotron radiation, there is a probability to spin flip, which is naturally skewed toward anti-parallel (spin flip up-to-down) such that the beam reaches a theoretical 92% polarisation (down)
- The Touschek scattering cross-section is polarisation dependent. Polarised beams have longer lifetime and less beam loss
- The polarised electron spin precesses at the spin tune, which is proportional to the Lorentz factor and not many other parameters. Therefore, **an accurate measurement of the spin tune results in an accurate measurement of the beam energy (keV resolution on a GeV measurement)**
- Driving a kicker magnet at the spin resonance depolarises the beam by increasing the angle of electron precession, resulting in a step-change in the beam losses. Therefore we sweep the kicker frequency, record the spin tune / resonance condition as the freqency at which we see a sharp increase in the beam loss, and accurately determine the beam energy.