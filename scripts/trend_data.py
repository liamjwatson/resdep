#!/usr/bin/env python3
"""
Trend beam energy over time. 
Try to correlate with other variables like temperature.
"""   
import matplotlib.dates
from dataclasses import dataclass, field
import itertools
import re
import logging
from typing import Union
import json
import datetime
from pathlib import Path
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

from resdep.experiment import ProcessedData, ResonantDepolarisation
from resdep._fitting import Fitter, FittingError
from resdep._plotting import StandaloneGraph, Plotter


@dataclass
class Temperatures: 
    beam_pipe: dict[str, list[float]]  = field(default_factory=dict)
    magnet: dict[str, list[float]]     = field(default_factory=dict)
    RF601_body: dict[str, list[float]] = field(default_factory=dict)
    RF601_LCW: dict[str, list[float]]  = field(default_factory=dict)
    RF602_body: dict[str, list[float]] = field(default_factory=dict)
    RF602_LCW: dict[str, list[float]]  = field(default_factory=dict)
    RF701_body: dict[str, list[float]] = field(default_factory=dict)
    RF701_LCW: dict[str, list[float]]  = field(default_factory=dict)
    RF702_body: dict[str, list[float]] = field(default_factory=dict)
    RF702_LCW: dict[str, list[float]]  = field(default_factory=dict)
    slab: dict[str, list[float]]       = field(default_factory=dict)
    SUBH: dict[str, list[float]]       = field(default_factory=dict)
    tunnel_air: dict[str, list[float]] = field(default_factory=dict)
    component_names: list[str] = field(
        default_factory=lambda: [
            "beam_pipe",             
            "magnet",
            "RF601_body",
            "RF601_LCW",
            "RF602_body",
            "RF602_LCW",
            "RF701_body",
            "RF701_LCW", 
            "RF702_body",
            "RF702_LCW",
            "slab",
            "SUBH",
            "tunnel_air",
        ]
    )

    def load(self, data_paths: list[Path]) -> None:
        """
        Load all the temp values from every data path and concatenate them
        by component
        """         

        # initialise some dicts with value = list[float]
        for component_name in self.component_names:

            storage: dict[str, list[float]] = {}

            for index, path in enumerate(data_paths):
                
                filepath = path / "temperatures" / (
                        component_name+"_temperatures.json"
                )
                with open(filepath, "r") as f:
                    temp: dict[str, float] = json.load(f)

                # initialise storage dict with PV keys
                if index == 0:
                    for key in temp:
                        storage[key] = []
                
                for key, value in temp.items():
                    storage[key].append(value)

            setattr(self, component_name, storage)

        return None
    

def get_data_paths(dates: list[str]) -> list[Path]:
    """
    Generate a list of paths that contain resdep data.
    For loading into data classes.

    Parameters
    ----------
    dates: list[str]
        list of dates of format YYYY-MM-DD

    Returns
    -------
    data_paths: list[Path]
        list of pathlib.Path objects
    """                     
    path_prefix = Path("Z:/usr/data/resdep")
    data_paths: list[Path] = []
    filenames: list[str] = [
            "set_freqs",
            "adc_counter_loss_1",
            "adc_counter_loss_2",
            "timestamps"
    ]
    legacy_extensions: list[str] = [
            ".txt",
            ".json",
            ".json",
            ".txt"
    ]
    legacy_filenames: list[str] = [
            name+ext for name, ext in zip(filenames, legacy_extensions)
    ]
    compressed_extensions: list[str] = [".npz"] * len(filenames)
    compressed_filenames: list[str] = [
            name+ext for name, ext in zip(filenames, compressed_extensions)
    ]
    for date in dates:
        year = date[:4]
        date_path = path_prefix / year /  date 
        for path in date_path.iterdir():
            legacy_files_exist: list[bool] = [
                (path / filename).exists() for filename in legacy_filenames
            ]
            compressed_files_exist: list[bool] = [
                (path / filename).exists() for filename in compressed_filenames
            ]

            if path.is_dir() and (
                    all(legacy_files_exist) or all(compressed_files_exist)
                ):
                data_paths.append(path)
                print(f"found {path}")

            else:
                print(f"ERROR: no data at {path}")

    return data_paths

def get_timestamps(
        data_paths: list[Path],
        ) -> tuple[list[str], list[datetime.datetime]]:
    """
    Get a list of starting times for each diagnostic measurement
    """         
    timestamps: list[str] = []
    datetimes: list[datetime.datetime] = []
    for path in data_paths:

        timestamps_files = [file for file in path.glob("timestamps.*")]
        npz_exists: bool = any([file.suffix == ".npz" for file in timestamps_files])
        if npz_exists:
            with np.load(path / "timestamps.npz") as loaded:
                timestamps_datetimes = loaded["arr_0"].tolist()

            start_time: datetime.datetime = timestamps_datetimes[0]
            # convert to str
            first_timestamp: str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            timestamps.append(first_timestamp)
        else:
            with open(path / "timestamps.txt", "r") as f:
                first_timestamp: str = f.readline()

            timestamps.append(first_timestamp)
            # convert to datetime
            start_time: datetime.datetime = datetime.datetime.strptime(
                    first_timestamp[:-1],
                    "%Y-%m-%d %H:%M:%S"
            )
            datetimes.append(start_time)

    return timestamps, datetimes

def create_data_objects(
        data_path: Path
    ) -> tuple[ProcessedData, ResonantDepolarisation]:
    """
    Create processed data object loaded with 
    the data from the corresponding path.
    """             

    resdep = ResonantDepolarisation()

    
    with open(data_path / "metadata.json", "r") as f:
        metadata = json.load(f)

    resdep.f_rev = metadata["f_rev"]
    resdep.tune = metadata["fractional tune"]
    resdep.harmonic = metadata["harmonic"]
    resdep.res_freq = resdep.f_rev * (resdep.tune + resdep.harmonic)
    resdep.sweep_step_size = metadata["sweep step size (Hz)"]

    set_freqs: list[float] = []
    set_freqs_files = [file for file in data_path.glob("set_freqs.*")]
    npz_exists: bool = any([file.suffix == ".npz" for file in set_freqs_files])
    if npz_exists:
        with np.load(data_path / "set_freqs.npz") as loaded:
            set_freqs = loaded["arr_0"].tolist()
    else:
        with open(data_path / "set_freqs.txt", "r") as f:
            for line in f.readlines():
                set_freqs.append(float(line)) # kHz
    resdep.set_freqs = set_freqs

    beam_loss_files: list[Path] = [
        file for file in data_path.glob("adc_counter_loss*")
    ]
    npz_exists: list[bool] = [file.suffix == ".npz" for file in beam_loss_files]
    if any(npz_exists):
        beam_loss_window_1: dict[str, list[float]] = {}
        beam_loss_window_2: dict[str, list[float]] = {}
        with np.load(data_path / "adc_counter_loss_1.npz") as loaded:
            for key in loaded.files:
                beam_loss_window_1[key] = loaded[key].tolist()
        with np.load(data_path / "adc_counter_loss_2.npz") as loaded:
            for key in loaded.files:
                beam_loss_window_2[key] = loaded[key].tolist()

    else: # files are in legacy .json format
        with open(data_path / "adc_counter_loss_1.json", "r") as f:
            beam_loss_window_1 = json.load(f)
        # beam_losses adc window 2
        with open(data_path / "adc_counter_loss_2.json", "r") as f:
            beam_loss_window_2 = json.load(f)

    resdep.beam_loss_window_1 = beam_loss_window_1
    resdep.beam_loss_window_2 = beam_loss_window_2
    
    processed_data = ProcessedData(resdep=resdep)

    return processed_data, resdep

def get_beam_energies(data_paths: list[Path]) -> tuple[npt.NDArray, ...]:

    energies: npt.NDArray = np.zeros_like(data_paths, dtype=float)
    errors: npt.NDArray = np.zeros_like(data_paths, dtype=float)

    for index, path in enumerate(data_paths):
        beam_energy_path = path / "beam_energy.txt"
        if beam_energy_path.exists():
            with open(beam_energy_path, "r") as f:
                formatted_beam_energy: str = f.readline()

            energy, error = match_beam_energy_string(formatted_beam_energy)
            energies[index] = energy
            errors[index] = error

        else: # if there is no beam_energy.txt, do manual data analysis
            print(f"Manually calulating data from {path}.")
            processed_data, resdep = create_data_objects(data_path=path)
            processed_data.calculate_ratio_loss()
            fitter = Fitter(
                    resdep=resdep, processed_data=processed_data
            )
            try:
                *_, formatted_beam_energy, _ = fitter.automagic_fit()

                energy, error = match_beam_energy_string(formatted_beam_energy)
                energies[index] = energy
                errors[index] = error

            except FittingError:
                energies[index] = np.nan
                errors[index] = np.nan
                continue 

    return energies, errors

def match_beam_energy_string(formatted_beam_energy: str) -> tuple[float,...]:
    """
    Extract energy and error from formatted str
    """         

    beam_energy_match: Union[re.Match, None] = re.search(
            r"^(\d+\.\d+)\s(?=GeV)", # grab digits behind 'GeV'
            formatted_beam_energy
    ) 
    if beam_energy_match is not None:
        energy = float(beam_energy_match.group())
    else:
        raise TypeError("No match for energy")

    beam_error_match: Union[re.Match, None] = re.search(
            r"(\d+)\s(?=keV$)", # grab digits behind 'keV'
            formatted_beam_energy
    ) 
    if beam_error_match is not None:
        error = float(beam_error_match.group())
    else:
        raise TypeError("No match for energy error")

    return energy, error

def trend_with_temperature(dates: list[str]) -> None:
    """
    Trend beam energy with temperature over the listed dates
    """         

    data_paths = get_data_paths(dates)
    print("got paths")
    temperatures = Temperatures()
    temperatures.load(data_paths)
    print("got temperatures")
    timestamps, datetimes = get_timestamps(data_paths)
    print("got timestamps")
    energies, errors = get_beam_energies(data_paths)
    errors_GeV = np.array(errors) * 1e-6
    print("got energies")

    fig, axs = plt.subplots(2, 1, figsize=(6,4), layout="tight")

    axs[0].errorbar(x=datetimes, y=energies, yerr=errors_GeV)
    for component_name in temperatures.component_names:
        component = getattr(temperatures, component_name)

        for key, value in component.items():
            axs[1].plot(datetimes, value, label=key)

    # axs[1].legend()


    # rotate timestamp strings 90 degrees
    for ax in axs:
        ax.tick_params("x", rotation=90)

    # prevent scientific notation axes
    for ax in axs:
        ax.ticklabel_format(useOffset=False, axis="y")

    plt.show()

def trend_fit_quality(dates: list[str]) -> None:
    """
    Assess automagic fitting robustness over many different data sets
    """         
    writing_results = False
    response = input(
            "Do you want to save the beam energy results as a .txt (y/n)? "
            " + WARNING: This will overwrite current results!"
    )
    if response == "y":
        writing_results = True

    data_paths = get_data_paths(dates)

    graph = StandaloneGraph()

    for path in data_paths:
        processed_data, resdep = create_data_objects(data_path=path)
        processed_data.calculate_ratio_loss()
        fitter = Fitter(
                resdep=resdep, processed_data=processed_data
        )
        plotting = Plotter(
                resdep=resdep, processed_data=processed_data, graph=graph
        )
        

        # sliding window difference based on resonance width
        RESONANCE_WIDTH: int = 600 # Hz
        RESONANCE_WIDTH_ARG: int = int(RESONANCE_WIDTH/resdep.sweep_step_size)
        ratio_loss_difference: dict[str, npt.NDArray] = {}
        step_locations: list[float] = []
        for index, (key, loss) in enumerate(processed_data.ratio_loss.items()):
            # diff
            ratio_loss_difference[key] = (
                    loss[RESONANCE_WIDTH_ARG:]
                    - loss[:-RESONANCE_WIDTH_ARG]
            )/RESONANCE_WIDTH
            # padding
            ratio_loss_difference[key] = np.insert(
                    arr = ratio_loss_difference[key],
                    obj = 0,
                    values = np.zeros(RESONANCE_WIDTH_ARG//2)
            )
            ratio_loss_difference[key] = np.append(
                arr = ratio_loss_difference[key],
                values = np.zeros(RESONANCE_WIDTH_ARG//2)
            )
            # find max of difference
            y_max = np.max(ratio_loss_difference[key])
            x_at_y_max = processed_data.freqs_array[
                    np.argmax(ratio_loss_difference[key])
            ]
            step_locations.append(x_at_y_max)
            # plot
            vertical_offset = index * 0.5 / RESONANCE_WIDTH
            graph.axes.plot(
                    processed_data.freqs_array,
                    ratio_loss_difference[key] + vertical_offset,
                    label=key
            )
            # indicate max
            graph.axes.scatter(
                    x = x_at_y_max,
                    y = y_max + vertical_offset,
                    s = 50, # marker size 
                    marker = "*",
                    color = "red"
            )
            # shade +- RESONANCE_WIDTH around max
            graph.axes.axvspan(
                    xmin = x_at_y_max - RESONANCE_WIDTH/1000,
                    xmax = x_at_y_max + RESONANCE_WIDTH/1000,
                    alpha = 0.1
            )

                    
        median_step_location: np.floating = np.median(step_locations)
        step_lower_bound: np.floating = (
                median_step_location - 2*RESONANCE_WIDTH/1000
        )
        step_upper_bound: np.floating = (
                median_step_location + 2*RESONANCE_WIDTH/1000
        )
        mask = np.logical_and(
            processed_data.freqs_array > step_lower_bound,
            processed_data.freqs_array < step_upper_bound,
        )
        processed_data.mask = mask

        graph.show()
        graph.new_figure()



        #plotting.plot_step_loss_detection()
        #plotting.plot_cusum()

        try:
            plotting.plot_ratio_loss()
            *_, formatted_beam_energy, error = fitter.automagic_fit()
            print(formatted_beam_energy)
            plotting.plot_fits()
            graph.show()
            graph.new_figure()
            if writing_results:
                with open(path / "beam_energy.txt", "w") as f:
                    f.write(formatted_beam_energy)
            # graph.show()
            # graph.new_figure()
            # graph.show()
        except FittingError:
            print(f"Could not fit data from {path}")
        
def estimate_resonance_width(dates: list[str]) -> None:
    """
    loop through difference resonance width, look for best snr
    """

    data_paths = get_data_paths(dates)

    graph = StandaloneGraph()

    for path in data_paths:
        processed_data, resdep = create_data_objects(data_path=path)
        processed_data.calculate_ratio_loss()
        fitter = Fitter(
                resdep=resdep, processed_data=processed_data
        )
        plotting = Plotter(
                resdep=resdep, processed_data=processed_data, graph=graph
        )
        

        # sliding window difference based on resonance width
        RESONANCE_WIDTH: int = 800 # Hz
        RESONANCE_WIDTH_ARG: int = int(RESONANCE_WIDTH/resdep.sweep_step_size)
        ratio_loss_difference: dict[str, npt.NDArray] = {}
        step_locations: list[float] = []
        SNR: dict[str, np.floating] = {}
        print(f"------------ {path} ------------")
        for index, (key, loss) in enumerate(processed_data.ratio_loss.items()):
            # diff
            ratio_loss_difference[key] = (
                    loss[RESONANCE_WIDTH_ARG:]
                    - loss[:-RESONANCE_WIDTH_ARG]
            )
            # padding
            ratio_loss_difference[key] = np.insert(
                    arr = ratio_loss_difference[key],
                    obj = 0,
                    values = np.zeros(RESONANCE_WIDTH_ARG//2)
            ) / RESONANCE_WIDTH
            ratio_loss_difference[key] = np.append(
                arr = ratio_loss_difference[key],
                values = np.zeros(RESONANCE_WIDTH_ARG//2)
            )
            # find max of difference
            y_max = np.max(ratio_loss_difference[key])
            x_at_y_max = processed_data.freqs_array[
                    np.argmax(ratio_loss_difference[key])
            ]
            step_locations.append(x_at_y_max)
            # SNR
            mean = np.mean(ratio_loss_difference[key])
            std = np.std(ratio_loss_difference[key])
            signal_to_noise_ratio = abs(mean/std)
            SNR[key] = signal_to_noise_ratio
            # plot
            vertical_offset = index * 0.0005
            graph.axes.plot(
                    processed_data.freqs_array,
                    ratio_loss_difference[key] + vertical_offset,
                    label=key
            )
            # indicate max
            graph.axes.scatter(
                    x = x_at_y_max,
                    y = y_max + vertical_offset,
                    s = 50, # marker size 
                    marker = "*",
                    color = "red"
            )
            # shade +- RESONANCE_WIDTH around max
            graph.axes.axvspan(
                    xmin = x_at_y_max - RESONANCE_WIDTH/1000,
                    xmax = x_at_y_max + RESONANCE_WIDTH/1000,
                    alpha = 0.1
            )

                    
        for key, value in SNR.items():
            print(f"{key} SNR = {value}")
        graph.show()
        graph.new_figure()

def trend_with_RF_frequency(dates: list[str]) -> None:

    data_paths = get_data_paths(dates)
    print("got paths")

    RF_frequencies = np.zeros_like(data_paths, dtype=float)
    for index, path in enumerate(data_paths):
        with open(path / "metadata.json", "r") as f:
            metadata = json.load(f)
        f_rev = metadata["f_rev"]
        master_rf = f_rev * 360 * 1e-3  # MHz
        RF_frequencies[index] = master_rf

    print("got RF frequencies")

    timestamps, datetimes = get_timestamps(data_paths)
    npdatetimes = matplotlib.dates.date2num(datetimes)
    print("got timestamps")
    energies, errors = get_beam_energies(data_paths)
    errors_GeV = errors * 1e-6
    print("got energies")

    fig, axs = plt.subplots(2, 1, figsize=(6,6), layout="tight", sharex=True)
    cmap = plt.get_cmap("inferno")

    axs[0].errorbar(
            x=npdatetimes, 
            y=energies, 
            yerr=errors_GeV, 
            fmt='o',
            alpha=0.6,
            color=cmap(50)
    )
    # axs[0].plot_date(npdatetimes, energies, linestyle="--")
    axs[1].plot_date(
            npdatetimes, 
            RF_frequencies, 
            color=cmap(150),
            linestyle="None",
    )

    axs[0].set_ylabel("Beam energy (GeV)")
    axs[1].set_ylabel("Master RF (MHz)")
    axs[1].set_xlabel("datetime")

    fig.suptitle("Beam energy trend with master RF")

    # rotate timestamp strings 90 degrees
    for ax in axs:
        ax.tick_params("x", rotation=60)

    # prevent scientific notation axes
    for ax in axs:
        ax.ticklabel_format(useOffset=False, axis="y")

    response = input("Save figure? (y/n)\n")
    if response == "y":
        cwd = Path.cwd()
        filepath = cwd / "figures" / "trend_beam_energy_with_RF.png"
        plt.savefig(
                filepath,
                dpi=300,
                bbox_inches="tight",
                facecolor="white",
                transparent=False,
        )

    plt.show()

    response = input("Calculate momentum compaction factor? (y/n)\n")
    if response == "y":
        momentum_compaction_factor = calculate_momentum_compaction_factor(
                energies,
                RF_frequencies,
        )

def calculate_momentum_compaction_factor(
        energies: npt.NDArray,
        frequencies: npt.NDArray
        ) -> float:
    """
    Calculate alpha, the momentum compaction factor, the change in the electron 
    orbit as a function of energy.
    Its the gradient of the change in the energy over the change in the RF 
    cavity frequency (master)

    Parameters
    ----------
    energies: npt.NDArr
    """

    mean_energy: np.floating = energies.mean()
    mean_frequency: np.floating = frequencies.mean()

    residual_energy: npt.NDArray = energies - mean_energy
    residual_frequency: npt.NDArray = frequencies - mean_frequency

    change_in_energy = residual_energy / mean_energy
    change_in_frequency = residual_frequency / mean_frequency
    change_in_energy.sort()
    change_in_frequency.sort()

    popt: npt.NDArray = np.polyfit(
            x=change_in_energy,
            y=change_in_frequency,
            deg=1
    )
    momentum_compaction_factor = popt[0]
    vertical_offset = popt[1]
    print(f"popt={popt}")
    # -- calculate goodness of fit
    # residual sum of squares
    y_fit = momentum_compaction_factor * change_in_energy + vertical_offset
    ss_res = np.sum((change_in_frequency - y_fit) ** 2)
    # total sum of squares
    ss_tot = np.sum((change_in_frequency - np.mean(change_in_frequency)) ** 2)
    # r-squared
    r2 = 1 - (ss_res / ss_tot)

    # plot 
    fig, axs = plt.subplots(1, 1, figsize=(6,6), layout="tight")
    fig.suptitle("Momentum compaction factor")
    
    axs.scatter(change_in_energy, change_in_frequency, color="indigo")
    axs.set_xlabel(r"$\Delta E/E$")
    axs.set_ylabel(r"$\Delta f_\mathrm{rf}/f_\mathrm{rf}$")

    axs.plot(
            change_in_energy, 
            y_fit, 
            linestyle="--", 
            color="mediumpurple",
            label=r"$r^2$"+f" = {r2:0.2f}"
    )

    plt.legend()
    plt.show()


    return momentum_compaction_factor


if __name__ == "__main__":
    dates: list[str] = []
    for day in range(11,17+1,1):
        dates.append(f"2026-07-{day:02d}")
    trend_fit_quality(dates)
