"""
Expert level Qt layout for running resdep experiments.
Basically just an input panel for all the experiment sweep variables.
"""
"""
 ██████╗ ██╗   ██╗██╗
██╔════╝ ██║   ██║██║
██║  ███╗██║   ██║██║
██║   ██║██║   ██║██║
╚██████╔╝╚██████╔╝██║
 ╚═════╝  ╚═════╝ ╚═╝
"""

import datetime
from typing import Any, Union, cast, Literal
import sys
import json
import os
from pathlib import Path
import logging, traceback
import subprocess
import platform
import warnings
import numpy as np
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
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib import rcParams

# resdep
from resdep.experiment import ResonantDepolarisation, ProcessedData
from resdep._fitting import FittingClass
from resdep._plotting import PlottingClass, Graph


##########################
# -------- GUI --------- #
##########################
class MainWindow(QWidget):
    """
    The Qt GUI for Resonant Depolarisation
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # perpetual GUI settings
        QCoreApplication.setOrganizationName("Physics")
        QCoreApplication.setApplicationName("Resonant Depolarisation")

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
        self.resdepQt.ADC_windows.connect(self.on_new_ADC_windows)
        self.resdepQt.finished.connect(self.on_finish)

        # helper classes
        sectors_to_fit = ["1", "4", "8", "11", "12", "13"]
        self.processed_data = ProcessedData(resdep=self.resdep, sectors_to_fit=sectors_to_fit)
        self.fitting        = FittingClass(resdep=self.resdep, processed_data=self.processed_data)
        # ... self.plotting initialised in _init_plot_pane() due to plot canvas attribute

        # init path
        path = Path.cwd()
        self.current_path = path
        self.parent_path = path.parent
        self.config_path = path / "config" / "resdepGUI"

        # init window
        self.setWindowTitle("Resonant Depolarisation")
        self.setMinimumWidth(400)

        # create an layout for the whole window
        # ------------------------------------------- #
        # |     Parameters      |       Plot        | #
        # ------------------------------------------- #
        # |       do fit?       |                     #
        # |             -- Progress Bar -- % complete #
        #                               Measure MX3 ? #
        # |config buttons   Run Button | Abort button #
        # status bar -------------------------------- #
        # ------------------------------------------- #

        main_window_layout = QVBoxLayout()
        self.setLayout(main_window_layout)

        self.top_pane = QWidget(self)
        self.top_layout = QHBoxLayout()
        self.top_pane.setLayout(self.top_layout)

        self._init_settings_pane()
        self._init_button_pane()

        # --- progress bar
        # |             -- Progress Bar -- % complete #
        self.progress_bar = QProgressBar(self)

        # status bar -------------------------------- #
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Status: Ready")

        self._init_plot_pane()

        # add everything to full layout
        main_window_layout.addWidget(self.top_pane)
        main_window_layout.addWidget(self.progress_bar)
        main_window_layout.addWidget(self.MX3_pane)
        main_window_layout.addWidget(self.button_pane)
        main_window_layout.addWidget(self.status_bar)

        # read previous settings (if they exist)
        self.read_GUI_settings()

        self.show()

    # *--------------------------------* #
	# *---------- GUI Layout ----------* #
	# *--------------------------------* # 
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def _init_settings_pane(self, ) -> None:
        
        # --- settings pane
        # ---------------------- #
        # |     Parameters       #
        # ---------------------- #
        settings_pane = QWidget(self)
        settings_layout = QFormLayout()
        settings_pane.setLayout(settings_layout)

        # define settings widgets
        self.kicker_amp         = QSpinBox(minimum=0, maximum=100, suffix="%")
        self.harmonic           = QSpinBox(minimum=0, maximum=15)
        self.bounds             = QDoubleSpinBox(minimum=0.001, maximum=2,   decimals=3, singleStep=0.001, suffix="%")
        self.freq_shift         = QDoubleSpinBox(minimum=-1000,  maximum=1000, decimals=3, singleStep=0.001, suffix=" KHz")
        self.sweep_direction    = QComboBox(self)
        self.sweep_direction.addItem("Forward")
        self.sweep_direction.addItem("Backward")
        self.sweep_rate         = QDoubleSpinBox(minimum=0.1, maximum=10, decimals=1, singleStep=0.1, suffix=" Hz/s")
        self.sweep_step_size    = QDoubleSpinBox(minimum=0.5, maximum=10, decimals=1, singleStep=0.5, suffix=" Hz")
        self.drive_pattern      = QLineEdit(text="36:215")
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

        # ----------------------------- Measure MX3 ? #
        # This goes above run, but its a setting and should be added to the list of widgets

        self.MX3_pane = QWidget(self)
        self.MX3_layout = QHBoxLayout()
        self.MX3_pane.setLayout(self.MX3_layout)
        self.MX3_layout.addStretch()
        self.checkbox_measure_MX3 = QCheckBox("Measure MX3?")
        self.MX3_layout.addWidget(self.checkbox_measure_MX3)

        # add settings widgets to a dict for loops (enabling/disabling)
        self.settings_pane_widgets: dict[str, QWidget] = {
            "kicker_amp"        : self.kicker_amp,
            "harmonic"          : self.harmonic,
            "bounds"            : self.bounds,
            "freq_shift"        : self.freq_shift,
            "sweep_direction"   : self.sweep_direction,
            "sweep_rate"        : self.sweep_rate,
            "sweep_step_size"   : self.sweep_step_size,
            "drive_pattern"     : self.drive_pattern,
            "ADC_offset_1"      : self.ADC_offset_1,
            "ADC_window_1"      : self.ADC_window_1,
            "ADC_offset_2"      : self.ADC_offset_2,
            "ADC_window_2"      : self.ADC_window_2,
            "_measure_MX3"      : self.checkbox_measure_MX3
        }

        self.load_default_settings()

        # timing labels (dwell, estimated, elapsed, repolarisation)
        self.dwell_time         = QLabel(f"{self.resdep.dwell_time:.2f} s")
        self.estimated_time     = QLabel(self.resdep.estimated_sweep_time)
        self.elapsed_time: int  = 0
        self.timer              = QTimer(self)
        self.timer.setInterval(1000) # update every 1 s
        self.elapsed_time_label  = QLabel("")
        self.polarisation: float = 0
        self.polarisation_label  = QLabel("")
        self.repolarisation_time: int  = 0 # seconds. 3 tpol -> 39 minutes (88 %)
        self.repolarisation_time_label = QLabel("")
        self.repolarisation_timer = QTimer(self)
        self.repolarisation_timer.setInterval(1000)

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
            checkbox.setChecked(True)
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
        self.repolarisation_timer.timeout.connect(self.update_repolarisation_time)
        self.button_do_fit.clicked.connect(self.do_fit)
        self.checkbox_measure_MX3.checkStateChanged.connect(self.update_experiment_settings)
        
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
        settings_layout.addRow("Polarisation\n(minimum, estimate):", self.polarisation_label)
        settings_layout.addRow("Repolarisation time:", self.repolarisation_time_label)
        settings_layout.addRow("", self.button_do_fit)
        settings_layout.addRow("sigma", self.sigma)
        settings_layout.addWidget(checkbox_pane)
        settings_layout.addRow("Fitted Beam Energy:", self.fitted_beam_energy_label)
        settings_layout.addRow("Fit results:", self.fit_results_label)

        # Add to layout. Is horizontal box, so adds left
        self.top_layout.addWidget(settings_pane)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def _init_button_pane(self, ) -> None:
        # --- button pane
        # | config          Run Button | Abort button #
        self.button_pane = QWidget(self)
        button_layout = QHBoxLayout()
        self.button_pane.setLayout(button_layout)

        # button icons
        dir_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        reset_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)

        # load defaults
        self.button_default_settings = QPushButton("Load defaults")
        self.button_default_settings.setIcon(reset_icon)

        # load previous settings button (from last experiment)
        self.button_settings_from_file = QPushButton("Load from file")
        self.button_settings_from_file.setIcon(dir_icon)

        # data directory button
        self.button_data_path = QPushButton("Data path")
        self.button_data_path.setIcon(dir_icon)
        self.data_path = Path.cwd()

        # load finished experiment data button
        self.button_finished_experiment_data = QPushButton("Load finished experiment data")
        self.button_finished_experiment_data.setIcon(dir_icon)

        # run / abort buttons
        self.button_abort = QPushButton("Abort")
        self.button_run = QPushButton("Run")
        self.button_abort.setEnabled(False)
        self.button_data_path.setEnabled(False)

        # add callbacks for buttons
        self.button_default_settings.clicked.connect(self.load_default_settings)
        self.button_settings_from_file.clicked.connect(self.load_experiment_settings_from_json)
        self.button_data_path.clicked.connect(self.open_data_path)
        self.button_finished_experiment_data.clicked.connect(self.load_finished_experiment_data)
        self.button_run.clicked.connect(self.run_experiment)
        self.button_abort.clicked.connect(self.abort)

        # add buttons to layout
        button_layout.addWidget(self.button_default_settings)
        button_layout.addWidget(self.button_settings_from_file)
        button_layout.addWidget(self.button_data_path)
        button_layout.addWidget(self.button_finished_experiment_data)
        # spacer so run/abort buttons are flush right
        button_layout.addStretch()
        # change the spacing between the buttons, like an offset, which doesn't scale with the window
        # Measured in px
        button_layout.setSpacing(20) # px
        button_layout.addWidget(self.button_run)
        button_layout.addWidget(self.button_abort)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def _init_plot_pane(self, ) -> None:
        # --------------------- #
        # |       Plot        | #
        # --------------------- #
        plot_pane = QWidget(self)
        plot_layout = QVBoxLayout()
        plot_pane.setLayout(plot_layout)

        # Create canvas
        self.graph = Graph(self)
        self.plotting = PlottingClass(resdep=self.resdep, processed_data=self.processed_data, graph=self.graph)
        # calculate range and draw plot
        self.update_expected_resonances()
        # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
        plot_toolbar = NavigationToolbar(self.graph, self)
        # add plot to pane
        plot_layout.addWidget(plot_toolbar)
        plot_layout.addWidget(self.graph)
        # Add to top layout. Is horizontal box, so adds right
        self.top_layout.addWidget(plot_pane)

        return None

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
        self.button_default_settings.setEnabled(False)
        self.button_settings_from_file.setEnabled(False)
        self.button_finished_experiment_data.setEnabled(False)
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
    def on_new_plot_info(self, ) -> None:
        """
        Updates the GUI plot with the latest ratio loss data
        """
        self.graph.axes.clear()
        self.processed_data.calculate_ratio_loss(sigma=self.sigma.value())
        self.plotting.plot_ratio_loss()

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_status_update(self, message) -> None:
        """
        Updates the GUI statues (primarily from running to sleeping on injection)
        """
        self.status_bar.showMessage(message)
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_data_path_update(self, data_path: Path) -> None:
        """
        Assign data path from resdep to GUI button 
        Spawn error logger
        """
        self.data_path = data_path
        self.button_data_path.setEnabled(True)

        # update canvas save directory
        rcParams["savefig.directory"] = data_path

        # --- logging to console and file
        # Create a logger
        self.logger = logging.getLogger('resdep_logger')
        self.logger.setLevel(logging.DEBUG)
        # Create a formatter to define the log format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        # Create a file handler to write logs to a file
        file_handler = logging.FileHandler(data_path / "logfile.log")
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

        # reset state
        self._abort_requested = False
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
        self.save_experiment_settings_to_json(path=self.resdep.data_path)

        self.timer.stop()

        try:
            self.elapsed_time_label.setText(f"Experiment completed in {self.elapsed_timedelta}")
        except AttributeError:
            pass

        self.repolarisation_timer.start()

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_start_timer(self, ) -> None:
        self.timer.start()
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_new_ADC_windows(self, ADC_windows: list[int], depolarised_bunches: str) -> None:
        """
        Update GUI with new values after time aligning the BLM ADC windows and BbB system
        """
        self.ADC_offset_1.setValue(ADC_windows[0])
        self.ADC_window_1.setValue(ADC_windows[1])
        self.ADC_offset_2.setValue(ADC_windows[2])
        self.ADC_window_2.setValue(ADC_windows[3])

        self.drive_pattern.setText(depolarised_bunches)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_elapsed_time(self, ) -> None: 
        """
        Add one second to elapsed time and update QLabel
        """
        self.elapsed_time += 1
        self.elapsed_timedelta = datetime.timedelta(seconds=self.elapsed_time)
        self.elapsed_time_label.setText(f"{self.elapsed_timedelta}")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_repolarisation_time(self, ) -> None:
        """
        Calculate time spent repolarising the beam after experiment end. \\ 
        Ideal wait time: (3 tpol, 39 min, 88%) \\ 
        Calculate estimate of polarisation (assuming fully depolarised at the end of the experiment) \\
        Stop after enough time (~2 hours)
        """
        self.repolarisation_time += 1
        repolarisation_timedelta = datetime.timedelta(seconds=self.repolarisation_time)
        self.repolarisation_time_label.setText(f"{repolarisation_timedelta}")

        # self.polarisation = 92.38*(1-np.exp(-self.repolarisation_time/779))
        self.polarisation = 100*(1-np.exp(-self.repolarisation_time/779))
        self.polarisation_label.setText(f"{self.polarisation:0.2f}%")

        if self.repolarisation_time >= 779*10:
            self.repolarisation_timer.stop()

        return None
    
    # *--------------------------------* #
	# *------ Settings Callbacks ------* #
	# *--------------------------------* #
    def save_GUI_settings(self, ) -> None:

        self.GUI_settings = QSettings()

        self.GUI_settings.setValue("window_pos", self.pos())
        self.GUI_settings.setValue("window_size", self.size())

        for key, widget in self.settings_pane_widgets.items():
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                self.GUI_settings.setValue(key, widget.value())
            elif isinstance(widget, QComboBox):
                self.GUI_settings.setValue(key, widget.currentText())
            elif isinstance(widget, QLineEdit):
                self.GUI_settings.setValue(key, widget.text())
            elif isinstance(widget, QCheckBox):
                self.GUI_settings.setValue(key, widget.isChecked())

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def read_GUI_settings(self, ) -> None:
        """
        Reads and applies GUI settings / config using `QSettings`. \\
        Compatible for using resdep as a module, stores settings in OS specific system directories (*e.g.* `etc\\`, registry) 
        """
        self.GUI_settings = QSettings()

        window_pos = self.GUI_settings.value("window_pos")
        window_size = self.GUI_settings.value("window_size")
        if isinstance(window_pos, QPoint):
            self.move(window_pos)
        if isinstance(window_size, QSize):
            self.resize(window_size)

        for key, widget in self.settings_pane_widgets.items():
            value: Any = self.GUI_settings.value(key, defaultValue=None) # should be type: int | float | str
            if value is None:
                continue
            try:
                if isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value)) # for some reason, QDoubleSpinBox saves in QSettings as str, not float.
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))

            except Exception:
                logging.error(traceback.format_exc())

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def save_experiment_settings_to_json(self, path: Union[Path, None] = None) -> None:

        try:
            # add to dict
            settings_pane_config: dict[str, Union[str, int, float]] = {}
            for key, widget in self.settings_pane_widgets.items():
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    settings_pane_config[key] = widget.value()
                elif isinstance(widget, QComboBox):
                    settings_pane_config[key] = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    settings_pane_config[key] = widget.text()
                elif isinstance(widget, QCheckBox):
                    settings_pane_config[key] = widget.isChecked()

            # save to file
            if not path:
                path = self.config_path
            with open(path / "settings_pane.json", "w") as f:
                json.dump(settings_pane_config, f)

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(
            self,
            "Error",
            "Failed to save experiment settings?."
            )

        return None
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

        if self.checkbox_measure_MX3.isChecked():
            self.resdep._measuring_MX3 = True
        else:
            self.resdep._measuring_MX3 = False
            
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
        self.graph.axes.clear()
        self.plotting.plot_expected_resonances()

        return None

    # *--------------------------------* #
	# *------ Button Callbacks --------* #
	# *--------------------------------* #
    def load_default_settings(self, ) -> None:

        default_values: dict[str, Any] = {
            "kicker_amp"        : 0,
            "harmonic"          : 1,
            "bounds"            : 0.05,
            "freq_shift"        : 0,
            "sweep_direction"   : "Forward",
            "sweep_rate"        : 10,
            "sweep_step_size"   : 0.5,
            "drive_pattern"     : "36:215",
            "ADC_offset_1"      : 0,
            "ADC_window_1"      : 42,
            "ADC_offset_2"      : 42,
            "ADC_window_2"      : 44,
            "_measure_MX3"      : False
        }

        for key, widget in self.settings_pane_widgets.items():
            try:
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(default_values[key])
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(default_values[key])
                elif isinstance(widget, QLineEdit):
                    widget.setText(default_values[key])
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(default_values[key])
            
            except Exception:
                logging.error(traceback.format_exc())

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def load_experiment_settings_from_json(self,) -> None:
        """
        load experiment settings config (loads into settings pane) - spawns file dialog window
        """
        filename, _ = QFileDialog.getOpenFileName(
            dir="Data", 
            filter="All Files (*);; JSON (*.json);; settings config (settings_pane.json)", 
            selectedFilter="settings config (settings_pane.json)"
            )

        if len(filename) > 0:
            self.status_bar.showMessage("Status: loading...")
            
            with open(Path(filename), "r") as f:
                settings_pane_config = json.load(f)

            for key, widget in self.settings_pane_widgets.items():
                try:
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(settings_pane_config[key])
                    elif isinstance(widget, QComboBox):
                        widget.setCurrentText(settings_pane_config[key])
                    elif isinstance(widget, QLineEdit):
                        widget.setText(settings_pane_config[key])
                    if isinstance(widget, QCheckBox):
                        widget.setChecked(settings_pane_config[key])
                
                except Exception:
                    logging.error(traceback.format_exc())

            self.status_bar.showMessage("Status: Ready")
        
        return None
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
    def do_fit(self, ) -> None:
        """
        Performs error function fit to experiment data within xlim of interactive plot for all selected sectors
        """
        self.status_bar.showMessage("Status: Fitting...")

        checked_sector_checkboxes = cast(list[bool], [sector_checkbox.isChecked() for sector_checkbox in self.sector_checkboxes])
        self.sectors_to_fit = [_sector for _sector, checked in zip(self.sectors, checked_sector_checkboxes) if checked]

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
        
        try: 
            self.plotting.calculate_fitting_mask()
            self.on_new_plot_info()
            y_model, _, _, fit_results = self.fitting.fit_error_functions()

            if len(y_model) == 0: # if all fits fail
                print("Fit results:\n", fit_results)
                return None

            if len(self.sectors_to_fit) > 1: # calc stddev of means if multiple fits
                _, _, E0_mean_sigfig, E0_stddev_sigfig = self.fitting.calculate_fitted_energy_stats() 
            else: # use stddev of fit if only one fit
                _, _, E0_mean_sigfig, E0_stddev_sigfig = self.fitting.calculate_fitted_energy_stats() 

            self.plotting.plot_fits()
            
            fitted_beam_energy_str = f"{E0_mean_sigfig} GeV" + u" \u00B1 " + f"{E0_stddev_sigfig*1e6:.0f} keV"
            print(f"mean E0 = {fitted_beam_energy_str}")
            print("Fit results:\n", fit_results)
            # update GUI
            self.fitted_beam_energy_label.setText(fitted_beam_energy_str)
            self.fit_results_label.setText(fit_results)
        
        finally:
            self.status_bar.showMessage("Status: Ready")

    
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def load_finished_experiment_data(self, ) -> None:
        """
        Loads finished experiment data (freqs, beam_loss) from folder, refreshes plot() for do_fit()
        """
        path = QFileDialog.getExistingDirectory(
            dir=str(self.current_path / "data" / "resdep"),
            options=QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
            )
        
        if len(path) > 0:
            # # convert path to os format
            # # Windows
            # if platform.system() == "Windows":
            #     path = path.replace(posixpath.sep, os.sep)
            # # Linux and MacOS
            # else:
            #     path = path.replace(ntpath.sep, os.sep)
            path = Path(path)
            # load freqs txt
            with open(path / "freqs.txt", "r") as f:
                for line in f.readlines():
                    self.resdep.freqs.append(float(line))	# Hz -> kHz
            # load beam loss windows
            with open(path / "adc_counter_loss_1.json", "r") as f:
                self.resdep.beam_loss_window_1 = json.load(f)
            with open(path / "adc_counter_loss_2.json", "r") as f:
                self.resdep.beam_loss_window_2 = json.load(f)
            # load res_freq as guess for fit
            with open(path / "metadata.json", "r") as f:
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
            self.on_new_plot_info()

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
        self.button_finished_experiment_data.setEnabled(True)
        
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
            for key, widget in self.settings_pane_widgets.items():
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
            
            self.save_GUI_settings()
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
    data_path = Signal(Path)
    start_timer = Signal()
    ADC_windows = Signal(list, str) # ADC windows, depolarised bunches
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
        self.worker.ADC_windows_callback = self._emit_new_ADC_windows

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
    def _emit_data_path(self, data_path: Path) -> None:
        self.data_path.emit(data_path)
        return None
    # ------------------------------------------------------------------------------
    def _emit_start_timer(self, ) -> None:
        self.start_timer.emit()
        return None
    # ------------------------------------------------------------------------------
    def _emit_new_ADC_windows(self, ADC_windows: list[int], depolarised_bunches: str) -> None:
        self.ADC_windows.emit(ADC_windows, depolarised_bunches)
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


def spawn():
    app = QApplication(sys.argv)
    window = MainWindow()
    if hasattr(sys, "ps1"): # interactive check
        app.exec()
    else:
        sys.exit(app.exec())

# run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())