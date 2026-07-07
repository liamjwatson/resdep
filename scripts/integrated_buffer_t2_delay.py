from typing import Union, Literal
import matplotlib.pyplot as plt
import time
import epics
import numpy as np
import numpy.typing as npt

from resdep.epicsBLMs import BLMs
from resdep.experiment import ResonantDepolarisation

global blm, SUM_DEC
SUM_DEC = 86
# load blm PVs
blm = BLMs()
blm.get_loss_PVs()
blm.get_t2_trigger_delays()
blm.get_adc_counter_mask_PVs()
blm.get_decimation()


# ---------------------------------------------------------------------------------------
def get_int_buff_loss() -> dict[str, npt.NDArray[np.floating]]:
    int_buff_loss: dict[str, npt.NDArray[np.floating]] = {}
    for key, PV in blm.integrated_buffer_loss_PV.items():
        int_buff_loss[key] = PV.get()
        time.sleep(0.1)

    return int_buff_loss
# ---------------------------------------------------------------------------------------
def shift_buffer_by_t2_delay(int_buff_loss) -> dict[str, npt.NDArray[np.floating]]:

    shifted_int_buff_loss: dict[str, npt.NDArray[np.floating]] = {}
    for key, value in int_buff_loss.items():
        t2_delay = blm.init_t2_trigger_delays[key[:-1]]
        if t2_delay is not None:
            t2_delay = int(t2_delay) % SUM_DEC
        else:
            raise ValueError(f"T2 delay for sector {key} returned None.")
        shifted_int_buff_loss[key] = np.concatenate((value[t2_delay:], value[:t2_delay]))

    return shifted_int_buff_loss
# ---------------------------------------------------------------------------------------
def plot_integrated_loss(int_buff_loss: dict[str, npt.NDArray[np.floating]], calculated_adc_counter_windows = None, block: bool = True) -> None:
    """
    Plots integrated buffer loss (7x4 table of plots)

    Two set of rows (A: straight, and B: bend), first sector 1->7, then 8->14
    """
    fig, axs = plt.subplots(nrows=4, ncols=7, figsize=(14,8), layout="compressed")
    for index, (key, loss) in enumerate(int_buff_loss.items()):
        # normalise
        loss = loss/np.max(loss)
        # flip and scale
        loss = -1 * loss + 1
        # straight (A) = row 1, bend (B) = row 2
        if key[-1] == "A":
            row_index = 0
        elif key[-1] == "B":
            row_index = 1
        else:
            row_index = 0
            raise KeyError

        # plot first 7 sectors in top two rows
        if int(key[:-1]) <=7:
            column_index = index//2
            axs[row_index, column_index].plot(loss)
        else:
            row_index += 2
            column_index = (index-14)//2
            axs[row_index, column_index].plot(loss)
        axs[row_index, column_index].set_title(key)
        if calculated_adc_counter_windows:
            start = calculated_adc_counter_windows[0]
            end = calculated_adc_counter_windows[0] + calculated_adc_counter_windows[1]
            axs[row_index, column_index].fill_between(x=[start, end], y1=0, y2=1, color="purple", alpha=0.2)
            start = calculated_adc_counter_windows[2]
            end = calculated_adc_counter_windows[2] + calculated_adc_counter_windows[3]
            axs[row_index, column_index].fill_between(x=[start, end], y1=0, y2=1, color="yellow", alpha=0.2)

        # --- Find middle of empty buckets
        threshold = 0.8 * np.max(loss)
        args_under_threshold = np.flatnonzero(loss < threshold)
        # Account for empty buckets wraping around T0
        if any(args_under_threshold < 5) and any(args_under_threshold > SUM_DEC - 5):
            difference_in_args = args_under_threshold[1:] - args_under_threshold[:-1]
            jump_in_args = np.argmax(difference_in_args)
            # undo wrap around T0
            args_under_threshold[:jump_in_args+1] += SUM_DEC
        middle_empty_bucket_arg = int(np.mean(args_under_threshold)) % SUM_DEC
        if key == "1A":
            print(f"args_under_threshold={args_under_threshold}")
            print(f"middle_empty_bucket_arg={middle_empty_bucket_arg}")
        # plot line at middle of empty buckets
        axs[row_index, column_index].axvline(x=middle_empty_bucket_arg, ymin=0, ymax=0.75, color="red", alpha=0.7)

    plt.show(block=block)

    return None
# ---------------------------------------------------------------------------------------
def get_FPM(direction: Literal["x", "y"]):
        if direction == "x":
            affix = 1
        else: # y
            affix = 2
        FPM_pv 							= epics.pv.get_pv(f"SR00BBB01FPM0{affix}:FILL_PATTERN_ABS_WAVEFORM_MONITOR", connect=True)
        bucket_shift_pv 				= epics.pv.get_pv(f"SR00BBB01FPM0{affix}:BUCKET_SHIFT_SP", connect=True)
        bucket_shift: Union[int, None]	= bucket_shift_pv.get() # int
        FPM_shifted				 	 	= FPM_pv.get()
        time.sleep(0.5)

        # calculate original FPM (unshifted).
        FPM_unshifted: npt.NDArray[np.floating]
        if bucket_shift is not None and FPM_shifted is not None:
            FPM_unshifted = np.concatenate((FPM_shifted[bucket_shift:], FPM_shifted[:bucket_shift]))
        else:
            raise TypeError("BbB FPM PVs returned None. Depolarised bunch calculations failed.")

        return FPM_shifted, FPM_unshifted
# ---------------------------------------------------------------------------------------
def get_SRAM_waveforms() -> tuple[npt.NDArray[np.floating], ...]:
    SRAM_x_pv = epics.pv.get_pv("IGPF:X:SRAM:MEAN", connect=True, timeout=1)
    SRAM_y_pv = epics.pv.get_pv("IGPF:Y:SRAM:MEAN", connect=True, timeout=1)

    waveforms = [np.array([]), np.array([])]

    for index, pv in enumerate([SRAM_x_pv, SRAM_y_pv]):
        if not pv.connected:
            raise ConnectionRefusedError
        waveform = pv.get(timeout=10)
        if waveform is not None:
            # shift min to 0 (no negatives)
            waveform += -np.min(waveform)
            # normalise
            waveform *= 1/np.max(waveform)
            waveforms[index] = waveform

    SRAM_x, SRAM_y = waveforms

    # print(f"SRAM_x={SRAM_x}")
    # print(f"SRAM_y={SRAM_y}")

    return SRAM_x, SRAM_y
# ---------------------------------------------------------------------------------------
def plot_FPM(FPM_data, direction:str,  depolarised_bunches = None, block: bool = True):

    if not isinstance(direction, str):
        raise TypeError("direction should be str")

    fig, axs = plt.subplots(figsize=(14,8), layout="compressed")

    axs.plot(FPM_data)

    # threshold
    # |
    # |
    # V
    # This is all from _timeAlignment
    boundary: int = len(FPM_data)
    threshold = 0.4 * np.max(FPM_data)
    args_under_threshold = np.flatnonzero(FPM_data < threshold)
    # Account for empty buckets wraping around T0
    if any(args_under_threshold < 5) and any(args_under_threshold > boundary - 5):
        difference_in_args = args_under_threshold[1:] - args_under_threshold[:-1]
        jump_in_args = np.argmax(difference_in_args)
        # undo wrap around T0
        args_under_threshold[:jump_in_args+1] += boundary
    middle_empty_bucket_arg = int(np.mean(args_under_threshold)) % boundary

    axs.axhline(y=threshold, xmin=0, xmax=1, color="violet", linestyle="--")
    axs.axvline(x=middle_empty_bucket_arg, ymin=0, ymax=0.75, color="red", alpha=0.7)

    axs.set_title("FPM " + direction)

    print(f"FPM middle empty bucket = {middle_empty_bucket_arg}")

    if depolarised_bunches:
        # separate start and stop
        separator_index = depolarised_bunches.find(":")
        start = int(depolarised_bunches[0:separator_index])
        end = int(depolarised_bunches[separator_index+1:])
        if start > end:
            axs.fill_between(x=[start, 360], y1=0, y2=1, color="purple", alpha=0.2)
            axs.fill_between(x=[0, end], y1=0, y2=1, color="purple", alpha=0.2)
            axs.fill_between(x=[end, start], y1=0, y2=1, color="yellow", alpha=0.2)
            # Calculate area under each window
            window_1_area = np.sum(FPM_data[start:]) + np.sum(FPM_data[0:end+1])
            window_2_area = np.sum(FPM_data[end:start]) 
            print(f"window 1 area={window_1_area}, window_2_area={window_2_area}")
        else:
            axs.fill_between(x=[start, end], y1=0, y2=1, color="purple", alpha=0.2)
            axs.fill_between(x=[end, 360], y1=0, y2=1, color="yellow", alpha=0.2)
            axs.fill_between(x=[0, start], y1=0, y2=1, color="yellow", alpha=0.2)
            # Calculate area under each window
            window_1_area = np.sum(FPM_data[start:end+1])
            window_2_area = np.sum(FPM_data[end:]) + np.sum(FPM_data[0:start+1])
            print(f"window 1 area={window_1_area}, window_2_area={window_2_area}")

    plt.show(block=block)

    return None
# ---------------------------------------------------------------------------------------
def main() -> None:
    # do stuff
    int_buff_loss = get_int_buff_loss()
    # plot_integrated_loss(int_buff_loss)

    # FPM_x_shifted, FPM_x_unshifted = get_FPM(direction="x")
    # FPM_y_shifted, FPM_y_unshifted = get_FPM(direction="y")
    # plot_FPM(FPM_x_shifted)
    # plot_FPM(FPM_y_shifted)

    SRAM_x, SRAM_y = get_SRAM_waveforms()
    # plot_FPM(SRAM_x)
    # plot_FPM(SRAM_y)

    resdep = ResonantDepolarisation()
    resdep.blm = blm
    resdep.calculate_adc_counter_windows(sector=4)
    depolarised_bunches = resdep.set_drive_pattern
    calculated_adc_counter_windows = [resdep.set_adc_counter_offset_1, resdep.set_adc_counter_window_1,
        resdep.set_adc_counter_offset_2, resdep.set_adc_counter_window_2]
    
    print(f"depolarised bunches={depolarised_bunches}")
    print(f"calculated adc counter windows={calculated_adc_counter_windows}")

    shifted_int_buff_loss = shift_buffer_by_t2_delay(int_buff_loss)
    plot_integrated_loss(shifted_int_buff_loss, calculated_adc_counter_windows, block=False)
    plot_FPM(SRAM_x, "X", depolarised_bunches, block=False)
    plot_FPM(SRAM_y, "Y", depolarised_bunches)

# ---------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
