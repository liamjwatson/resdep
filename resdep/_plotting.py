"""                                                              
Class mixins (not general) for resdepGUI related to plotting to the matplotlib canvas in the GUI.

ONLY for use (import) in resdepGUI

@Author Liam Watson
"""
"""
██████╗ ██╗      ██████╗ ████████╗████████╗██╗███╗   ██╗ ██████╗ 
██╔══██╗██║     ██╔═══██╗╚══██╔══╝╚══██╔══╝██║████╗  ██║██╔════╝ 
██████╔╝██║     ██║   ██║   ██║      ██║   ██║██╔██╗ ██║██║  ███╗
██╔═══╝ ██║     ██║   ██║   ██║      ██║   ██║██║╚██╗██║██║   ██║
██║     ███████╗╚██████╔╝   ██║      ██║   ██║██║ ╚████║╚██████╔╝
╚═╝     ╚══════╝ ╚═════╝    ╚═╝      ╚═╝   ╚═╝╚═╝  ╚═══╝ ╚═════╝ 
"""

from typing import TYPE_CHECKING, Union, Callable
import builtins
import numpy as np
import numpy.typing as npt
import logging, traceback
from functools import partial

from PySide6.QtCore import QSize

# matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.lines import Line2D

# automagic fit testing
from scipy.ndimage import gaussian_filter1d
from scipy.special import erf

# resdep
from resdep._calculations import energy_calc, freq_calc
if TYPE_CHECKING:
    from resdep.experiment import ResonantDepolarisation, ProcessedData
    from resdep._fitting import FittingClass
    

class GUIGraph(FigureCanvasQTAgg):
    """
    Spawn canvas instance object to add and modify in GUI
    """
    def __init__(self, parent=None):

        # Create the figure and figure canvas
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.canvas = self.figure.canvas

        super().__init__(self.figure) 
        self.setParent(parent)

    # fixed size
    def sizeHint(self):
        return QSize(700, 600)

    def minimumSizeHint(self):
        return QSize(700, 600)
    
class StandaloneGraph():
    """
    Spawn an interactive graph object to plot to manually. \\
    Defines canvas correctly so that draw.idle() can be effective overrided.
    """
    def __init__(self,):

        # Create the figure and figure canvas
        self.figure, self.axes = plt.subplots(figsize=(7,6), layout="constrained")
        self.canvas = self.figure.canvas


# ----------------------------------------------------------------------------------------------------------------------------------------------------

class PlottingClass():
    def __init__(self, resdep: "ResonantDepolarisation", processed_data: "ProcessedData", graph: Union[GUIGraph, StandaloneGraph]):
        # Required
        self.resdep         = resdep
        self.processed_data = processed_data
        self.graph          = graph
        # defaults
        self.mask: Union[npt.NDArray[np.bool_], "builtins.ellipsis"] = ...
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def plot_ratio_loss(self, ):
        """
        Takes the ratio of the beam loss windows between the two ADC windows and plots the result. \\
        Data is smoothed by a gaussian function with a sigma defined on the GUI, or by standard binning (200 points).

        ## First requires (from `resdep.experiment`)
        1. Instance :class:`ProcessedData`
        2. run member function :func:`ProcessedData().calculate_ratio_loss`
        """
        try:
            for sector in self.processed_data.sectors_to_fit:
                key = f"{sector}B"
                x = self.processed_data.freqs_array
                y = self.processed_data.ratio_loss[key]
                # plot
                vertical_offset = 0.01 * int(sector)
                self.graph.axes.plot(x, y + vertical_offset, label=f"{sector}B")

            self.graph.axes.legend(loc='center right', ncol=1, reverse=True) # bbox_to_anchor=(0.5, -0.3)
            self.graph.figure.suptitle("Ratio beam loss")
            self.graph.axes.set_xlabel("frequency (kHz)")

            # Create energy top axis
            self.second_axis = self.graph.axes.secondary_xaxis("top", functions=(self.energy_secodary_axis()))
            self.second_axis.set_xlabel('Energy (GeV)')

            # prevent scientific notation axes
            self.graph.axes.ticklabel_format(useOffset=False)
            self.second_axis.ticklabel_format(useOffset=False)

            self.graph.canvas.draw_idle()

        except Exception:
            logging.error(traceback.format_exc())
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def calculate_fitting_mask(self) -> npt.NDArray[np.bool_]:
        """
        Grabs the current limits of the interactive plot (including when it is zoomed in) and calculates the frequency range displayed. \\
        This is then used as a mask to fit error functions in `fit_error_functions()`

        Returns
        -------
        mask: list[bool]
            Binary mask for the frequency range shown in the interactive plot
        """
        self.xlims: tuple[float, float] = self.graph.axes.get_xlim() # tuple[lower_bound, upper_bound]
        self.ylims: tuple[float, float] = self.graph.axes.get_ylim()
        mask = np.logical_and(self.processed_data.freqs_array > self.xlims[0], self.processed_data.freqs_array < self.xlims[1])

        # pass to processed_data
        self.processed_data.mask = mask

        return mask
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def plot_fits(self, ) -> None:
        """
        Plots the cumulative distribution function fit, intended on-top of the existing data \\
        Shades two standard deviations around the mean

        ## First requires 
        using :class:`FittingClass` (from :mod:`resdep._fitting`)
        1. :meth: `fit_error_functions` or :meth:`automagic_fit` 
        2. :meth:`calculate_fitted_energy_stats`
        """
        y_model     = self.processed_data.y_model
        E0_mean     = self.processed_data.E0_mean
        E0_stddev   = self.processed_data.E0_stddev

        if len(y_model) == 0:
            raise KeyError("No fit data to plot. Make sure you have called Fitting().fit_error_functions().")

        for key, fit in y_model.items():
            sector = key.replace("A", "")
            sector = sector.replace("B", "")
            # plot fit
            vertical_offset = 0.01 * int(sector)
            self.graph.axes.plot(self.processed_data.freqs_array[self.processed_data.mask], fit + vertical_offset, linestyle='--', color="red")
            # plot baseline
            self.graph.axes.axhline(y=fit[0] + vertical_offset, xmin=0, xmax=1, alpha=0.1, linestyle="--", color="black")

        # shade 2*std.dev region on plot
        if E0_mean and E0_stddev:
            self.graph.axes.axvspan(
                freq_calc(energy=float(E0_mean-E0_stddev), f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic),
                freq_calc(energy=float(E0_mean+E0_stddev), f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic),
                alpha=0.1,
                color="black"
            )

        # reset the plot limits
        try:
            self.graph.axes.set_xlim(self.xlims)
            self.graph.axes.set_ylim(self.ylims)
        except AttributeError: # if xlims and ylims aren't defined, do nothing (continue)
            pass

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def plot_expected_resonances(self, ) -> None:
        """
        Plots the expected resoanaces around the main (spin tune resonance). \\
        This includes synchrotron sidebands and betatron resonances. \\
        Updates dynamically on Qt GUI settings pane changes.
        """
    
        # --- resonance of competing tunes (betatron, synchrotron)
        # plot these resonances around the expected depolarisation resonance
        synchrotron_sidebands = [self.resdep.res_freq + i*(self.resdep.f_rev * self.resdep.v_synch) for i in [-3, -2, -1, 1, 2, 3]]

        for h in range(0,30,1):
            v_x_resonance = self.resdep.f_rev * (self.resdep.v_x + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
            v_y_resonance = self.resdep.f_rev * (self.resdep.v_y + h) # 300 Hz
            v_x_mirror_resonance = self.resdep.f_rev * ((1-self.resdep.v_x) + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
            v_y_mirror_resonance = self.resdep.f_rev * ((1-self.resdep.v_y) + h) # 300 Hz
            self.graph.axes.axvline(x=v_x_resonance, ymin=0, ymax=0.7, color="blue", linestyle="-")
            self.graph.axes.axvline(x=v_y_resonance, ymin=0, ymax=0.7, color="green", linestyle="-")
            self.graph.axes.axvline(x=v_x_mirror_resonance, ymin=0, ymax=0.7, color="blue", alpha=0.5, linestyle="-.")
            self.graph.axes.axvline(x=v_y_mirror_resonance, ymin=0, ymax=0.7, color="green", alpha=0.5, linestyle="-.")

        self.graph.axes.axvline(x=self.resdep.res_freq, ymin=0, ymax=1, color="red", linewidth=2)

        for sideband in synchrotron_sidebands:
            self.graph.axes.axvline(x=sideband, ymin=0, ymax=0.4, color="black", alpha=0.5, linestyle="dotted")

        self.graph.axes.text(x=self.resdep.res_freq, y=0.95, s=r"$\nu_\mathrm{s}$ = " + f"{self.resdep.res_freq:.0f} Hz  ", color="red", horizontalalignment="right")
        self.graph.figure.suptitle("Expected resonances within the scan range")
        self.graph.axes.set_xlabel("frequency (kHz)")
        self.graph.axes.set_xlim(self.resdep.sweep_limits[0], self.resdep.sweep_limits[-1])
        self.graph.axes.set_yticks([])
        legend_elements = [
            Line2D([0], [0], color='red', linewidth=2, label=r"$\nu_\mathrm{s}$"),
            Line2D([0], [0], color='blue', linewidth=1, label=r"$\nu_x$"),
            Line2D([0], [0], color='green', linewidth=1, label=r"$\nu_y$"),
            Line2D([0], [0], color='black', linewidth=1, label=r"$\nu_\mathrm{synch}$", linestyle="dotted", alpha=0.5),
            Line2D([0], [0], color='blue', linewidth=1, label=r"mirror $\nu_x$", alpha=0.5, linestyle="-."),
            Line2D([0], [0], color='green', linewidth=1, label=r"mirror $\nu_y$", alpha=0.5, linestyle="-."),
        ]                         
        self.graph.axes.legend(handles=legend_elements, ncols=2)

        self.second_axis = self.graph.axes.secondary_xaxis("top", functions=(self.energy_secodary_axis()))
        self.second_axis.set_xlabel('Energy (GeV)')

        # prevent scientific notation axes
        self.graph.axes.ticklabel_format(useOffset=False)
        self.second_axis.ticklabel_format(useOffset=False)

        self.graph.canvas.draw_idle()
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def energy_secodary_axis(self,) -> tuple[Callable, Callable]:

        return (
            partial(energy_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic), 
            partial(freq_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic)
        )
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def plot_step_loss_detection(self, ) -> None:

        peaks = []

        for sector in self.processed_data.sectors_to_fit:
            key = f"{sector}B"
            x = self.processed_data.freqs_array
            y = self.processed_data.ratio_loss[key]
            # set 0 
            y += -np.mean(y[:100]) 
            # normalise
            y *= 1/np.max(y)
            # self.graph.axes.plot(x, y + 0.3 * float(sector), label=f"{sector}B")
            # smooth into oblivion
            y = gaussian_filter1d(input=y, sigma=1000*10//5) # n * 10 datapoints/sec / 5Hz/s scan
            # differentiate
            y = np.gradient(y)
            # peaks
            peak = x[np.argmax(y)]
            peaks.append(peak)
            print(f"peak={peak}")

            self.graph.axes.axvline(peak, 0, 1, color="red")


            # # --- coarse grid search
            # means = np.linspace(np.min(x), np.max(x), 200)
            # errors = []

            # for mean in means:
            #     y_predicted = self.erf_model(x, mean, sigma=1)
            #     errors.append(np.sum((y-y_predicted)**2))
            
            # mean_with_lowest_error = means[np.argmin(errors)]
            # print(f"{key}: lowest error mean={mean_with_lowest_error}")

            # y = savgol_filter(y, window_length=300, polyorder=1, deriv=1, )
            self.graph.axes.plot(x, y)# + 0.1 * float(sector), label=f"{sector}B")

        # data points?
        n_data_points = len(x) # type:ignore
        freq_range = x[-1] - x[0] # type:ignore
        data_point_spacing = np.round(1e3*freq_range/n_data_points,1) # Hz
        print(f"data point spacing = {data_point_spacing} Hz")

        # peak stats
        peaks_mean = np.mean(peaks)
        peaks_var = np.var(peaks)
        peaks_median = np.median(peaks)
        peaks_stddev = np.std(peaks)
        energy_mean = energy_calc(peaks_mean, self.resdep.f_rev, self.resdep.harmonic)
        energy_median = energy_calc(peaks_median, self.resdep.f_rev, self.resdep.harmonic)
        print(f"--- PEAKS ---")
        print(f"mean \t\t= {peaks_mean}")
        print(f"variance \t= {peaks_var}")
        print(f"stddev \t\t= {peaks_stddev}")
        print(f"median \t\t= {peaks_median}")
        print(f"mean energy \t= {energy_mean}")
        print(f"median energy \t= {energy_median}")
        print("-----------------------")
        
        lower_bound = peaks_mean - 1*peaks_stddev
        upper_bound = peaks_mean + 1*peaks_stddev

        for index, peak in enumerate(peaks):    
            if peak > lower_bound and peak < upper_bound:
                print(f"Peak {index} is within one sigma.")
            else:
                print(f"Peak {index} is an outlier!")

        # Create energy top axis
        self.second_axis = self.graph.axes.secondary_xaxis("top", functions=(self.energy_secodary_axis()))
        self.second_axis.set_xlabel('Energy (GeV)')

        # prevent scientific notation axes
        self.graph.axes.ticklabel_format(useOffset=False)
        self.second_axis.ticklabel_format(useOffset=False)

        self.graph.canvas.draw_idle()

        return None 
    @staticmethod
    def erf_model(x, mu, sigma) -> float:
        return 0.5 * (1 + erf((x-mu)/(np.sqrt(2)*sigma)))
if __name__ == "__main__":
    print("_fitting.py contains class mixin functions for resdepGUI.py and should not be run directly.")
