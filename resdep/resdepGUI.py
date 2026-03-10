"""
Barebones Qt layout for running resdep experiments.
Basically just an input panel for all the experiment sweep variables.
Going to build in a plotting callback for the range and harmonic

Future future stuff is to plot the output of the experiment which should be a PV. 
It would be nice to plot continuously but im not sure how to do that with top-up normalisation
"""

import datetime
from typing import Union, cast, Literal
import sys
import json
import os
import ntpath
import posixpath
import logging, traceback
import subprocess
import platform
import warnings
import numpy as np
from scipy.ndimage import gaussian_filter1d
# fitting
from scipy import optimize

# Qt
from PySide6.QtWidgets import (
    QApplication, 
    QWidget, 
    QFormLayout, 
    QSpinBox, 
    QHBoxLayout, 
    QLineEdit, 
    QDoubleSpinBox, 
    QVBoxLayout, 
    QComboBox, 
    QProgressBar, 
    QPushButton, 
    QLabel,
    QStatusBar,
    QMessageBox,
    QStyle,
    QFileDialog,
    QCheckBox
    )
from PySide6.QtCore import (
    QThreadPool, 
    QObject, 
    Signal, 
    QRegularExpression,
    QTimer,
    QSize,
    QSettings,
    QCoreApplication,
    QPoint
    )
from PySide6.QtGui import (
    QRegularExpressionValidator
    )
# Matplotlib dependencies
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# resdep
from resdep.experiment import ResonantDepolarisation
import resdep._plotting as _plotting
import resdep._fitting as _fitting
from resdep._calculations import calculate_fitted_energy_stats

# TODO: Run (optional) FPM alignment script, write to inits?
# TODO: Working on this with ADC_integrated buffer which is a much more elegant solution.
# TODO: if it doesn't contain a loop, then there is no need to thread it or create a separate class and wrapper just for the alignment function
# TODO: Fix top-up normalisation breaking on one injection

##########################
# -------- GUI --------- #
##########################
class MainWindow(QWidget, _plotting.Mixin, _fitting.Mixin):
    """
    The Qt GUI for Resonant Depolarisation
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # perpetual GUI settings
        QCoreApplication.setOrganizationName("Physics")
        QCoreApplication.setApplicationName("Resonant Depolarisation")
        self.read_GUI_settings()

        # --- Resonant Depolarisation module
        # import
        self.resdep = ResonantDepolarisation()
        # define thread for resdep
        self.thread_manager = QThreadPool()
        # decorate resdep
        self.resdepQt = QtDecorator(self.resdep)
        # Connect emitted signals from worker (wrapped resdep)
        # to GUI update (member) functions (slots)
        self.resdepQt.progress.connect(self.on_progress_update)
        self.resdepQt.new_plot_info.connect(self.on_new_plot_info)
        self.resdepQt.status.connect(self.on_status_update)
        self.resdepQt.data_path.connect(self.on_data_path_update)
        self.resdepQt.start_timer.connect(self.on_start_timer)
        self.resdepQt.finished.connect(self.on_finish)

        # init path
        self.current_path = os.getcwd()
        self.parent_path = os.path.dirname(self.current_path)
        self.config_path = os.path.join(self.current_path, "config", "resdepGUI")

        # init window
        self.setWindowTitle("Resonant Depolarisation")
        self.setMinimumWidth(400)

        # init icon
        pixmapi = QStyle.StandardPixmap.SP_DirIcon
        dir_icon = self.style().standardIcon(pixmapi)

        # create an layout for the whole window
        # ------------------------------------------- #
        # |     Parameters      |       Plot        | #
        # ------------------------------------------- #
        # |                 do fit?                   #
        # |             -- Progress Bar -- % complete #
        # |config           Run Button | Abort button #
        # ------------------------------------------- #
        # status bar -------------------------------- #

        full_layout = QVBoxLayout()
        self.setLayout(full_layout)

        # horizontal layout - side by side parameters and plot
        top_pane = QWidget(self)
        top_layout = QHBoxLayout()
        top_pane.setLayout(top_layout)

        # --- settings pane
        # ---------------------- #
        # |     Parameters       #
        # ---------------------- #
        settings_pane = QWidget(self)
        settings_layout = QFormLayout()
        settings_pane.setLayout(settings_layout)

        # define settings widgets
        self.kicker_amp         = QSpinBox(minimum=0, maximum=100, value=0, suffix="%")
        self.harmonic           = QSpinBox(minimum=0, maximum=15, value=0)
        self.bounds             = QDoubleSpinBox(minimum=0.001, maximum=2, decimals=3, singleStep=0.001, value=0.05, suffix="%")
        self.freq_shift         = QDoubleSpinBox(minimum=-10, maximum=10, decimals=3, singleStep=0.001, value=0, suffix=" KHz")
        self.sweep_direction    = QComboBox(self)
        self.sweep_direction.addItem("Forward")
        self.sweep_direction.addItem("Backward")
        self.sweep_rate         = QDoubleSpinBox(minimum=0.1, maximum=10, decimals=1, singleStep=0.1, value=10, suffix=" Hz/s")
        self.sweep_step_size    = QDoubleSpinBox(minimum=0.5, maximum=10, value=0.5, singleStep=0.5, decimals=1, suffix=" Hz")
        self.drive_pattern      = QLineEdit("36:215")
        self.drive_pattern.setMask("900:900")
        pattern_validator       = QRegularExpressionValidator(
            QRegularExpression(r"^(?:!|(?:[1-9]|[1-9]\d|[12]\d\d|3[0-5]\d|360):(?:[1-9]|[1-9]\d|[12]\d\d|3[0-5]\d|360))$"), 
            self.drive_pattern
            )
        self.drive_pattern.setValidator(pattern_validator)

        # ADC windows as 4 separate inputs
        ADC_window_pane = QWidget(self) 
        ADC_form_layout = QHBoxLayout()
        ADC_window_pane.setLayout(ADC_form_layout)
        self.ADC_offset_1 = QSpinBox(minimum=0, maximum=86, value=0)
        self.ADC_window_1 = QSpinBox(minimum=0, maximum=86, value=42)
        self.ADC_offset_2 = QSpinBox(minimum=0, maximum=86, value=42)
        self.ADC_window_2 = QSpinBox(minimum=0, maximum=86, value=44)
        ADC_form_layout.addWidget(self.ADC_offset_1)
        ADC_form_layout.addWidget(self.ADC_window_1)
        ADC_form_layout.addWidget(self.ADC_offset_2)
        ADC_form_layout.addWidget(self.ADC_window_2)

        # add settings widgets to a list for loops (enabling/disabling)
        self.settings_pane_widgets: list[QWidget] = [
            self.kicker_amp,
            self.harmonic,
            self.bounds,
            self.freq_shift,
            self.sweep_direction,
            self.sweep_rate,
            self.sweep_step_size,
            self.drive_pattern,
            self.ADC_offset_1,
            self.ADC_window_1,
            self.ADC_offset_2,
            self.ADC_window_2
        ]

        # timing labels (dwell, estimated, elapsed)
        self.dwell_time         = QLabel(f"{self.resdep.dwell_time:.2f} s")
        self.estimated_time     = QLabel(self.resdep.estimated_sweep_time)
        self.elapsed_time: int  = 0
        self.timer              = QTimer(self)
        self.timer.setInterval(1000) # update every 1 s
        self.elapsed_time_label  = QLabel("")

        # fit panel
        self.button_do_fit       = QPushButton("Do fit")
        self.button_do_fit.setEnabled(False)
        self.sigma               = QSpinBox(minimum=1, maximum=100, value=10)
        self.sigma.setEnabled(False)
        
        # separate layout for sector checkboxes
        checkbox_pane            = QWidget(self)
        checkbox_layout          = QHBoxLayout()
        checkbox_pane.setLayout(checkbox_layout)
        self.sectors: list[str] = ["1", "4", "8", "11", "12", "13"]
        self.sector_checkboxes = [QCheckBox(sector) for sector in self.sectors]
        # add to layout
        checkbox_layout.addWidget(QLabel("Sectors:"))
        for checkbox in self.sector_checkboxes:
            checkbox.setEnabled(False)
            checkbox_layout.addWidget(checkbox)
        # fit results labels
        self.fitted_beam_energy_label = QLabel("")
        self.fit_results_label        = QLabel("")

        # add do_fit widgets to list for enabling / disabling in loop
        self.fit_widgets = [
            self.button_do_fit,
            self.sigma,
        ]
        self.fit_widgets.extend(self.sector_checkboxes)

        # Add callbacks
        self.kicker_amp.valueChanged.connect(self.update_experiment_settings)
        self.harmonic.valueChanged.connect(self.update_expected_resonances)
        self.bounds.valueChanged.connect(self.update_expected_resonances)
        self.freq_shift.valueChanged.connect(self.update_expected_resonances)
        self.sweep_rate.valueChanged.connect(self.update_experiment_settings)
        self.sweep_step_size.valueChanged.connect(self.update_experiment_settings)
        self.timer.timeout.connect(self.update_elapsed_time)
        self.button_do_fit.clicked.connect(self.do_fit)
        
        # add widgets to settings pane
        settings_layout.addRow("Kicker amplifier (%)", self.kicker_amp)
        settings_layout.addRow("Harmonic", self.harmonic)
        settings_layout.addRow("Energy bounds\n(% dE/E)", self.bounds)
        settings_layout.addRow("Resonance shift (KHz)", self.freq_shift)
        settings_layout.addRow("Sweep direction", self.sweep_direction)
        settings_layout.addRow("Sweep rate (Hz/s)", self.sweep_rate)
        settings_layout.addRow("Sweep step size (Hz)", self.sweep_step_size)
        settings_layout.addRow("Drive pattern\n(start:stop)", self.drive_pattern)
        settings_layout.addRow("ADC counter windows", ADC_window_pane)
        settings_layout.addRow("Dwell time:", self.dwell_time)
        settings_layout.addRow("Estimated sweep time:", self.estimated_time)
        settings_layout.addRow("Elapsed time:", self.elapsed_time_label)
        settings_layout.addRow("", self.button_do_fit)
        settings_layout.addRow("sigma", self.sigma)
        settings_layout.addWidget(checkbox_pane)
        settings_layout.addRow("Fitted Beam Energy:", self.fitted_beam_energy_label)
        settings_layout.addRow("Fit results:", self.fit_results_label)
        # Add to layout. Is horizontal box, so adds left
        top_layout.addWidget(settings_pane)

        # --- progress bar
        # |             -- Progress Bar -- % complete #
        self.progress_bar = QProgressBar(self)
        
        # --- button pane
        # | config          Run Button | Abort button #
        button_pane = QWidget(self)
        button_layout = QHBoxLayout()
        button_pane.setLayout(button_layout)

        # load previous settings button (from last experiment)
        self.button_load_run_settings = QPushButton("Load last run")
        self.button_load_run_from_file = QPushButton("Load from file")
        self.button_load_run_from_file.setIcon(dir_icon)

        # data directory button
        self.button_open_data_path = QPushButton("Data path")
        self.button_open_data_path.setIcon(dir_icon)
        self.data_path = ""

        # load finished experiment data button
        self.button_load_finished_experiment_data = QPushButton("Load finished experiment data")
        self.button_load_finished_experiment_data.setIcon(dir_icon)

        # run / abort buttons
        self.button_abort = QPushButton("Abort")
        self.button_run = QPushButton("Run")
        self.button_abort.setEnabled(False)
        self.button_open_data_path.setEnabled(False)

        # add callbacks for buttons
        self.button_load_run_settings.clicked.connect(self.load_run_settings)
        self.button_load_run_from_file.clicked.connect(self.load_run_from_file)
        self.button_open_data_path.clicked.connect(self.open_data_path)
        self.button_load_finished_experiment_data.clicked.connect(self.load_finished_experiment_data)
        self.button_run.clicked.connect(self.run_experiment)
        self.button_abort.clicked.connect(self.abort)

        # add buttons to layout
        button_layout.addWidget(self.button_load_run_settings)
        button_layout.addWidget(self.button_load_run_from_file)
        button_layout.addWidget(self.button_open_data_path)
        button_layout.addWidget(self.button_load_finished_experiment_data)
        # spacer so run/abort buttons are flush right
        button_layout.addStretch()
        # change the spacing between the buttons, like an offset, which doesn't scale with the window
        # Measured in px
        button_layout.setSpacing(20) # px
        button_layout.addWidget(self.button_run)
        button_layout.addWidget(self.button_abort)

        # status bar -------------------------------- #
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Status: Ready")

        # --- plot pane
        # --------------------- #
        # |       Plot        | #
        # --------------------- #
        plot_pane = QWidget(self)
        plot_layout = QVBoxLayout()
        plot_pane.setLayout(plot_layout)

        # Create canvas
        self.canvas = PlotCanvas(self)
        # calculate range and draw plot
        self.update_expected_resonances()
        # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
        plot_toolbar = NavigationToolbar(self.canvas, self)
        # add plot to pane
        plot_layout.addWidget(plot_toolbar)
        plot_layout.addWidget(self.canvas)
        # Add to top layout. Is horizontal box, so adds right
        top_layout.addWidget(plot_pane)

        # add everything to full layout
        full_layout.addWidget(top_pane)
        full_layout.addWidget(self.progress_bar)
        full_layout.addWidget(button_pane)
        full_layout.addWidget(self.status_bar)

        self.show()

    # *--------------------------------* #
	# *---------- Experiment ----------* #
	# *--------------------------------* # 
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def run_experiment(self, ) -> None:
        """
        Executes the resdep experiment in a separate thread. \\
        resdep is wrapped in a worker class that attaches emitted progress, status, and plot updates (info)
        """

        # Write settings pane to resdep
        self.update_experiment_settings()

        # grey out settings
        self.enable_GUI_pane(pane="settings", enable=False)
        # grey out run, load buttons
        self.button_run.setEnabled(False)
        self.button_load_run_settings.setEnabled(False)
        self.button_load_run_from_file.setEnabled(False)
        self.button_load_finished_experiment_data.setEnabled(False)
        # enable abort button (and turn red)
        self.button_abort.setEnabled(True)
        self.button_abort.setStyleSheet("QPushButton {background-color: red;}")
        # update status bar
        self.status_bar.showMessage("Status: Starting up...")
            
        # call resdep
        self.thread_manager.start(self.resdepQt.run)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_progress_update(self, step: int) -> None:
        """
        Simply update the value of the progress bar \\
        Uses emitted signal from resdep (worker wrapper)
        """
        self.progress_bar.setValue(step)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_new_plot_info(self, freqs: list[float], beam_loss_window_1: dict[str, list[float]], beam_loss_window_2: dict[str, list[float]]) -> None:
        """
        Updates the GUI plot with the latest ratio loss data
        """
        self.canvas.axes.clear()
        self.plot_ratio_loss(freqs, beam_loss_window_1, beam_loss_window_2)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_status_update(self, message) -> None:
        """
        Updates the GUI statues (primarily from running to sleeping on injection)
        """
        self.status_bar.showMessage(message)
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_data_path_update(self, data_path: str) -> None:
        """
        Assign data path from resdep to GUI button 
        Spawn error logger
        """
        self.data_path = data_path
        self.button_open_data_path.setEnabled(True)

        # --- logging to console and file
        # Create a logger
        self.logger = logging.getLogger('resdep_logger')
        self.logger.setLevel(logging.DEBUG)
        # Create a formatter to define the log format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        # Create a file handler to write logs to a file
        file_handler = logging.FileHandler(os.path.join(data_path, "logfile.log"))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        # Create a stream handler to print logs to the console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # You can set the desired log level for console output
        console_handler.setFormatter(formatter)
        # Add the handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_finish(self,) -> None:
        """
        Re-enable the run and abort buttons and settings panel widgets, update status
        """
        self.status_bar.showMessage("Status: Experiment finished")

        # disable abort button
        self.button_abort.setEnabled(False)
        # self.button_abort.setStyleSheet("QPushButton {background-color: grey;}")
        
        # relabel run button as "reset"
        self.button_run.setText("Reset")
        self.button_run.clicked.disconnect(self.run_experiment)
        self.button_run.clicked.connect(self.reset_GUI)
        self.button_run.setEnabled(True)

        # enable fit panel
        self.enable_GUI_pane(pane="fit", enable=True)

        # make sure progress bar reads 100%
        self.progress_bar.setValue(100)
        self.progress_bar.setMaximum(100)

        # save settings to data path
        self.save_experiment_settings(path=self.resdep.data_path)

        self.timer.stop()
        self.elapsed_time_label.setText(f"Experiment completed in {self.elapsed_timedelta}")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_start_timer(self, ) -> None:
        self.timer.start()
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_elapsed_time(self, ) -> None:
        self.elapsed_time += 1
        self.elapsed_timedelta = datetime.timedelta(seconds=self.elapsed_time)
        self.elapsed_time_label.setText(f"{self.elapsed_timedelta}")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def read_GUI_settings(self,) -> None:
        """
        Reads and applies GUI settings / config using `QSettings`. \\
        Compatible for using resdep as a module, stores settings in OS specific system directories (*e.g.* `etc\\`, registry) 
        """
        self.GUI_settings = QSettings()

        window_pos = self.GUI_settings.value("window_pos", defaultValue=QPoint(50, 50))
        window_size = self.GUI_settings.value("window_size", defaultValue=QSize(400, 400))
        if isinstance(window_pos, QPoint):
            self.move(window_pos)
        if isinstance(window_size, QSize):
            self.resize(window_size)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def save_experiment_settings(self, path = None) -> None:

        try:
            # add to dict
            settings_pane_config: dict[str, Union[str, int, float]] = {
            "kicker_amp"        : self.kicker_amp.value(),
            "harmonic"          : self.harmonic.value(),
            "bounds"            : self.bounds.value(),
            "freq_shift"        : self.freq_shift.value(),
            "sweep_direction"   : self.sweep_direction.currentText(),
            "sweep_rate"        : self.sweep_rate.value(),
            "sweep_step_size"   : self.sweep_step_size.value(),
            "drive_pattern"     : self.drive_pattern.text(),
            "ADC_offset_1"      : self.ADC_offset_1.value(),
            "ADC_window_1"      : self.ADC_window_1.value(),
            "ADC_offset_2"      : self.ADC_offset_2.value(),
            "ADC_window_2"      : self.ADC_window_2.value()
            }

            # save to file
            if not path:
                path = self.config_path
            with open(os.path.join(path, "settings_pane.json"), "w") as f:
                json.dump(settings_pane_config, f)

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(
            self,
            "Error",
            "Failed to save experiment settings?."
            )

        # new: using QSettings
        self.GUI_settings = QSettings()
        self.GUI_settings.setValue("window_pos", self.pos())
        self.GUI_settings.setValue("window_size", self.size())

        return None
    
    
    # *--------------------------------* #
	# *------ Settings Callbacks ------* #
	# *--------------------------------* #
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_experiment_settings(self) -> None:
        """
        Writes values from GUI to self.resdep \\
        Values are fed into experiment for initiation.
        """

        # turn kicker amp box orange over 0
        if self.kicker_amp.value() > 0:
            self.kicker_amp.setStyleSheet("QSpinBox {background-color: orange;}")
        else:
            self.kicker_amp.setStyleSheet("QSpinBox {background-color: white;}")

        # update resdep values
        self.resdep.harmonic 			= self.harmonic.value()
        self.resdep.bounds 			    = self.bounds.value() / 100
        self.resdep.freq_shift          = self.freq_shift.value()
        self.resdep.set_drive_pattern 	= self.drive_pattern.text()
        self.resdep.set_kicker_amp 	    = self.kicker_amp.value() / 100
        self.resdep.sweep_rate 		    = self.sweep_rate.value()
        self.resdep.sweep_step_size 	= self.sweep_step_size.value()
        if self.sweep_direction.currentText() == "Forward":
            self.resdep.sweep_direction	= 1
        elif self.sweep_direction.currentText() == "Backward":
            self.resdep.sweep_direction	= -1 

        # self.fast_log_frequency	
        # self.slow_log_frequency	
        # ADC masks
        self.resdep.set_adc_counter_offset_1 = self.ADC_offset_1.value()
        self.resdep.set_adc_counter_window_1 = self.ADC_window_1.value()
        self.resdep.set_adc_counter_offset_2 = self.ADC_offset_2.value()
        self.resdep.set_adc_counter_window_2 = self.ADC_window_2.value()

        # calculate range
        self.resdep.calculate_range()

        # update the sweep time | dwell time | progress bar
        self.estimated_time.setText(self.resdep.estimated_sweep_time)
        self.dwell_time.setText(f"{self.resdep.dwell_time:.2f} s")
        self.progress_bar.setMaximum(self.resdep.sweep_steps)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_expected_resonances(self, ) -> None:
        """
        Plots the expected resoanaces around the main (spin tune resonance). \\
        This includes synchrotron sidebands and betatron resonances. \\
        Updates dynamically on settings pane changes.
        """
        self.update_experiment_settings()
        self.canvas.axes.clear()
        self.plot_expected_resonances()

        return None

    # *--------------------------------* #
	# *------ Button Callbacks --------* #
	# *--------------------------------* #
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def open_data_path(self, ) -> None:
        """
        Opens data folder on any OS
        """
        # MacOS
        if platform.system() == "Darwin":
            subprocess.call(("open", self.data_path))
        # Windows
        elif platform.system() == "Windows":
            os.startfile(self.data_path)
        # Linux
        else:
            subprocess.call(("xdg-open", self.data_path))
        
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def load_run_settings(self, path = None) -> None:
        """
        Overwrite settings pane with last runs settings
        """

        if not path:
            path = os.path.join(self.config_path, "settings_pane.json")

        if path[-18:] != "settings_pane.json":
            QMessageBox.critical(
                self,
                "Critical",
                "Incorrect config file. Should be named \"settings_pane.json\".",
                QMessageBox.StandardButton.Ok
            )

        
        try:
            # load settings pane config from json
            with open(os.path.join(path), "r") as f:
                settings_pane_config = json.load(f)
            # update front panel (can't do in loop due to different QWidget syntax)
            self.kicker_amp.setValue(settings_pane_config["kicker_amp"])
            self.harmonic.setValue(settings_pane_config["harmonic"])
            self.bounds.setValue(settings_pane_config["bounds"])
            self.freq_shift.setValue(settings_pane_config["freq_shift"])
            self.sweep_direction.setCurrentText(settings_pane_config["sweep_direction"])
            self.sweep_rate.setValue(settings_pane_config["sweep_rate"])
            self.sweep_step_size.setValue(settings_pane_config["sweep_step_size"])
            self.drive_pattern.setText(settings_pane_config["drive_pattern"])
            self.ADC_offset_1.setValue(settings_pane_config["ADC_offset_1"])
            self.ADC_window_1.setValue(settings_pane_config["ADC_window_1"])
            self.ADC_offset_2.setValue(settings_pane_config["ADC_offset_2"])
            self.ADC_window_2.setValue(settings_pane_config["ADC_window_2"])
            
            # update resdep settings and plot after load
            self.update_expected_resonances()

        except Exception:
            logging.error(traceback.format_exc())

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def load_run_from_file(self, ) -> None:
        """
        load experiment settings config (loads into settings pane) - spawns file dialog window
        """
        filename, _ = QFileDialog.getOpenFileName(
            dir="Data", 
            filter="All Files (*);; JSON (*.json);; settings config (settings_pane.json)", 
            selectedFilter="settings config (settings_pane.json)"
            )
        # print(f"filename={filename}")
        # print(f"len(filename)={len(filename)}")
        if len(filename) > 0:
            self.status_bar.showMessage("Status: loading...")
            self.load_run_settings(path=filename)
            self.status_bar.showMessage("Status: Ready")
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def do_fit(self, ) -> None:
        """
        Performs error function fit to experiment data within xlim of interactive plot for all selected sectors
        """
        checked_sector_checkboxes = cast(list[bool], [sector_checkbox.isChecked() for sector_checkbox in self.sector_checkboxes])
        self.checked_sectors = [_sector for _sector, checked in zip(self.sectors, checked_sector_checkboxes) if checked]

        # warn if no sectors selected and exit early
        if not any(checked_sector_checkboxes):
            warnings.warn("No sectors selected")
            QMessageBox.critical(
                self,
                "Critical",
                "No sectors selected on which to perform fit.",
                QMessageBox.StandardButton.Ok
            )
            return None
        
        mask, xlims, ylims = self.calculate_fitting_mask()

        self.on_new_plot_info(
            freqs=self.resdep.freqs, 
            beam_loss_window_1=self.resdep.beam_loss_window_1, 
            beam_loss_window_2=self.resdep.beam_loss_window_2
        )

        y_model, fitted_beam_energies, fitted_beam_energy_stddevs, fit_results = self.fit_error_functions(mask=mask)

        if len(y_model) == 0: # if all fits fail
            print("Fit results:\n", fit_results)
            return None

        if len(self.checked_sectors) > 1: # calc stddev of means if multiple fits
            E0_mean, E0_stddev, E0_mean_sigfig, E0_stddev_sigfig = calculate_fitted_energy_stats(fitted_beam_energies) 
        else: # use stddev of fit if only one fit
            E0_mean, E0_stddev, E0_mean_sigfig, E0_stddev_sigfig = calculate_fitted_energy_stats(fitted_beam_energies, fitted_beam_energy_stddevs) 

        self.plot_fits(y_model, E0_mean, E0_stddev, mask, xlims, ylims)
        
        fitted_beam_energy_str = f"{E0_mean_sigfig} GeV" + u" \u00B1 " + f"{E0_stddev_sigfig*1e6:.0f} keV"
        print(f"mean E0 = {fitted_beam_energy_str}")
        print("Fit results:\n", fit_results)
        # update GUI
        self.fitted_beam_energy_label.setText(fitted_beam_energy_str)
        self.fit_results_label.setText(fit_results)
    
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def load_finished_experiment_data(self, ) -> None:
        """
        Loads finished experiment data (freqs, beam_loss) from folder, refreshes plot() for do_fit()
        """
        path = QFileDialog.getExistingDirectory(
            dir=os.path.join(self.parent_path, "data", "resdep"),
            options=QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
            )
        
        if len(path) > 0:
            # convert path to os format
            # Windows
            if platform.system() == "Windows":
                path = path.replace(posixpath.sep, os.sep)
            # Linux and MacOS
            else:
                path = path.replace(ntpath.sep, os.sep)
            # load freqs txt
            with open(os.path.join(path, "freqs.txt"), "r") as f:
                for line in f.readlines():
                    self.resdep.freqs.append(float(line))	# Hz -> kHz
            # load beam loss windows
            with open(os.path.join(path, "adc_counter_loss_1.json"), "r") as f:
                self.resdep.beam_loss_window_1 = json.load(f)
            with open(os.path.join(path, "adc_counter_loss_2.json"), "r") as f:
                self.resdep.beam_loss_window_2 = json.load(f)
            # load res_freq as guess for fit
            with open(os.path.join(path, "metadata.json"), "r") as f:
                metadata: dict = json.load(f)
            
            # safely assign metadata values (if they exist)
            metadata_keys = ["f_rev", "fractional tune", "harmonic"]
            if not all(key in metadata for key in metadata_keys):
                QMessageBox.critical(
                self,
                "Error",
                "Missing metadata."
                )
                return None
            self.resdep.f_rev       = metadata["f_rev"]
            self.resdep.tune        = metadata["fractional tune"]
            self.resdep.harmonic    = metadata["harmonic"]

            # calculate expected resonance frequency
            self.resdep.res_freq = self.resdep.f_rev * (self.resdep.tune + self.resdep.harmonic)

            # refresh plot
            self.on_new_plot_info(
                freqs=self.resdep.freqs,
                beam_loss_window_1=self.resdep.beam_loss_window_1,
                beam_loss_window_2=self.resdep.beam_loss_window_2
            )

            # enable fit pane
            self.enable_GUI_pane(pane="fit", enable=True)
            
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def abort(self, ) -> None:
        """
        Interrupts resdep experiment loop.
        """

        print("Abort!")

        # Disable abort button
        self.button_abort.setEnabled(False)
        self.button_abort.setStyleSheet("QPushButton {background-color: grey;}")

        # abort thread
        self.resdepQt.abort()

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def reset_GUI(self, ) -> None:
        """
        After experiment, resets the GUI so you can run another experiment
        """

        # relabel reset button to "run"
        self.button_run.clicked.disconnect(self.reset_GUI)
        self.button_run.setText("Run")
        self.button_run.clicked.connect(self.run_experiment)

        # re-enable settings pane
        self.enable_GUI_pane(pane="settings", enable=True)

        # re-enable load buttons
        self.button_load_finished_experiment_data.setEnabled(True)
        
        # disable fit panel
        self.enable_GUI_pane(pane="fit", enable=False)

        # make sure progress bar reads 0%
        self.progress_bar.setValue(0)

        return None
    
    # *--------------------------------* #
	# *---------- GUI Config ----------* #
	# *--------------------------------* #
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def enable_GUI_pane(self, pane: Literal["settings", "fit"], enable: bool) -> None:

        if pane == "settings":
            for widget in self.settings_pane_widgets:
                widget.setEnabled(enable)
        
        if pane == "fit":
            for widget in self.fit_widgets:
                widget.setEnabled(enable)


        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        """
        Shutdown tasks for GUI \\
        For now, just save used input parameters
        """

        answer = QMessageBox.question(
            self,
            "Confirmation",
            "Save experiment settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) 
        # if yes
        if answer == QMessageBox.StandardButton.Yes:
            
            self.save_experiment_settings()
            self.close()
            event.accept()

        else: # if no
           self.close()
           event.accept()


        return None


##########################
# ---- Qt Decorator ---- #
# ---- (threadding) ---- #
##########################
class QtDecorator(QObject):
    """
    Qt wrapper for resdep \\
    Defines emitted signals and attaches them to the worker. \\
    The worker must contain these callbacks to emit signals 
    """
    # define emitted signals (from resdep)
    progress = Signal(int) # step
    new_plot_info = Signal(list, dict, dict)
    status = Signal(str) # status: message
    data_path = Signal(str)
    start_timer = Signal()
    finished = Signal()
    # ------------------------------------------------------------------------------
    def __init__(self, worker: ResonantDepolarisation) -> None:
        super().__init__()
        self.worker = worker

        # Inject callbacks into the worker
        self.worker.progress_callback = self._emit_progress
        self.worker.plot_callback = self._emit_new_plot_info
        self.worker.status_callback = self._emit_status
        self.worker.data_path_callback = self._emit_data_path
        self.worker.timer_callback = self._emit_start_timer

        return None
    # ------------------------------------------------------------------------------
    def _emit_progress(self, step: int) -> None:
        self.progress.emit(step)
        return None
    # ------------------------------------------------------------------------------
    def _emit_new_plot_info(
            self, 
            freqs: list[float], 
            beam_loss_window_1: dict[str, list[float]], 
            beam_loss_window_2: dict[str, list[float]]
            ) -> None:
        self.new_plot_info.emit(freqs, beam_loss_window_1, beam_loss_window_2) 
        return None
    # ------------------------------------------------------------------------------
    def _emit_status(self, message: str) -> None:
        self.status.emit(message)
        return None
    # ------------------------------------------------------------------------------
    def _emit_data_path(self, data_path: str) -> None:
        self.data_path.emit(data_path)
        return None
    # ------------------------------------------------------------------------------
    def _emit_start_timer(self, ) -> None:
        self.start_timer.emit()
        return None
    # ------------------------------------------------------------------------------
    def run(self,) -> None:
        try:
            self.worker.start_experiment()
        finally:
            self.finished.emit()
        return None
    # ------------------------------------------------------------------------------
    def abort(self, ) -> None:
        self.worker.request_abort()
        return None

##########################
# ----- Matplotlib ----- #
# ------- canvas ------- #
##########################
class PlotCanvas(FigureCanvasQTAgg):
    """
    Spawn canvas instance object to add and modify in GUI
    """
    def __init__(self, parent=None, dpi=100):

        # Create the figure and figure canvas
        fig = Figure(dpi=dpi)#, constrained_layout=True)
        self.figure = fig
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = fig.add_subplot()

        # super(PlotCanvas, self).__init__(Figure())
        super().__init__(self.figure) 
        self.setParent(parent)

    # fixed size
    def sizeHint(self):
        return QSize(700, 600)

    def minimumSizeHint(self):
        return QSize(700, 600)

def spawn():
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())

# run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
