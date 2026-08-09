#!/usr/bin/env python3
"""
Barebones Qt layout for running resdep experiments.
One button to enable automatic scans during user beam.
Has two manual buttons: "normal scan" and "wide scan"
"""
"""
███████╗██╗███╗   ███╗██████╗ ██╗     ███████╗     ██████╗ ██╗   ██╗██╗
██╔════╝██║████╗ ████║██╔══██╗██║     ██╔════╝    ██╔════╝ ██║   ██║██║
███████╗██║██╔████╔██║██████╔╝██║     █████╗      ██║  ███╗██║   ██║██║
╚════██║██║██║╚██╔╝██║██╔═══╝ ██║     ██╔══╝      ██║   ██║██║   ██║██║
███████║██║██║ ╚═╝ ██║██║     ███████╗███████╗    ╚██████╔╝╚██████╔╝██║
╚══════╝╚═╝╚═╝     ╚═╝╚═╝     ╚══════╝╚══════╝     ╚═════╝  ╚═════╝ ╚═╝
"""     

from enum import Enum, IntEnum
import datetime
import time
from typing import Literal, Union, Optional
import sys
import os
from pathlib import Path
import logging
import traceback
import subprocess
import platform
import numpy as np
import epics

# Qt
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QProgressBar,
    QPushButton,
    QLabel,
    QStatusBar,
    QStyle,
    QFrame,
    QMessageBox,
    QCheckBox,
    QDoubleSpinBox,
    QProgressDialog,
)
from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QObject,
    Signal,
    QTimer,
    QCoreApplication,
)

# resdep
from resdep.experiment import ProcessedData, ResonantDepolarisation
from resdep._fitting import Fitter
from resdep._archiver import (
        check_recent_beam_injection, check_recent_wiggler_ramp
)

class BeamMode(IntEnum):
    SHUT_DOWN = 1
    MAINTENANCE = 2
    MACHINE_STUDIES = 3
    USER_BEAM_DECAY = 8
    USER_BEAM_TOP_UP = 9
    USER_BEAM_EXOTIC = 10

class ScanType(Enum):
    AUTOMATIC = 0
    NORMAL = 1
    WIDE = 2

class MainWindow(QWidget):
    """
    The simple Qt GUI for Resonant Depolarisation.
    Pre-configured scan options. Has automatic scanning and data analysis.
    For full control, spawn resdepGUI instead.

    Dependencies
    ------------
    1. from [`resdep.experiment`][]
        1. [`ResonantDepolarisation`][resdep.experiment.ResonantDepolarisation]
        2. [`ProcessedData`][resdep.experiment.ProcessedData]
    2. from [`resdep._fitting`][]
        1. [`Fitter`][resdep._fitting.Fitter]

    Examples
    --------

    ```py title="Python"
    from resdep import simpleGUI
    simpleGUI.spawn()
    ```

    ```bash title="Command Line"
    >>> ipython3 -m resdep.simpleGUI
    ```

    """         

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print(
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⡀⠄⢀⠀⠀⠀⠀⠀⠀⠐⡀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠲⡀⠀⠀⠠⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠠⠑⢈⠐⠀⡀⠄⢀⡀⢀⠀⠁⠈⠀⠐⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠐⠀⢉⠀⠀⠀⠀⠀⠀⠀⠂⠉⡄⠀⠠⠁⠘⠄⡂⢁⠀⡀⠀⠀⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠂⠠⠀⠠⠁⡐⠀⠀⠂⠀⠀⠁⠀⠀⠃⠄⠈⠂⠡⢄⠂⠐⠀⠂⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠰⠀⠀⠀⠙⢦⡀⠀⠐⠀⠀⠀⠀⠀⠂⠌⠀⠁⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠐⠀⠀⠀⠹⡮⠲⢔⣤⣤⡀⠀⠀⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠈⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠳⣶⣿⣿⣿⣿⣷⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠢⡀⠀⠀⠀⠀⠠⠀⠀⠀⡀⢄⢦⡝⢿⣿⣿⣿⣿⣿⣿⡿⠷⠖⠀⠐⠀⠀⠒⠤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⢤⣀⠀⠀⠀⠀⢄⡻⡟⠘⢼⣼⣿⣿⣿⣿⠿⠛⠀⠀⠀⡀⣀⣤⣿⣤⣤⣀⡀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠷⣶⡦⠔⠮⡟⠾⢶⣿⣿⡿⠛⠉⢀⠀⣀⣤⣲⣿⣿⣿⣿⣿⣿⣿⣿⣿⣡⡄⠀⢀⠢⢁⣟⣦⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡈⠛⢟⡿⠿⢧⣾⢝⡩⠂⣁⣤⣷⢿⣫⣿⣿⢿⣿⣿⣿⣿⣿⣷⣿⣿⡿⠆⠀⢸⠠⢿⢿⡯⣿⢷⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠘⢿⣶⣶⣤⣤⣴⣠⣤⣄⡉⣤⡘⠚⢈⡃⢩⣪⣿⣿⣟⣵⣿⣿⣿⣷⣿⣿⣿⣿⣿⡿⢦⣔⢒⣽⣿⡉⣋⣿⣽⣾⢒⡿⡛⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⠈⠹⣿⣿⣿⣿⣿⣿⣿⣿⣾⣷⣾⣰⢲⣾⣿⣯⣾⣿⣿⣿⣿⡟⣥⢷⣶⣻⣿⣽⣾⣿⡇⠐⠻⠿⠿⠿⠿⠿⠁⠀⠟⠻⠙⣷⠆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⡀⠀\n",
            "⣄⠀⠄⣀⠂⠐⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⢫⣾⣷⡟⠿⣿⣿⠿⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠂\n",
            "⣿⣷⣴⣈⣻⣜⣘⡽⣮⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢣⣿⣿⣿⣿⠀⠈⠀⠀⠀⠀⠀⠀⠀⠰⢲⣶⣶⣶⣾⣷⣾⣶⠀⠀⠀⣰⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⡿⣿⡿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⡟⣾⡕⣝⣱⡏⠆⢐⡼⢿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⠀⠀⣀⠀⠀⠀⠁⠀⠄⠀⠀⢀⠀⢸⡟⠾⠯⠙⠻⡔⢰⣣⣾⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡕⠀⣼⣟⠰⠀⠀⠀⠀⠀⢀⣀⣠⣠⣀⠀⠶⣶⡶⣄⣀⢳⣯⢯⡹⣏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⣡⢠⣟⣛⣶⡂⠀⢰⣧⣼⣧⣀⠘⣷⢚⣻⣤⣿⣾⣿⣫⣻⣿⢌⣇⠌⠀⠀⠀⠀⠀⠀⠀⠀⣤⠀⠀⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣷⣶⣿⣿⣿⣿⣦⣸⣿⣿⣿⣿⣶⣾⣿⣻⡟⣼⣮⣻⠿⢹⢻⡞⡘⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠀⠀⠀⠀\n",
            "⣿⡛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣻⣟⣿⣿⣖⢓⣱⡕⢟⡵⠛⠲⠁⠀⠀⠀⠀⠀⠄⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠛⠀⠈⠻⠿⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣮⣳⣿⡙⢹⣿⣷⣧⠽⠉⠡⡒⠅⡀⠀⠀⠀⠀⠈⠀⠀⠀⠀⢀⠀⠀⠀⠀\n",
            "⠀⠄⠀⠀⠀⠠⣬⣍⠉⢽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⣻⣟⠻⢿⣷⠤⢄⣀⡤⠒⠁⠐⡠⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n",
            "⠀⠀⠀⢐⡄⢀⣫⣷⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣲⢶⣒⣂⣡⡴⢻⠅⠶⢊⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡆⠀\n",
            "⠐⠂⠃⢠⣴⣯⡟⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⠘⠒⠈⢩⣥⣬⠀⠐⠐⢩⠀⠀⠀⠀⠂⠀⠀⠀⠀⠀⠀⠀⢠⠁⠀\n",
            "⢂⣤⠲⢚⡵⢋⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣲⢫⣬⡬⣭⢖⡶⡏⣞⡼⠁⠀⠀⠀⠀⠀⠐⠀⠀⠀⡸⠀⠀\n",
            "⣳⣈⢨⢕⣽⣟⣻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣹⣿⣿⣿⣿⣶⣿⣶⣿⣿⣿⠟⢀⡄⠀⠄⠀⠂⠔⠀⠀⠀⢀⠃⠀⠀\n",
            "⣿⣿⣆⡚⢿⣿⣞⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⡫⣐⣜⠵⠢⢂⠠⠀⠁⠀⠀⠀⢀⠎⠀⠀⠀\n",
            "⣿⣿⣿⣿⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣫⡽⠟⠻⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣯⣴⡚⢛⠒⠀⡀⣀⣠⠥⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀\n",
            "⣿⣿⣿⡿⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣝⣻⣿⣿⣄⠐⣶⣤⡤⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣾⣿⣶⠿⡛⠃⢀⠄⠀⠐⠀⠄⠀⠀⠀⠀⠀⢠\n",
            "⣿⣿⣿⣿⣿⣿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⢀⡈⠳⢿⡿⠟⣡⣿⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣛⠛⠿⠯⠾⢛⣁⣠⣲⠀⢀⠁⠀⠀⠀⠀⠀⠀⢀⡴⠁\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⣴⣾⣿⣶⣦⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣭⣀⣦⢨⣉⣥⣋⡤⠀⠂⠀⠀⠀⣀⠔⠋⠀⠀\n",
            "⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⠿⣻⢁⣧⣔⠦⠀⠀⠈⠀⠀⠀⠀⠀\n",
            "R  E  S  O  N  A  N  T     D  E  P  O  L  A  R  I  S  A  T  I  O  N ",
        )

        # perpetual GUI settings
        QCoreApplication.setOrganizationName("Physics")
        QCoreApplication.setApplicationName("Resonant Depolarisation (simple)")

        #--------------------------------------- Resonant Depolarisation module
        # import
        self.resdep = ResonantDepolarisation()
        # define thread for resdep
        self.thread_manager = QThreadPool()
        # decorate resdep
        self.resdepQt = QtWorkerDecorator(self.resdep)
        # Connect emitted signals from worker (wrapped resdep)
        # to GUI update (member) functions (slots)
        self.resdepQt.progress.connect(self.on_progress_update)
        self.resdepQt.status.connect(self.on_status_update)
        self.resdepQt.data_path.connect(self.on_data_path_update)
        self.resdepQt.finished.connect(self.on_finish)

        # helper classes
        self.processed_data = ProcessedData(resdep=self.resdep)
        self.fitter = Fitter(
            resdep=self.resdep, processed_data=self.processed_data
        )

        # init window
        self.setWindowTitle("Resonant Depolarisation")
        self.setMinimumWidth(400)
        mainwindow_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_TitleBarMenuButton
        )
        self.setWindowIcon(mainwindow_icon)

        # create an layout for the whole window
        # ┌──────────────────────────────────────────┐
        # │          RESONANT DEPOLARISATION         │
        # │   ┌───────────────┐     ┌─────────────┐  │
        # │   │   Energy PV   │     │  Automatic  │  │
        # │   └───────────────┘     │             │  │
        # │                         │ ┌─────────┐ │  │
        # │   ┌───────────────┐     │ │ Enable  │ │  │
        # │   │ Countdown     │     │ └─────────┘ │  │
        # │   │ to next scan  │     └─────────────┘  │
        # │   └───────────────┘     ┌─────────────┐  │
        # │                         │   Manual    │  │
        # │   ┌───────────────┐     │┌───────────┐│  │
        # │   │               │     ││Normal Scan││  │
        # │   │ Other stats?  │     │└───────────┘│  │
        # │   │               │     │┌───────────┐│  │
        # │   │               │     ││Wide Search││  │
        # │   └───────────────┘     │└───────────┘│  │
        # │                         └─────────────┘  │
        # │                               Progress   │
        # │ ┌──────────────────────────────────────┐ │
        # │ └──────────────────────────────────────┘ │
        # │ Status:                                  │
        # └──────────────────────────────────────────┘

        main_window_layout = QVBoxLayout()
        self.setLayout(main_window_layout)

        #--------------------------------------------------- app title / banner
        self.app_title = QLabel("Resonant Depolarisation")
        self.app_title.setStyleSheet(
            """
            background-color: transparent;
            font-size: 42px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 2px;
            """
        )
        self.app_subtitle = QLabel("beam energy diagnostic")
        self.app_subtitle.setStyleSheet(
            """
            background-color: transparent;
            font-size: 16px;
            font-weight: 500;
            letter-spacing: 1px;
            """
        )

        #--------------- top panel (results / stats LHS (first place you look))
        # (buttons / control RHS)
        top_panel = QWidget(self)
        top_panel_layout = QHBoxLayout()
        top_panel.setLayout(top_panel_layout)

        self._init_results_panel()
        self._init_control_panel()

        # add everything to top panel
        top_panel_layout.addWidget(self.results_panel_frame)
        top_panel_layout.addWidget(self.control_panel)

        #----------------------------------------------------------- status bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(self.resdep.sweep_steps)

        # status bar -------------------------------- #
        self.status_bar = QStatusBar()
        self.on_status_update("Ready")

        # add everything to window
        main_window_layout.addWidget(
            self.app_title, alignment=Qt.AlignmentFlag.AlignCenter
        )
        main_window_layout.addWidget(
            self.app_subtitle, alignment=Qt.AlignmentFlag.AlignCenter
        )
        main_window_layout.addWidget(top_panel)
        main_window_layout.addWidget(self.progress_bar)
        main_window_layout.addWidget(self.status_bar)

        # background logic
        self._load_state_PVs()
        self._running_experiment = False
        self.automatic_scan_timer = QTimer(self)
        self.automatic_scan_timer.setInterval(1000)
        self.automatic_scan_timer.timeout.connect(
            self._update_automatic_scan_timer
        )

        self._config_logger()

        self.show()

    # *--------------------------------* #
    # *---------- GUI Layout ----------* #
    # *--------------------------------* #
    def _init_results_panel(
        self,
    ) -> None:
        """
        Results panel, LHS of GUI.
        Lists beam energy, fit stats, repolarisation time, etc.
        """
        # icons
        dir_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        #------------------------------------------------ results / stats panel
        results_panel_layout = QVBoxLayout()
        # frame around manual button
        self.results_panel_frame = QFrame(self)
        self.results_panel_frame.setFrameShape(QFrame.Shape.Panel)
        self.results_panel_frame.setLayout(results_panel_layout)

        # Results label / header
        results_panel_header = QLabel("Results")
        results_panel_header.setStyleSheet(
            """
            font-size: 16px;
            font-weight: 900;
            """
        )

        results_form = QWidget()
        results_form_layout = QFormLayout()
        results_form.setLayout(results_form_layout)

        self.beam_energy_label = QLabel()
        self.repolarisation_time_elapsed_label = QLabel()
        self.polarisation_label = QLabel()

        self.polarisation: float = 100  # %
        self.repolarisation_time_elapsed: int = (
            0  # seconds. 3 tpol -> 39 minutes (88 %)
        )
        self.repolarisation_time_elapsed_label = QLabel("")
        self.repolarisation_timer = QTimer(self)
        self.repolarisation_timer.setInterval(1000)
        self.repolarisation_timer.timeout.connect(
            self._update_repolarisation_time
        )

        self.automatic_scan_countdown_label = QLabel("")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:red")
        self.error_label.setWordWrap(True)

        results_form_layout.addRow("Beam Energy:", self.beam_energy_label)
        results_form_layout.addRow(
            "Repolarisation time:", self.repolarisation_time_elapsed_label
        )
        results_form_layout.addRow("Polarisation:", self.polarisation_label)
        results_form_layout.addRow(
            "Next scan in:", self.automatic_scan_countdown_label
        )
        results_form_layout.addRow("Errors:", self.error_label)

        # temporary data path
        self.data_path = Path.cwd()
        hostname = platform.node()
        try:
            hostname.index("OPI")
            self.data_path = Path("/asp/usr/data/resdep")
        except ValueError:  # not running on AS OPI
            Path.mkdir(
                self.data_path / "GUI_log", exist_ok=True
            )  # does not wipe the dir if it exists, just continues

        self.logfile_path = Path(self.data_path / "GUI_log")

        self.button_data_path = QPushButton("Data")
        self.button_data_path.setIcon(dir_icon)
        # button callbacks
        self.button_data_path.clicked.connect(self.open_data_path)

        results_panel_layout.addWidget(
            results_panel_header, alignment=Qt.AlignmentFlag.AlignCenter
        )
        results_panel_layout.addWidget(results_form)
        results_panel_layout.addStretch()
        results_panel_layout.addWidget(self.button_data_path)

        return None
    #--------------------------------------------------------------------------
    def _init_control_panel(
        self,
    ) -> None:
        """
        Control panel, RHS of GUI.
        Contains buttons for automatic operation, and manual (normal / long) scans
        """
        # buttons / control panel
        self.control_panel = QWidget(self)
        control_panel_layout = QVBoxLayout()
        self.control_panel.setLayout(control_panel_layout)

        #----------------------------------------------- Automatic button panel
        automatic_button_panel_layout = QVBoxLayout()
        # frame around automatic button
        automatic_button_panel_frame = QFrame(self)
        automatic_button_panel_frame.setFrameShape(QFrame.Shape.Panel)
        automatic_button_panel_frame.setLayout(automatic_button_panel_layout)

        # Automatic label / header
        automatic_button_header = QLabel("Automatic")
        automatic_button_header.setStyleSheet(
            """
            font-size: 16px;
            font-weight: 900;
            """
        )

        # automatic button
        self.button_automatic = QPushButton("Disabled")
        self.button_automatic.setCheckable(True)
        self.button_automatic.setChecked(False)

        # time between scans (input)
        automatic_form = QWidget()
        automatic_form_layout = QFormLayout()
        automatic_form.setLayout(automatic_form_layout)
        self.time_between_automatic_scans = QDoubleSpinBox(
            minimum=1, value=2, singleStep=0.1, decimals=2, suffix=" hours"
        )
        automatic_form_layout.addRow(
            "Time between scans:\n(end to start)",
            self.time_between_automatic_scans,
        )

        # add to panel
        automatic_button_panel_layout.addWidget(
            automatic_button_header, alignment=Qt.AlignmentFlag.AlignCenter
        )
        automatic_button_panel_layout.addWidget(self.button_automatic)
        automatic_button_panel_layout.addWidget(automatic_form)

        #-------------------------------------------------- manual button panel
        manual_button_panel_layout = QVBoxLayout()
        # frame around manual button
        manual_button_panel_frame = QFrame()
        manual_button_panel_frame.setFrameShape(QFrame.Shape.Panel)
        manual_button_panel_frame.setLayout(manual_button_panel_layout)

        # Manual label / header
        manual_button_header = QLabel("Manual")
        manual_button_header.setStyleSheet(
            """
            font-size: 16px;
            font-weight: 900;
            """
        )

        # manual buttons
        self.button_manual_normal_scan = QPushButton("Normal Scan")
        self.button_manual_wide_search = QPushButton("Wide Search")

        # button callbacks
        self.button_automatic.clicked.connect(self._on_automatic_scan_clicked)
        self.button_manual_normal_scan.clicked.connect(
            self._on_normal_scan_clicked
        )
        self.button_manual_wide_search.clicked.connect(
            self._on_wide_search_clicked
        )

        # machine studies mode (override checks) checkbox
        self.checkbox_machine_studies = QCheckBox("Machine Studies")
        self.checkbox_machine_state_override = QCheckBox(
            "Override machine state checks"
        )

        # add to manual panel
        manual_button_panel_layout.addWidget(
            manual_button_header, alignment=Qt.AlignmentFlag.AlignCenter
        )
        manual_button_panel_layout.addWidget(self.button_manual_normal_scan)
        manual_button_panel_layout.addWidget(self.button_manual_wide_search)
        manual_button_panel_layout.addWidget(
            self.checkbox_machine_studies,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        manual_button_panel_layout.addWidget(
            self.checkbox_machine_state_override,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        # abort button
        self.button_abort = QPushButton("ABORT!")
        self.button_abort.setFixedSize(100, 60)
        # self.button_abort.setStyleSheet(
        #   "QPushButton {background-color: red;}"
        # )
        self.button_abort.setEnabled(False)
        self.button_abort.clicked.connect(self.abort)

        # add everything to control panel
        control_panel_layout.addWidget(automatic_button_panel_frame)
        control_panel_layout.addSpacing(50)
        control_panel_layout.addWidget(manual_button_panel_frame)
        control_panel_layout.addWidget(
            self.button_abort, alignment=Qt.AlignmentFlag.AlignCenter
        )

        return None
    #--------------------------------------------------------------------------
    def _config_logger(
        self,
    ) -> None:
        """
        Configure the logger to write to console and logfile
        """
        self.start_time: datetime.datetime = datetime.datetime.now()
        date: str = self.start_time.strftime("%Y-%m-%d")
        hours: str = self.start_time.strftime("%H%Mh")
        seconds: str = self.start_time.strftime("%Ss")
        filename: str = f"logfile_{date}_{hours}-{seconds}.log"
    
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # create file handler which logs even debug messages
        file_handler = logging.FileHandler(
                filename=self.logfile_path/filename
        )
        file_handler.setLevel(logging.DEBUG)
        # create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        # add the handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.debug(self.start_time)
        self.logger.debug("--- simpleGUI starting up ---")

        return None
    #--------------------------------------------------------------------------
    def _enable_abort_button(self, enable: bool = True) -> None:
        """
        Enables / disables abort button and changes color to red 
        when experiment is running or automatic scans enabled.
        """
        if enable:
            self.button_abort.setEnabled(True)
            self.button_abort.setStyleSheet(
                "QPushButton {background-color: red;}"
            )
        else:
            self.button_abort.setEnabled(False)
            self.button_abort.setStyleSheet(
                "QPushButton {background-color: none;}"
            )
        return None
    #--------------------------------------------------------------------------
    def _disable_abort_button(
        self,
    ) -> None:
        """
        Alias for `_enable_abort_button(enable=False)`
        """
        self._enable_abort_button(enable=False)
        return None
    #--------------------------------------------------------------------------
    def _enable_control_panel(self, enable: bool = True) -> None:
        self.button_manual_normal_scan.setEnabled(enable)
        self.button_manual_wide_search.setEnabled(enable)
        # if you run a manual scan, the automatic button will be disabled.
        # but this function will always enable/re-enable it if enable==True
        if not self._automatic_scan_enabled and enable == False:
            self.button_automatic.setEnabled(enable)
        self.checkbox_machine_studies.setEnabled(enable)
        self.checkbox_machine_state_override.setEnabled(enable)
        return None
    def _disable_control_panel(self) -> None:
    #--------------------------------------------------------------------------
        self._enable_control_panel(enable=False)
        return None
    # *--------------------------------* #
    # *---------- Experiment ----------* #
    # *--------------------------------* #
    def run_experiment(
        self,
    ) -> None:
        """
        Executes the resdep experiment in a separate thread.
        resdep is wrapped in a worker class that attaches 
        emitted progress, status, and plot updates (info)
        """

        # disable appropriate buttons
        #
        #
        # enable abort button (and turn red)
        self._abort_requested: bool = False
        # enable / disable buttons
        self._enable_abort_button()
        self._disable_control_panel()
        # update status bar
        self.on_status_update("Starting up...")

        # update progress bar
        self.resdep._calculate_range()
        self.progress_bar.setMaximum(self.resdep.sweep_steps)

        # call resdep
        self._running_experiment: bool = True
        self.thread_manager.start(self.resdepQt.run)

        return None
    #--------------------------------------------------------------------------
    def on_progress_update(self, step: int) -> None:
        """
        Simply update the value of the progress bar.
        Uses emitted signal from resdep (worker wrapper)
        """
        self.progress_bar.setValue(step)

        return None
    #--------------------------------------------------------------------------
    def on_status_update(self, message: str) -> None:
        """
        Updates the GUI statues 
        (primarily from running to sleeping on injection)
        """
        self.status_bar.showMessage(f"Status: {message}")
        return None
    #--------------------------------------------------------------------------
    def on_data_path_update(self, data_path: Path) -> None:
        """
        Assign data path from resdep to GUI button.
        """
        self.data_path = data_path
        self.button_data_path.setEnabled(True)

        return None
    #--------------------------------------------------------------------------
    def on_finish(
        self,
    ) -> None:
        """
        Update states, buttons, progress bar. 
        Perform data analysis (automagic fit).
        Write fit results to GUI (and PV?).
        Start timers for repolarisation and countdown to next scan 
        (if automatic scans enabled).
        """
        self.logger.debug("Scan finished.")
        self.on_status_update(
            "Experiment finished. Performing data analysis..."
        )

        # reset state
        self._running_experiment: bool = False

        self._disable_abort_button()
        self._enable_control_panel()

        # make sure progress bar reads 100%
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)

        if (not self._abort_requested) and (self.resdep._has_stored_data):
            self.fit_beam_energy()

        # Timer things
        # self.timer.stop()
        self.repolarisation_time_elapsed: int = 0
        self.repolarisation_timer.start()
        if self._automatic_scan_enabled:
            self._start_automatic_scan_countdown()
            self.on_status_update("Waiting for next automatic scan...")
        else:
            self.on_status_update("Ready")

        if self._abort_requested:
            self._abort_requested = False

        return None
    #--------------------------------------------------------------------------
    def _start_automatic_scan_countdown(
        self,
    ) -> None:
        # update countdown duration from GUI input
        self.automatic_scan_countdown: int = int(
            self.time_between_automatic_scans.value() * 3600
        )
        self.automatic_scan_timer.start()
        return None
    #--------------------------------------------------------------------------
    def _update_automatic_scan_timer(
        self,
    ) -> None:
        """
        Use QTimer to countdown and trigger the next automatic scan.
        """
        self.automatic_scan_countdown += -1
        self.automatic_scan_countdown_label.setText(
            f"{datetime.timedelta(seconds=self.automatic_scan_countdown)}"
        )

        if not self._automatic_scan_enabled:
            self.automatic_scan_timer.stop()
            self.automatic_scan_countdown_label.setText("")

        elif self.automatic_scan_countdown <= 0:
            self.automatic_scan_timer.stop()
            self.automatic_scan()

        return None
    #--------------------------------------------------------------------------
    def _update_repolarisation_time(
        self,
    ) -> None:
        """
        Calculate time spent repolarising the beam after experiment end. 
        Ideal wait time: (3 tpol, 39 min, 88%).
        Calculate estimate of polarisation 
        (assuming fully depolarised at the end of the experiment).
        Stop after enough time (~2 hours)
        """
        self.repolarisation_time_elapsed += 1
        repolarisation_timedelta: datetime.timedelta = datetime.timedelta(
                seconds=self.repolarisation_time_elapsed
        )
        self.repolarisation_time_elapsed_label.setText(
                f"{repolarisation_timedelta}" 
        )

        self.polarisation: float = 100 * (
                1 - np.exp(-self.repolarisation_time_elapsed / 779)
        ) # %
        self.polarisation_label.setText(f"{self.polarisation:0.2f}%")

        if self._running_experiment:
            self.repolarisation_timer.stop()
            self.repolarisation_time_elapsed_label.setText("")
            self.polarisation_label.setText("-> 0%")

        # stop after enough time
        if self.repolarisation_time_elapsed >= 7790:
            self.repolarisation_timer.stop()

        return None
    #--------------------------------------------------------------------------
    def fit_beam_energy(
        self,
    ) -> None:
        """
        Calls magic fitting functions from 
        [`_fitting`][resdep._fitting] to extract beam energy from data.
        """
        error: Optional[str] = None
        formatted_beam_energy: str = ""

        try:  # try block so GUI doesn't crash
            self.processed_data.calculate_ratio_loss()

            *_, formatted_beam_energy, error = self.fitter.automagic_fit()
            

        # Catch something critical that `automagic_fit()` does not handle
        except Exception:
            error: str = traceback.format_exc()
            self.logger.error(error)

        finally:
            # update GUI
            if error is not None:
                self.error_label.setText(error)
                return None

            self.beam_energy_label.setText(formatted_beam_energy)
            with open(self.data_path / "beam_energy.txt", "w") as f:
                f.write(formatted_beam_energy)
            if (self.data_path / "beam_energy.txt").exists():
                logging.debug("beam energy txt file saved successfully.")
            else:
                logging.debug("beam energy txt file not saved :(")
            # save processed data
            self.processed_data.save_data()

        # TODO: write to PV????
        # beam_energy_PV.put(E0_mean_sigfig)

        return None
    #--------------------------------------------------------------------------
    def _check_able_to_run(
        self, 
        scan_type: ScanType
        ) -> tuple[bool, Optional[str]]:
        """
        Check if the experiment can run based on the state of the machine.

        Parameters
        ----------
        scan_type: ScanType (enum)
            Automatic scans require the beam mode: "User Beam", 
            while manual scans do not.

        Returnm
        -------
        verdict: bool
            Answer to whether the experiment can run
        error: str
            Error message for why (specifically or first offending requirement) 
            the experiment cannot run.
            Displayed on the results panel.
        
        Requirements
        ------------
        1. More that 150 mA of beam current
        2. At least 95% beam polarisation
            1. Considers both time since recent injection 
                and last diagnostic scan
        3. Must be in "User Beam" if automatic scans are enabled
        """                 
        verdict: bool = False
        error: Optional[str] = None

        self.error_label.setText("")
        formatted_beam_modes: str = ""
        for mode in BeamMode:
            formatted_beam_modes += (
                    f"{mode.name} = {mode.value}\n"
            )

        if self.checkbox_machine_state_override.isChecked():
            verdict = True
            return verdict, error

        # If not connected/disconnected:
        # give PVs a chance to reconnect before state check logic
        for pv in self.machine_state_PVs.values():
            if not pv.connected:
                pv.connect(timeout=1)
                time.sleep(1)
            # if still not connected, fail
            if not pv.connected:
                error = (
                    f"{pv} refused to connect. Cannot determine machine state."
                )
                return False, error

        beam_mode_response: Union[int, None] = (
                self.beam_mode_PV.get(timeout=0.1)
        )
        current: Union[float, None] = self.current_PV.get(timeout=0.1)
        time.sleep(0.5)

        # if PVs return None, exit early
        if beam_mode_response is not None:
            beam_mode = BeamMode(beam_mode_response)
        else:
            error = (
                "beam_mode (FS01:BEAM_MODE_MONITOR) returned None." 
                + "Expected any of:\n" 
                + formatted_beam_modes
                + "Aborting request to run resdep."
            )
            return False, error

        if current is None:
            error = (
                "Current PV (DCCT) returned None.\n" 
                + "Aborting request to run resdep."
            )
            return False, error

        # NOTE: This check is depreciated due to unreliable RAMP_STATUS
        #       behaviour.
        # recent_wiggler_ramp: bool = check_recent_wiggler_ramp()
        # if recent_wiggler_ramp:
        #     error = (
        #             "Wiggler ramp initiated in the 40 minutes. "
        #             +"Require more time to repolarise / stabilise."
        #     )
        #     verdict = False
        #     return verdict, error

        # Assume can run, else check for errors
        is_user_beam: bool = any([
                beam_mode == BeamMode.USER_BEAM_DECAY,
                beam_mode == BeamMode.USER_BEAM_TOP_UP,
                beam_mode == BeamMode.USER_BEAM_EXOTIC
        ])

        if scan_type == ScanType.AUTOMATIC:
            scan_type_allowed: bool = any([
                    is_user_beam,
                    self.checkbox_machine_studies.isChecked()
            ])
        elif scan_type == ScanType.NORMAL or scan_type == ScanType.WIDE:
            scan_type_allowed: bool = True # manual scans can run anytime


        try:
            recent_beam_injection: bool = check_recent_beam_injection()
        except Exception:
            self.logger.error(traceback.format_exc())
            error = (
                    "Unable to check if there was a recent beam injection. "
                    +"This is probably due to an issue with the archiver. "
                    +"Check the GUI log (/asp/usr/data/resdep/GUI_log) "
                    +"for more info."
            )
            verdict = False
            return verdict, error

        if all(
                [
                    scan_type_allowed,
                    current >= 150, # mA. 
                    # More current = more resolution. 
                    # Should ideally run at 200 mA.
                    self.polarisation >= 95, # %
                    not recent_beam_injection,
                ]
            ):
            verdict = True
        elif current < 150: # mA
            error = (
                "Less than 150 mA beam current. " 
                + f"{current:0.0f} mA is not enough resolution for measurement. " 
                + "Aborting request to run resdep."
            )
            return False, error
        elif self.polarisation < 95:  # %
            error = (
                "Beam polarisation is less than 95%; not enough resolution. "
                + "Aborting request to run resdep."
            )
            return False, error
        elif recent_beam_injection:
            error = (
                "Beam has been injected too recently and has not have enough " 
                + "time to polarise (requires at least 39 minutes)."
            )
            return False, error
        elif all([
                scan_type == ScanType.AUTOMATIC,
                not is_user_beam,
                not self.checkbox_machine_studies.isChecked()
            ]):  # tried automatic scan but not user beam
            error = ("beam_mode (FS01:BEAM_MODE_MONITOR) returned " 
                     + f"{beam_mode.name}. " 
                     + "Expected any form of 'User Beam'. " 
                     + "Aborting request to run resdep.")
            return False, error

        return verdict, error
    # *--------------------------------* #
    # *---------- Scan Types ----------* #
    # *--------------------------------* #
    def automatic_scan(
        self,
    ) -> None:
        """
        Automatically runs resdep every hour+ using countdown timer.
        """
        able_to_run, error = self._check_able_to_run(
                scan_type=ScanType.AUTOMATIC
        )

        if able_to_run:
            self.logger.debug("Starting automatic scan...")
            self._apply_default_scan_settings()
            self.run_experiment()
        else:
            if error is not None:
                self.logger.error(error)
                self.error_label.setText(error)
            self._start_automatic_scan_countdown()

        return None
    #--------------------------------------------------------------------------
    def normal_scan(
        self,
    ) -> None:
        """
        Runs a typical beam energy scan. 
        No different to automatic_scan, just manually triggered.
        """

        able_to_run, error = self._check_able_to_run(
            scan_type=ScanType.NORMAL
        )

        if able_to_run:
            self.logger.debug("Starting normal scan...")
            self._apply_default_scan_settings()
            self.run_experiment()
        else:
            self.logger.error(error)
            QMessageBox.critical(self, "Error", f"{error}")

        return None
    #--------------------------------------------------------------------------
    def wide_search(
        self,
    ) -> None:
        """
        Runs a wide search for the beam energy.
        2 hour long scan, 0.35% of beam energy [3.02, 3.04] GeV.
        
        Warning
        -------
        If betatron tunes are off and within scan range, 
        kicker will drive tunes.
        """

        able_to_run, error = self._check_able_to_run(
            scan_type=ScanType.WIDE
        )

        if able_to_run:
            answer = QMessageBox.question(
                self,
                "Continue?",
                ("WARNING: May drive betatron tunes if they're REALLY FAR off.\n" 
                 +"DANGER ZONE: "
                 + "v_y = [0.097, 0.145] and v_y = [0.855, 0.903].\n" 
                 +"Continue?"
                 ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            # if yes
            if answer == QMessageBox.StandardButton.Yes:
                self.close()
                self.resdep.bounds = 0.35 / 100  # 2 hour scan
                self.resdep.sweep_rate = 10  # Hz/s
                self.logger.debug("Starting wide search...")
                self.run_experiment()
            else:
                self.close()

        else:
            self.logger.error(error)
            QMessageBox.critical(self, "Error", f"{error}")

        return None
    #--------------------------------------------------------------------------
    def _apply_default_scan_settings(
        self,
    ) -> None:
        """
        Default resdep scan settings for normal and automatic
        """
        self.resdep.bounds = 0.05 / 100  # input %, output decimal
        self.resdep.sweep_rate = 5  # Hz/s

    # *--------------------------------* #
    # *------ Button Callbacks --------* #
    # *--------------------------------* #
    def _on_automatic_scan_clicked(
        self,
    ) -> None:
        """
        Toggles states on button click.
        If enabled -> calls automatic_scan().
        If disabled -> stops countown, asks to abort experiment.
        """
        if self.button_automatic.isChecked():
            self.button_automatic.setText("Enabled")
            self.button_automatic.setStyleSheet(
                "QPushButton {background-color: orange;}"
            )
            self.on_status_update("Waiting for next automatic scan...")
            self._automatic_scan_enabled = True
            self._apply_default_scan_settings()
            self.automatic_scan()

        else:  # if unchecked (i.e. clicked to diable automatic scans)
            self.button_automatic.setText("Disabled")
            self.button_automatic.setStyleSheet(
                "QPushButton {background-color: none;}"
            )
            self._automatic_scan_enabled = False
            if self._running_experiment:
                answer = QMessageBox.question(
                    self,
                    "Abort experiment?",
                    "Diagnostic is still running. Do you want to abort it?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                )

                if answer == QMessageBox.StandardButton.Yes:
                    self.abort()
                    self._wait_for_abort_tasks()

                if answer == QMessageBox.StandardButton.No:
                    self.button_automatic.setEnabled(False)

            else:  # if experiment is not running
                self.on_status_update("Ready")

        return None
    #--------------------------------------------------------------------------
    def _on_normal_scan_clicked(
        self,
    ) -> None:
        """ """
        self.normal_scan()
        return None
    #--------------------------------------------------------------------------
    def _on_wide_search_clicked(
        self,
    ) -> None:
        """ """
        self.wide_search()
        return None
    #--------------------------------------------------------------------------
    def open_data_path(
        self,
    ) -> None:
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
    #--------------------------------------------------------------------------
    def abort(
        self,
    ) -> None:
        """
        Interrupts resdep experiment loop.
        """
        self.logger.critical("Abort requested!")
        self._disable_abort_button()
        self._abort_requested = True
        self.resdepQt.abort()

        return None
    #--------------------------------------------------------------------------
    def _wait_for_abort_tasks(self,) -> None:
        """
        Wait for resdep.experiment to finish, setting _running_experiment 
        to false, then hand back control to the user
        """
        self.dialog_wait_for_shutdown = QProgressDialog(
            parent=self, labelText="Waiting for experiment to shutdown"
        )
        self.dialog_wait_for_shutdown.setCancelButton(None)
        self.dialog_wait_for_shutdown.setMinimum(0)
        self.dialog_wait_for_shutdown.setMaximum(1)
        self.dialog_wait_for_shutdown.setWindowTitle("Please Wait")
        self.dialog_wait_for_shutdown.setWindowModality(
            Qt.WindowModality.ApplicationModal
        )
        self.dialog_wait_for_shutdown.show()
        while self._running_experiment:
            # pass control back to the application event loop
            time.sleep(0.05)
            QCoreApplication.processEvents()
        self.dialog_wait_for_shutdown.setValue(1)
        self.dialog_wait_for_shutdown.close()
        
        return None
    # *--------------------------------* #
    # *------------- EPICS ------------* #
    # *--------------------------------* #
    def _load_state_PVs(
        self,
    ) -> None:
        """
        Loads PVs that track the current state of the beam.
        These are used to determine whether resdep is allowed to run.
        Provides safeguards and automatic disabling of automatic scans.
        """
        #------------------------------------------------------------ Beam Mode

        self.beam_mode_PV: epics.pv.PV = epics.pv.get_pv(
            "FS01:BEAM_MODE_MONITOR", connect=True, timeout=1
        )
        self.current_PV: epics.pv.PV = epics.pv.get_pv(
            "SR11BCM01:CURRENT_MONITOR", connect=True, timeout=1
        )
        self.bioSAXS_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
                "SR02SCU01:RAMP_STATUS", connect=True, timeout=1
        )
        self.IMBL_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
                "SR08SCW01:FIELD_RAMPING_STATUS", connect=True, timeout=1
        )
        self.ADS_ramp_status_PV: epics.pv.PV = epics.pv.get_pv(
                "SR10SCW01:RAMP_STATUS", connect=True, timeout=1
        )
        self.machine_state_PVs: dict[str, epics.pv.PV] = {
            "beam_mode": self.beam_mode_PV,
            "current": self.current_PV,
            "bioSAXS_ramp_status": self.bioSAXS_ramp_status_PV,
            "IMBL_ramp_status": self.IMBL_ramp_status_PV,
            "ADS_ramp_status": self.ADS_ramp_status_PV,
        }
    # *--------------------------------* #
    # *----------- QT Config ----------* #
    # *--------------------------------* #
    def closeEvent(self, event) -> None:
        """
        Shutdown tasks for GUI. Abort scan if scanning. 
        Save shutdown time to log.
        """
        if self._running_experiment:
            self.abort()
            self._wait_for_abort_tasks()

        self.logger.debug("--- simpleGUI shutting down ---")
        shutdown_time: datetime.datetime = datetime.datetime.now()
        self.logger.debug(shutdown_time)

        self.close()
        event.accept()

        return None


class QtWorkerDecorator(QObject):
    """
    Qt wrapper for resonant depolarisation.
    Defines emitted signals and attaches them to the worker.
    The worker must contain these callbacks to emit signals.
    """

    # define emitted signals (from resdep)
    progress = Signal(int)  # step
    new_plot_info = Signal(list, dict, dict)
    status = Signal(str)  # status: message
    data_path = Signal(Path)
    start_timer = Signal()
    ADC_windows = Signal(list, str)  # ADC windows, depolarised bunches
    finished = Signal()
    #--------------------------------------------------------------------------
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
    #--------------------------------------------------------------------------
    def _emit_progress(self, step: int) -> None:
        self.progress.emit(step)
        return None
    #--------------------------------------------------------------------------
    def _emit_new_plot_info(
        self,
        freqs: list[float],
        beam_loss_window_1: dict[str, list[float]],
        beam_loss_window_2: dict[str, list[float]],
    ) -> None:
        self.new_plot_info.emit(freqs, beam_loss_window_1, beam_loss_window_2)
        return None
    #--------------------------------------------------------------------------
    def _emit_status(self, message: str) -> None:
        self.status.emit(message)
        return None
    #--------------------------------------------------------------------------
    def _emit_data_path(self, data_path: Path) -> None:
        self.data_path.emit(data_path)
        return None
    #--------------------------------------------------------------------------
    def _emit_start_timer(
        self,
    ) -> None:
        self.start_timer.emit()
        return None
    #--------------------------------------------------------------------------
    def _emit_new_ADC_windows(
        self, ADC_windows: list[int], depolarised_bunches: str
    ) -> None:
        self.ADC_windows.emit(ADC_windows, depolarised_bunches)
        return None
    #--------------------------------------------------------------------------
    def run(
        self,
    ) -> None:
        try:
            self.worker.start_experiment()
        finally:
            self.finished.emit()
        return None
    #--------------------------------------------------------------------------
    def abort(
        self,
    ) -> None:
        self.worker.request_abort()
        return None


def spawn():
    app = QApplication(sys.argv)
    MainWindow()
    if hasattr(sys, "ps1"):  # interactive check
        app.exec()
    else:
        sys.exit(app.exec())


# run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    if hasattr(sys, "ps1"):  # interactive check
        app.exec()
    else:
        sys.exit(app.exec())
