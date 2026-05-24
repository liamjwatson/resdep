# Getting started

## Description
Beam energy diagnostic tool using resonant depolarisation at the Australian Synchrotron

Sweeps the kicker drive frequency over a specified range (the spin tune) and records beam loss on all the beam loss monitors (BLMs). Fail-safes built into the GUIs. Saves data to `\asp\usr\data\resdep` (not to be confused with `\rdp`.) Records LCW and tunnel temperatures to correlate with beam energy (long-term) drift.

## Installation

1. Clone this repo:

    ```git clone https://bitbucket.synchrotron.org.au/scm/~watsonl/resdep.git```

2. Navigate to the repo root durectory
3. Install with **pip** or **uv**: 

=== "uv"

    ```bash
    uv pip install -e .
    ```

=== "pip"

    ```bash
    pip install .
    ```


### Installation on OPIs
1. Clone the latest **tag**, which contains the latest source distribution (*.tar.gz* file) and corresponding wheel (*.whl* file) in `./dist`.
2. Either:  
    1. **execute** `install_resdep.sh`, *or*
    2. Inside the folder, **run**

```pip install $WHEEL_FILE_NAME.whl --find-links ./ --no-index --no-deps```

## Usage
- **Kubili**: standard operation, see $URL_TO_CONFLUENCE_PAGE
- `simpleGUI`: for general / routine measurements (contains lots of checks to not disturb normal operator and use beam operations)  
- `resdepGUI`: for machine studies 

run in **python**: 

=== "`simpleGUI`"
    
    ```py linenums="1"
    from resdep import simpleGUI
    simpleGUI.spawn()
    ```
    
=== "`resdepGUI`"
    
    ```py linenums="1"
    from resdep import resdepGUI
    resdepGUI.spawn()
    ```
