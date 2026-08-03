#!/usr/bin/env python3
"""
Plot resdep data
"""

"""
██████╗ ██╗      ██████╗ ████████╗    ██████╗  █████╗ ████████╗ █████╗ 
██╔══██╗██║     ██╔═══██╗╚══██╔══╝    ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗
██████╔╝██║     ██║   ██║   ██║       ██║  ██║███████║   ██║   ███████║
██╔═══╝ ██║     ██║   ██║   ██║       ██║  ██║██╔══██║   ██║   ██╔══██║
██║     ███████╗╚██████╔╝   ██║       ██████╔╝██║  ██║   ██║   ██║  ██║
╚═╝     ╚══════╝ ╚═════╝    ╚═╝       ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
"""

from datetime import datetime
import json
from typing import Literal
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from cycler import cycler
import os
from pathlib import Path

# resdep modules
from resdep.epicsBPMs import SR_BPMs, MX3_BPMs, TBPMs
from resdep._plotting import Plotter, StandaloneGraph
from resdep._fitting import Fitter
from resdep.experiment import ResonantDepolarisation, ProcessedData

# --- consts
f_rev = 1.38799e3  # kHz
v_synch = 0.00847
g = 2.0023193043609236
a_g = (g - 2) / 2
m_e = 9.109383713928e-31  # kg
c = 299792458  # m/s
e = 1.602176634e-19  # C
mu: str = "\u03bc"

# --- import data

data_path = Path("Z:/usr/data/resdep")
data_path = data_path / "2026" / "2026-07-14" / "1328h"
print(f"folder={data_path.name}")
if not data_path.exists():
    raise FileNotFoundError("Incorrect path")

# metadata json
with open(data_path / "metadata.json", "r") as f:
    metadata = json.load(f)
print("---metadata---")
print(metadata)

# freqs txt
freqs: list[float] = []
with open(os.path.join(data_path, "freqs.txt"), "r") as f:
    for line in f.readlines():
        freqs.append(float(line) / 1e3)  # Hz -> kHz

set_freqs: list[float] = []
with open(os.path.join(data_path, "set_freqs.txt"), "r") as f:
    for line in f.readlines():
        set_freqs.append(float(line))  # kHz

# timestamps txt
timestamps_strings: list[str] = []
with open(data_path / "timestamps.txt", "r") as f:
    for line in f.readlines():
        timestamps_strings.append(line[:-1])
# convert to datetime
timestamps_datetimes: list[datetime] = [
    datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") for ts in timestamps_strings
]
# Create minutes axis
start_time = timestamps_datetimes[0]
minutes: list[float] = [
    (td - start_time).total_seconds() / 60 for td in timestamps_datetimes
]

# current txt
current: list[float] = []
with open(os.path.join(data_path, "current.txt"), "r") as f:
    for line in f.readlines():
        current.append(float(line))

# beam_losses adc window 1
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

# # ODB beam size and offset
# with open(os.path.join(data_path, "ODB_data.json"), "r") as f:
# 	ODB_data = json.load(f)

# Assign metadata to variables:
if "f_rev" in metadata.keys():
    f_rev = metadata["f_rev"]
tune = metadata["fractional tune"]
harmonic = metadata["harmonic"]
sweep_rate = metadata["sweep rate (Hz/s)"]
# calculate expected resonance frequency
res_freq: float = f_rev * (tune + harmonic)

# --- config classes
resdep = ResonantDepolarisation()
resdep.freqs = [freq * 1e3 for freq in freqs]
resdep.set_freqs = set_freqs
resdep.beam_loss_window_1 = beam_loss_window_1
resdep.beam_loss_window_2 = beam_loss_window_2
resdep.sweep_rate = sweep_rate
resdep.f_rev = f_rev
resdep.tune = tune
resdep.harmonic = harmonic
resdep.res_freq = res_freq

processed_data = ProcessedData(resdep=resdep)
processed_data.sectors_to_fit = [1, 3, 8, 14]
processed_data.calculate_ratio_loss()

graph = StandaloneGraph()
plotting = Plotter(
    resdep=resdep, processed_data=processed_data, graph=graph
)
fitter = Fitter(resdep=resdep, processed_data=processed_data)

# --- BPMs
def load_bpm_data(bpms: list[Literal["SR", "MX3", "TBPM"]]) -> None:  
    
    print("Loading BPM data...")

    global bpm_path
    bpm_path = data_path / "BPMs"
    if not bpm_path.exists():
        raise FileNotFoundError("No 'BPMs' save folder.")

    if "SR" in bpms:
        global sr_path, sr_bpms
        sr_path = bpm_path / "SR"
        if not sr_path.exists():
            raise FileNotFoundError("Can't find SR BPM data.")
        sr_bpms = SR_BPMs()
        sr_bpms.load_from_finished_experiment(path=sr_path)

    if "MX3" in bpms:
        global mx3_path, mx3_bpms
        mx3_path = bpm_path / "MX3"
        if not mx3_path.exists():
            raise FileNotFoundError("Can't find MX3 BPM data")
        mx3_bpms = MX3_BPMs()
        mx3_bpms.load_from_finished_experiment(path=mx3_path)
        # check keys are in the correct order ([1, 2, 5, 3, 4]):
        correct_bpm_order = ["1", "2", "5", "3", "4"]
        bpm_order = list(mx3_bpms.x_position.keys())
        if bpm_order != correct_bpm_order: 
            attr_names = ["x_position", "y_position", "intensity"]
            for name in attr_names:
                attr = getattr(mx3_bpms, name) 
                reordered_dict = {
                    bpm: attr[bpm] for bpm in correct_bpm_order
                }
                setattr(mx3_bpms, name, reordered_dict)

    if "TBPM" in bpms:
        global tbpm_path, tbpms
        tbpm_path = bpm_path / "TBPMs"
        if not tbpm_path.exists():
            raise FileNotFoundError("Can't find TBPM data.")
        tbpms = TBPMs()
        tbpms.load_from_finished_experiment(path=tbpm_path)
    
    print("Loaded!")

    return None
# -----------------------------------------------------------------------------
def plot_SR_BPMs_around_kicker() -> None:

    # Plot SR BPM 10 before and after kicker
    fig, axs = plt.subplots(2, 1, figsize=(5, 8), layout="tight")
    fig.suptitle("SR10/11 BPMs\nbefore and after kicker")

    colors = ["coral", "coral", "darkslateblue", "darkslateblue"]
    alphas = [0.2, 1, 1, 0.2]

    attributes = ["x_position", "y_position"]
    bpms = ["10:5", "10:6", "10:7", "11:1"]
    for bpm_index, bpm in enumerate(bpms):
        for attribute_index, attribute in enumerate(attributes):
            pos = np.array(getattr(sr_bpms, attribute)[bpm])
            pos = pos - np.mean(pos[:100])
            axs[attribute_index].plot(
                minutes,
                pos,
                label=bpm,
                color=colors[bpm_index],
                alpha=alphas[bpm_index],
            )

    axs[0].set_title("x_position change")
    axs[1].set_title("y_position change")
    for ax in [0, 1]:
        axs[ax].legend()
        axs[ax].set_xlabel("Time (minutes)")
        axs[ax].set_ylabel("nm")

    shade_kicker_off(axs)

    plt.savefig(
        sr_path / "kicker_before_and_after.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    # --- Angle
    yaw, pitch = sr_bpms.calculate_angles(loop_around=True)
    fig, axs = plt.subplots(2, 1, figsize=(5, 8), layout="tight")
    fig.suptitle("Angle through SR10/11 BPMs\nbefore and after kicker")

    colors = ["coral", "black", "darkslateblue"]
    alphas = [0.2, 1, 0.2]
    adjacent_bpms = ["10:5|10:6", "10:6|10:7", "10:7|11:1"]
    for bpms_index, bpms in enumerate(adjacent_bpms):
        # calculate change
        yaw_change = yaw[bpms] - np.mean(yaw[bpms][:100])
        pitch_change = pitch[bpms] - np.mean(pitch[bpms][:100])
        axs[0].plot(
            minutes,
            yaw_change,
            label=bpms,
            color=colors[bpms_index],
            alpha=alphas[bpms_index],
            linewidth=1,
        )
        axs[1].plot(
            minutes,
            pitch_change,
            label=bpms,
            color=colors[bpms_index],
            alpha=alphas[bpms_index],
            linewidth=1,
        )

    axs[0].set_title("change in yaw")
    axs[1].set_title("change in pitch")
    for ax in [0, 1]:
        axs[ax].legend()
        axs[ax].set_xlabel("Time (minutes)")
        axs[ax].set_ylabel(f"{mu}rad")

    shade_kicker_off(axs)

    plt.savefig(
        sr_path / "kicker_yaw_pitch.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    plt.show()
# -----------------------------------------------------------------------------
def plot_SR_BPMs_around_MX3_IVU() -> None:

    # --- Position
    fig, axs = plt.subplots(2, 1, figsize=(5, 8), layout="tight")
    fig.suptitle("SR03/04 BPMs\nbefore and after MX3 IVU")

    colors      = ["green", "green", "purple", "purple"]
    alphas      = [0.2, 1, 1, 0.2]
    attributes  = ["x_position", "y_position"]
    bpms        = ["3:6", "3:7", "4:1", "4:2"]
    for bpm_index, bpm in enumerate(bpms):
        for attribute_index, attribute in enumerate(attributes):
            pos = np.array(getattr(sr_bpms, attribute)[bpm])
            pos = pos - np.mean(pos[:100])
            axs[attribute_index].plot(
                minutes,
                pos,
                label=bpm,
                color=colors[bpm_index],
                alpha=alphas[bpm_index],
                linewidth=1,
            )

    axs[0].set_title("x_position change")
    axs[1].set_title("y_position change")
    for ax in [0, 1]:
        axs[ax].legend()
        axs[ax].set_xlabel("minutes")
        axs[ax].set_ylabel("nm")

    shade_kicker_off(axs)

    plt.savefig(
        sr_path / "MX3_IVU_before_and_after.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    # --- Angle
    yaw, pitch = sr_bpms.calculate_angles(loop_around=True)
    mx3_IVU_missteer: list[str] = []
    missteer: list[float] = [0, 0]

    print("---Max missteer (yaw, pitch) through MX3 IVU---")
    for bpms in ["3:6|3:7", "3:7|4:1", "4:1|4:2"]:
        for index, angle in enumerate([yaw, pitch]):
            angle_change = angle[bpms] - np.mean(angle[bpms][:100])
            angle_maxabs = np.max(np.abs(angle_change))
            angle_maxabs_index = np.argmax(np.abs(angle_change))
            angle_maxabs_sign = np.sign(angle_change[angle_maxabs_index])
            missteer[index] = np.copysign(angle_maxabs, angle_maxabs_sign)

        missteer_str = (
            f"Between SR BPMs {bpms}: yaw={missteer[0]:+0.3f} "
            + f"{mu}rad, pitch={missteer[1]:+0.3f} {mu}rad"
        )
        mx3_IVU_missteer.append(missteer_str)
        print(missteer_str)

    # save deviations .txt
    with open(sr_path / "mx3_IVU_misteer.txt", "w", encoding="utf-8") as f:
        for line in mx3_IVU_missteer:
            f.write(line + "\n")

    fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(5, 8), layout="tight")
    fig.suptitle("Angle through SR03/04 BPMs\nbefore and after MX3 IVU")

    colors = ["green", "black", "purple"]
    alphas = [0.2, 1, 0.2]

    for bpms_index, bpms in enumerate(["3:6|3:7", "3:7|4:1", "4:1|4:2"]):
        # calculate change
        yaw_change = yaw[bpms] - np.mean(yaw[bpms][:100])
        pitch_change = pitch[bpms] - np.mean(pitch[bpms][:100])
        axs[0].plot(
            minutes,
            yaw_change,
            label=bpms,
            color=colors[bpms_index],
            alpha=alphas[bpms_index],
            linewidth=1,
        )
        axs[1].plot(
            minutes,
            pitch_change,
            label=bpms,
            color=colors[bpms_index],
            alpha=alphas[bpms_index],
            linewidth=1,
        )

    axs[0].set_title("change in yaw")
    axs[1].set_title("change in pitch")
    for ax in axs:
        ax.legend()
        ax.set_xlabel("minutes")
        ax.set_ylabel(f"{mu}rad")

    shade_kicker_off(axs)

    plt.savefig(
        sr_path / "MX3_IVU_yaw_pitch.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    plt.show()
# -----------------------------------------------------------------------------
def plot_MX3_BPMs(fixed_limits: bool = False) -> None:

    # --- colour palette
    color = plt.cm.inferno(np.linspace(start=0, stop=1, num=6)) # type: ignore
    plt.rcParams["axes.prop_cycle"] = cycler("color", color)

    # --- max deviation in x,y on MX3
    mx3_deviations: list[str] = []
    deviation: list[float] = [0, 0]
    mx3_stddevs: list[str] = []
    stddev: list[float] = [0, 0]

    print("---Max deviations in x,y on MX3---")
    for bpm in mx3_bpms.x_position:
        for index, position in enumerate(["x_position", "y_position"]):
            pos = getattr(mx3_bpms, position)
            pos_array = np.array(pos[bpm])
            pos_change = pos_array - np.mean(pos_array[:100])
            pos_maxabs = np.max(np.abs(pos_change))
            pos_maxabs_index = np.argmax(np.abs(pos_change))
            pos_maxabs_sign = np.sign(pos_change[pos_maxabs_index])
            deviation[index] = np.copysign(pos_maxabs, pos_maxabs_sign)
            stddev[index] = float(np.std(pos_array))

        deviation_str = (
            f"MX3 BPM {bpm}: x={deviation[0]:+0.2f} {mu}m," 
            + f"y={deviation[1]:+0.2f} {mu}m"
        )
        stddev_str = (
            f"MX3 BPM {bpm}: x={stddev[0]:+0.2f} {mu}m," 
            + f"y={stddev[1]:+0.2f} {mu}m"
        )
        mx3_deviations.append(deviation_str)
        mx3_stddevs.append(stddev_str)
        print(deviation_str)
        print(stddev_str)

    # save deviations .txt
    with open(mx3_path / "max_devations.txt", "w", encoding="utf-8") as f:
        for line in mx3_deviations:
            f.write(line + "\n")
    with open(mx3_path / "stddevs.txt", "w", encoding="utf-8") as f:
        for line in mx3_stddevs:
            f.write(line + "\n")

    mx3_intensity_changes: list[str] = []
    print("---Intensity change (std.dev/mean (%)) on MX3---")
    for bpm, intensity in mx3_bpms.intensity.items():
        intensity = np.array(intensity)  # nA
        intensity_mean = np.mean(intensity)  # nA
        intensity_stddev = np.std(intensity)  # nA
        intensity_change = 100 * intensity_stddev / intensity_mean  # %
        intensity_change_str = f"MX3 BPM {bpm}: {intensity_change:+0.2f} %"
        print(intensity_change_str)
        mx3_intensity_changes.append(intensity_change_str)

    # save deviations .txt
    with open(mx3_path / "intensity_changes.txt", "w", encoding="utf-8") as f:
        for line in mx3_intensity_changes:
            f.write(line + "\n")

    # # absolute intensity change
    # print("---Max deviations in INTENSITY on MX3 (% of mean)---")
    # for bpm, intensity in mx3_bpms.intensity.items():
    # 	intensity_array			= np.array(intensity)
    # 	intensity_maxabs 		= np.max(np.abs(intensity))
    # 	intensity_deviation 	= 100 - 100 * np.mean(intensity_array[:100]) / intensity_maxabs
    # 	intensity_deviation_str = f"MX3 BPM {bpm}: {intensity_deviation:+0.2f} %"
    # 	print(intensity_deviation_str)

    # --- plots x_pos, y_pos, intensity
    fig, axs = plt.subplots(3, 1, figsize=(5, 10), layout="constrained")
    fig.suptitle("MX3 BPMs")

    attributes = ["x_position", "y_position", "intensity"]
    for index, attribute in enumerate(attributes):
        attr = getattr(mx3_bpms, attribute)
        axs[index].set_title(f"{attribute} change")

        for bpm, value in attr.items():
            value_array = np.array(value)
            value_offset = value_array - np.mean(value_array[:100])

            axs[index].plot(
                minutes, value_offset, linewidth=1, linestyle="-", label=bpm
            )
            axs[index].set_ylabel(r"$\mu$m")
            axs[index].legend(ncols=2, fontsize=9, handlelength=1, loc="upper right")

            # create inset with just angle through IVU
            if bpm == "4":
                axs_inset = inset_axes(
                    axs[index], width="30%", height="30%", loc="upper center"
                )
                axs_inset.plot(
                    minutes, value_offset, color=color[4], label=bpm, linewidth=1
                )
                # set ylim
                if fixed_limits and not attribute == "intensity":
                    axs_inset.set_ylim(-0.15, 0.15)
                # remove x_ticks
                axs_inset.tick_params(
                    axis="x", which="both", bottom=False, labelbottom=False
                )
                shade_kicker_off(axs_inset, label=False)
        # adjusted ylims to fit in
        if fixed_limits:
            LOWER_LIMIT = -2.5 # um
            UPPER_LIMIT = 2.5 # um
            axs[0].set_ylim(LOWER_LIMIT, UPPER_LIMIT) # x
            axs[1].set_ylim(LOWER_LIMIT, UPPER_LIMIT) # y
            axs[2].set_ylim(-1500, 1500) # I
        else:
            ylims = axs[index].get_ylim()
            axs[index].set_ylim(ylims[0], ylims[1] * 1.3)

    shade_kicker_off(axs)

    # Third plot (intensity)
    axs[2].set_ylabel(r"nA")
    axs[2].set_xlabel(r"Time (minutes)")

    if fixed_limits:
        filename = mx3_path / "MX3_PDS_positions_fixed.png"
    else:
        filename = mx3_path / "MX3_PDS_positions.png"

    plt.savefig(
        filename,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    # --- angle
    yaw, pitch = mx3_bpms.calculate_angles()

    fig, axs = plt.subplots(
        nrows=2, ncols=1, figsize=(5, 8), layout="compressed"
    )
    fig.suptitle("Steer through MX3 PDS")

    inset: bool = False

    for index, angle in enumerate([yaw, pitch]):
        for bpms_index, bpms in enumerate(angle):
            # calculate change
            angle_change = angle[bpms] - np.mean(angle[bpms][:100])
            axs[index].plot(
                minutes,
                angle_change,
                color=color[bpms_index + 1],
                alpha=0.9,
                label=bpms,
                linewidth=1,
            )
            if inset and bpms == "3|4":
                axs_inset = inset_axes(
                    axs[index], width="30%", height="30%", loc="upper center"
                )
                axs_inset.plot(
                    minutes, angle_change, color=color[4], 
                    label=bpms, linewidth=1
                )
                # remove x_ticks
                axs_inset.tick_params(
                    axis="x", which="both", bottom=False, labelbottom=False
                )
                shade_kicker_off(axs_inset, label=False)

    shade_kicker_off(axs)

    axs[0].set_title("change in yaw")
    axs[1].set_title("change in pitch")
    for ax in axs:
        ax.legend(ncols=2, fontsize=9, handlelength=1, loc="upper right")
        ax.set_xlabel("Time (minutes)")
        ax.set_ylabel(f"{mu}rad")
        if fixed_limits:
            LOWER_LIMIT = -1.5 # urad
            UPPER_LIMIT = 1.5 # urad
            ax.set_ylim(LOWER_LIMIT, UPPER_LIMIT)

    shade_kicker_off(axs)

    if fixed_limits:
        filename = mx3_path / "MX3_PDS_yaw_pitch_fixed.png"
    else:
        filename = mx3_path / "MX3_PDS_yaw_pitch.png"
    plt.savefig(
        filename,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    plt.show()

    return None
# -----------------------------------------------------------------------------
def plot_MX3_at_sample() -> None:

    # --- just BPM 4 (goni / sample)
    bpm = "4"

    fig, axs = plt.subplots(2, 1, figsize=(4, 8), layout="tight")
    fig.suptitle("MX3 BPM at goni/sample\n(BPM4)")

    for index, attribute in enumerate(["x_position", "y_position"]):
        data = getattr(mx3_bpms, attribute)[bpm]
        data = np.array(data) - np.mean(data[:100])
        axs[index].plot(minutes, data, linewidth=1, color="purple")
        axs[index].set_xlabel("Time (minutes)")
        axs[index].set_ylabel(r"$\mu$m")
        axs[index].set_title(f"{attribute} change")

    shade_kicker_off(axs)

    plt.savefig(
        bpm_path / "MX3" / "at_goni_sample.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )

    plt.show()

    return None
# -----------------------------------------------------------------------------
def plot_all_BPMs() -> None:
    index = 0
    attribute = None

    BPM_classes = [sr_bpms, tbpms, mx3_bpms]
    BPM_groups = ["SR", "TBPMs", "MX3"]

    for BPMs, group_name in zip(BPM_classes, BPM_groups):
        fig, axs = plt.subplots(3, 1, figsize=(4, 10), layout="tight")
        fig.suptitle(f"{group_name} BPMs")

        try:
            for index, attribute in enumerate(
                ["x_position", "y_position", "intensity"]
            ):
                if hasattr(BPMs, attribute):
                    attr = getattr(BPMs, attribute)
                    axs[index].set_title(f"{attribute} change")

                    for key, value in attr.items():
                        # norm_value = np.array(value)/np.max(value)
                        value_array = np.array(value)
                        value_offset = value_array - np.mean(value_array[:100])
                        # Convert SR BPMs from nm --> um
                        if group_name == "SR" and attribute in [
                            "x_position",
                            "y_position",
                        ]:
                            value_offset *= 1e-3

                        axs[index].plot(
                            minutes,
                            value_offset,
                            linewidth=0.5,
                            linestyle="-",
                            label=key,
                        )
                        axs[index].set_ylabel(r"$\mu$m")
                        if not group_name == "SR":
                            axs[index].legend()

            # Third plot (intensity)
            axs[index].set_ylabel(r"a.u.")
            axs[index].set_xlabel(r"Time (minutes)")
            axs[index].tick_params("x", rotation=90)

        except NameError:
            continue

        if group_name == "MX3" and attribute == "intensity":
            axs[index].set_ylabel(r"nA")

    plt.show()

    return None
# -----------------------------------------------------------------------------
def shade_kicker_off(axes, label: bool = True) -> None:
    """
    Shade kicker off region for each plot
    """
    # if only one axis passed, cast to list of length 1
    if not hasattr(axes, "__len__"):
        axes = [axes]
    for axs in axes:
        axs.axvspan(
            xmin=0, xmax=minutes[99], ymin=0, 
            ymax=1, color="black", alpha=0.1
        )
        if label:
            axs.text(
                x=0,
                y=1.05,
                s="kicker off",
                horizontalalignment="left",
                verticalalignment="center",
                transform=axs.transAxes,
                color="black",
                alpha=0.3,
            )

if __name__ == "__main__":
    # load_bpm_data(bpms=["SR", "MX3"])
    # plot_SR_BPMs_around_kicker()
    # plot_SR_BPMs_around_MX3_IVU()
    # plot_MX3_BPMs(fixed_limits=True)

    # plotting.plot_ratio_loss()
    # graph.show()
    # plotting.plot_step_loss_detection()
    # fitter.fit_error_functions()
    # plotting.plot_fits()

    plotting.plot_ratio_loss()
    *_, formatted_beam_energy, _ = fitter.automagic_fit()
    plotting.plot_fits()
    print(formatted_beam_energy)
    # graph.show(block=False)
    # plotting.plot_step_loss_detection()
    # graph.show(block=True)
    # fitter.automagic_fit()
    # print(processed_data.fitted_beam_energy_str)
    # plotting.plot_ratio_loss()
    # plotting.plot_fits()
    # graph.show()
    
    # plotting.plot_cusum()

    # plotting.plot_totvar_denoise(eigval=1, mu=0.5, fused_lasso=True)

    # plotting.plot_median_filter()

    graph.show()
