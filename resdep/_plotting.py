"""
Class mixins (not general) for resdepGUI related to plotting to the matplotlib canvas in the GUI.

ONLY for use (import) in resdepGUI
"""

from typing import Union, Protocol, TYPE_CHECKING
import builtins
import numpy as np
import numpy.typing as npt
from scipy import stats, optimize
from scipy.ndimage import gaussian_filter1d
import logging, traceback
from functools import partial

from PySide6.QtWidgets import (
    QSpinBox
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.lines import Line2D

from resdep.experiment import ResonantDepolarisation
from resdep._calculations import energy_calc, freq_calc, model

if TYPE_CHECKING:
    class HasValueProtocol(Protocol):
        @property
        def sectors(self) -> list[str]: ...
        @sectors.setter
        def sectors(self, value) -> list[str]: ...
        @property
        def sigma(self) -> QSpinBox: ...
        @sigma.setter
        def sigma(self, value: QSpinBox) -> QSpinBox: ...
        @property
        def canvas(self) -> FigureCanvasQTAgg: ...
        @canvas.setter
        def canvas(self, value) -> FigureCanvasQTAgg: ...
        @property
        def resdep(self) -> ResonantDepolarisation: ...
        @resdep.setter
        def resdep(self, value) -> ResonantDepolarisation: ...
else:
    class HasValueProtocol: ...


class Mixin(HasValueProtocol):

    def plot_ratio_loss(self, freqs: list[float], beam_loss_window_1: dict[str, list[float]], beam_loss_window_2: dict[str, list[float]]):
        """
        Takes the ratio of the beam loss windows and plots the result. \\
        Data is smoothed by a gaussian function with a sigma defined on the GUI. 
        """
        try:
            # calculate / format data
            self.ratio_loss = {}
            self.freqs_array = np.array(freqs)/1e3

            for sector in self.sectors:
                # add offset so no ratio is divide by zero 
                beam_loss_window_1[f"{sector}B"] = [value + 1 for value in beam_loss_window_1[f"{sector}B"]]
                beam_loss_window_2[f"{sector}B"] = [value + 1 for value in beam_loss_window_2[f"{sector}B"]]
                self.ratio_loss[f"{sector}B"] = np.array(beam_loss_window_1[f"{sector}B"])/np.array(beam_loss_window_2[f"{sector}B"])

            sigma = self.sigma.value()
            for sector in self.sectors:
                # filter / bin
                self.ratio_loss[f"{sector}B"] = gaussian_filter1d(self.ratio_loss[f"{sector}B"], sigma)
                # set zero
                self.ratio_loss[f"{sector}B"] += np.min(self.ratio_loss[f"{sector}B"])
                # normalise
                self.ratio_loss[f"{sector}B"] *= 1/np.max(self.ratio_loss[f"{sector}B"])
                # plot
                self.canvas.axes.plot(self.freqs_array, self.ratio_loss[f"{sector}B"] + 0.03 * float(sector), label=f"{sector}B")

            self.canvas.axes.legend(loc='center right', ncol=1, reverse=True) # bbox_to_anchor=(0.5, -0.3)
            self.canvas.figure.suptitle("Ratio beam loss")
            self.canvas.axes.set_xlabel("frequency (kHz)")

            # Create energy top axis
            self.second_axis = self.canvas.axes.secondary_xaxis(
                "top", 
                functions=(
                    partial(energy_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic), 
                    partial(freq_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic)
                    )
                )
            self.second_axis.set_xlabel('Energy (GeV)')

            # prevent scientific notation axes
            self.canvas.axes.ticklabel_format(useOffset=False)
            self.second_axis.ticklabel_format(useOffset=False)

            self.canvas.draw_idle()

        except Exception:
            logging.error(traceback.format_exc())
    
    def plot_fits(self, ydata: dict[str, npt.NDArray[np.float64]], E0_mean: Union[float, np.floating, None] = None, E0_stddev: Union[float, np.floating, None] = None, mask: Union[list[bool], "builtins.ellipsis"] = ..., xlims: Union[tuple[np.floating], None] = None, ylims: Union[tuple[np.floating], None] = None) -> None:
        """
        Plots the passed fit (ydata), intended on-top of the existing data \\
        Optionally shades two standard deviations around the mean
        """
        
        for key, fit in ydata.items():
            sector = key.replace("A", "")
            sector = sector.replace("B", "")
            # plot fit
            self.canvas.axes.plot(self.freqs_array[mask], fit + 0.03 * float(sector), linestyle='--', color="red")
            # plot baseline
            self.canvas.axes.axhline(y=fit[0] + 0.03 * float(sector), xmin=0, xmax=1, alpha=0.1, linestyle="--", color="black")

        # shade 2*std.dev region on plot
        if E0_mean and E0_stddev:
            self.canvas.axes.axvspan(
                freq_calc(energy=float(E0_mean-E0_stddev), f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic),
                freq_calc(energy=float(E0_mean+E0_stddev), f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic),
                alpha=0.1,
                color="black"
            )

        # reset the plot limits
        if xlims:
            self.canvas.axes.set_xlim(xlims)
        if ylims:
            self.canvas.axes.set_ylim(ylims)

        return None

    def plot_expected_resonances(self, ) -> None:
        """
        Plots the expected resoanaces around the main (spin tune resonance). \\
        This includes synchrotron sidebands and betatron resonances. \\
        Updates dynamically on settings pane changes.
        """
    
        # --- resonance of competing tunes (betatron, synchrotron)
        # plot these resonances around the expected depolarisation resonance
        synchrotron_sidebands = [self.resdep.res_freq + i*(self.resdep.f_rev * self.resdep.v_synch) for i in [-3, -2, -1, 1, 2, 3]]

        for h in range(0,30,1):
            v_x_resonance = self.resdep.f_rev * (self.resdep.v_x + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
            v_y_resonance = self.resdep.f_rev * (self.resdep.v_y + h) # 300 Hz
            v_x_mirror_resonance = self.resdep.f_rev * ((1-self.resdep.v_x) + h) # 400 Hz (v_s 0th order ~ 1215 Hz)
            v_y_mirror_resonance = self.resdep.f_rev * ((1-self.resdep.v_y) + h) # 300 Hz
            self.canvas.axes.axvline(x=v_x_resonance, ymin=0, ymax=0.7, color="blue", linestyle="-")
            self.canvas.axes.axvline(x=v_y_resonance, ymin=0, ymax=0.7, color="green", linestyle="-")
            self.canvas.axes.axvline(x=v_x_mirror_resonance, ymin=0, ymax=0.7, color="blue", alpha=0.5, linestyle="-.")
            self.canvas.axes.axvline(x=v_y_mirror_resonance, ymin=0, ymax=0.7, color="green", alpha=0.5, linestyle="-.")

        self.canvas.axes.axvline(x=self.resdep.res_freq, ymin=0, ymax=1, color="red", linewidth=2)

        for sideband in synchrotron_sidebands:
            self.canvas.axes.axvline(x=sideband, ymin=0, ymax=0.4, color="black", alpha=0.5, linestyle="dotted")

        self.canvas.axes.text(x=self.resdep.res_freq, y=0.95, s=r"$\nu_\mathrm{s}$ = " + f"{self.resdep.res_freq:.0f} Hz  ", color="red", horizontalalignment="right")
        self.canvas.figure.suptitle("Expected resonances within the scan range")
        self.canvas.axes.set_xlabel("frequency (kHz)")
        self.canvas.axes.set_xlim(self.resdep.sweep_limits[0], self.resdep.sweep_limits[-1])
        self.canvas.axes.set_yticks([])
        legend_elements = [
            Line2D([0], [0], color='red', linewidth=2, label=r"$\nu_\mathrm{s}$"),
            Line2D([0], [0], color='blue', linewidth=1, label=r"$\nu_x$"),
            Line2D([0], [0], color='green', linewidth=1, label=r"$\nu_y$"),
            Line2D([0], [0], color='black', linewidth=1, label=r"$\nu_\mathrm{synch}$", linestyle="dotted", alpha=0.5),
            Line2D([0], [0], color='blue', linewidth=1, label=r"mirror $\nu_x$", alpha=0.5, linestyle="-."),
            Line2D([0], [0], color='green', linewidth=1, label=r"mirror $\nu_y$", alpha=0.5, linestyle="-."),
        ]                         
        self.canvas.axes.legend(handles=legend_elements, ncols=2)

        self.second_axis = self.canvas.axes.secondary_xaxis(
            "top", 
            functions=(
                partial(energy_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic), 
                partial(freq_calc, f_rev=self.resdep.f_rev, harmonic=self.resdep.harmonic)
                )
            )
        self.second_axis.set_xlabel('Energy (GeV)')

        # prevent scientific notation axes
        self.canvas.axes.ticklabel_format(useOffset=False)
        self.second_axis.ticklabel_format(useOffset=False)

        self.canvas.draw_idle()
        return None
    
if __name__ == "__main__":
    print("_fitting.py contains class mixin functions for resdepGUI.py and should not be run directly.")
