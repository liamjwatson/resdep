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

import datetime
import time
from typing import Literal, Union
import sys
import os
from pathlib import Path
import logging, warnings
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
    QDoubleSpinBox
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
from resdep._fitting import FittingClass
from resdep._archiver import check_for_recent_beam_injection



##########################
# -------- GUI --------- #
##########################
class MainWindow(QWidget):
    """
    The simple Qt GUI for Resonant Depolarisation \\
    Configuration for the experiment is hidden in the backend. For full control, spawn resdepGUI instead.


    :mod:`resdep`
    
    1. from :mod:`resdep.experiment`
        1. :class:`ResonantDepolarisation`
        2. :class:`ProcessedData`
    2. from :mod:`resdep._fitting`
        1. :class:`FittingClass()'
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print("⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⡀⠄⢀⠀⠀⠀⠀⠀⠀⠐⡀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠲⡀⠀⠀⠠⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠\n",
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
              " R  E  S  O  N  A  N  T     D  E  P  O  L  A  R  I  S  A  T  I  O  N ")

        # perpetual GUI settings
        QCoreApplication.setOrganizationName("Physics")
        QCoreApplication.setApplicationName("Resonant Depolarisation (simple)")

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
        self.resdepQt.status.connect(self.on_status_update)
        self.resdepQt.data_path.connect(self.on_data_path_update)
        self.resdepQt.finished.connect(self.on_finish)

        # helper classes
        sectors_to_fit = ["1", "4", "8", "11", "12", "13"]
        self.processed_data = ProcessedData(resdep=self.resdep, sectors_to_fit=sectors_to_fit)
        self.fitting        = FittingClass(resdep=self.resdep, processed_data=self.processed_data)

        # init window
        self.setWindowTitle("Resonant Depolarisation")
        self.setMinimumWidth(400)
        mainwindow_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton)
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

        # --- app title / banner
        self.app_title      = QLabel("Resonant Depolarisation")
        self.app_title.setStyleSheet(
            """
            background-color: transparent;
            font-size: 42px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 2px;
            """
        )
        self.app_subtitle   = QLabel("beam energy diagnostic")
        self.app_subtitle.setStyleSheet(
            """
            background-color: transparent;
            font-size: 16px;
            font-weight: 500;
            letter-spacing: 1px;
            """
        )

        # --- top panel (results / stats LHS (first place you look), buttons / control RHS)
        top_panel = QWidget(self)
        top_panel_layout = QHBoxLayout()
        top_panel.setLayout(top_panel_layout)

        self._init_results_panel()
        self._init_control_panel()

        # add everything to top panel
        top_panel_layout.addWidget(self.results_panel_frame)
        top_panel_layout.addWidget(self.control_panel)
        
        # --- status bar
        self.progress_bar = QProgressBar(self)

        # status bar -------------------------------- #
        self.status_bar = QStatusBar()
        self.on_status_update("Ready")

        # add everything to window
        main_window_layout.addWidget(self.app_title, alignment=Qt.AlignmentFlag.AlignCenter)
        main_window_layout.addWidget(self.app_subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        main_window_layout.addWidget(top_panel)
        main_window_layout.addWidget(self.progress_bar)
        main_window_layout.addWidget(self.status_bar)

        # background logic
        self.load_state_PVs()
        self._running_experiment = False
        self.automatic_scan_timer = QTimer(self)
        self.automatic_scan_timer.setInterval(1000)
        self.automatic_scan_timer.timeout.connect(self.update_automatic_scan_timer)

        self.show()

    # *--------------------------------* #
	# *---------- GUI Layout ----------* #
	# *--------------------------------* # 
    def _init_results_panel(self, ) -> None:
        """
        Results panel, LHS of GUI. \\
        Lists beam energy, fit stats, repolarisation time, etc.
        """
        # icons
        dir_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        # --- results / stats panel
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

        results_form        = QWidget()
        results_form_layout = QFormLayout()
        results_form.setLayout(results_form_layout)
        
        self.beam_energy_label          = QLabel()
        self.repolarisation_time_label  = QLabel()
        self.polarisation_label         = QLabel()

        self.polarisation       : float = 100   # %
        self.repolarisation_time: int   = 0     # seconds. 3 tpol -> 39 minutes (88 %)
        self.repolarisation_time_label  = QLabel("")
        self.repolarisation_timer       = QTimer(self)
        self.repolarisation_timer.setInterval(1000)
        self.repolarisation_timer.timeout.connect(self.update_repolarisation_time)

        self.automatic_scan_countdown_label = QLabel("")
        self.error_label                    = QLabel("")
        self.error_label.setStyleSheet("color:red")
        self.error_label.setWordWrap(True)

        results_form_layout.addRow("Beam Energy:", self.beam_energy_label)
        results_form_layout.addRow("Repolarisation time:", self.repolarisation_time_label)
        results_form_layout.addRow("Polarisation:", self.polarisation_label)
        results_form_layout.addRow("Next scan in:", self.automatic_scan_countdown_label)
        results_form_layout.addRow("Errors:", self.error_label)

        # temporary data path
        self.data_path = Path.cwd()
        hostname = platform.node()
        try:
            hostname.index("OPI")
            self.data_path = Path("/asp/usr/data/resdep")
        except ValueError: # not running on AS OPI
            pass

        self.button_data_path = QPushButton("Data")
        self.button_data_path.setIcon(dir_icon)
        # button callbacks
        self.button_data_path.clicked.connect(self.open_data_path)
        
        results_panel_layout.addWidget(results_panel_header, alignment=Qt.AlignmentFlag.AlignCenter)
        results_panel_layout.addWidget(results_form)
        results_panel_layout.addStretch()
        results_panel_layout.addWidget(self.button_data_path)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def _init_control_panel(self, ) -> None:
        """
        Control panel, RHS of GUI \\
        Contains buttons for automatic operation, and manual (normal / long) scans
        """
        # buttons / control panel
        self.control_panel = QWidget(self)
        control_panel_layout = QVBoxLayout()
        self.control_panel.setLayout(control_panel_layout)

        # --- Automatic button panel
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
        self.time_between_automatic_scans = QDoubleSpinBox(minimum=0.65, value=1, singleStep=0.01, decimals=2, suffix=" hours")
        automatic_form_layout.addRow("Time between scans:\n(end to start)", self.time_between_automatic_scans)

        # add to panel
        automatic_button_panel_layout.addWidget(automatic_button_header, alignment=Qt.AlignmentFlag.AlignCenter)
        automatic_button_panel_layout.addWidget(self.button_automatic)
        automatic_button_panel_layout.addWidget(automatic_form)
        
        # --- manual button panel
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
        self.button_manual_normal_scan  = QPushButton("Normal Scan")
        self.button_manual_wide_search  = QPushButton("Wide Search")

        # button callbacks
        self.button_automatic.clicked.connect(self.on_automatic_scan_clicked)
        self.button_manual_normal_scan.clicked.connect(self.on_normal_scan_clicked)
        self.button_manual_wide_search.clicked.connect(self.on_wide_search_clicked)
        
        # machine studies mode (override checks) checkbox
        self.checkbox_machine_studies = QCheckBox("Machine Studies (override)")

        # add to manual panel
        manual_button_panel_layout.addWidget(manual_button_header, alignment=Qt.AlignmentFlag.AlignCenter)
        manual_button_panel_layout.addWidget(self.button_manual_normal_scan)
        manual_button_panel_layout.addWidget(self.button_manual_wide_search)
        manual_button_panel_layout.addWidget(self.checkbox_machine_studies, alignment=Qt.AlignmentFlag.AlignCenter)

        # abort button
        self.button_abort = QPushButton("ABORT!")
        self.button_abort.setFixedSize(100, 60)
        # self.button_abort.setStyleSheet("QPushButton {background-color: red;}")
        self.button_abort.setEnabled(False)
        self.button_abort.clicked.connect(self.abort)

        # add everything to control panel
        control_panel_layout.addWidget(automatic_button_panel_frame)
        control_panel_layout.addSpacing(50)
        control_panel_layout.addWidget(manual_button_panel_frame)
        control_panel_layout.addWidget(self.button_abort, alignment=Qt.AlignmentFlag.AlignCenter)

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def enable_abort_button(self, enable: bool = True) -> None:
        """
        Enables / disables abort button and changes color to red when experiment is running or automatic scans enabled. 
        """
        if enable:
            self.button_abort.setEnabled(True)
            self.button_abort.setStyleSheet("QPushButton {background-color: red;}")
        else:
            self.button_abort.setEnabled(False)
            self.button_abort.setStyleSheet("QPushButton {background-color: none;}")
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def disable_abort_button(self,) -> None:
        """
        Alias for `enable_abort_button(enable=False)`
        """
        self.enable_abort_button(enable=False)
        return None
    # *--------------------------------* #
	# *---------- Experiment ----------* #
	# *--------------------------------* # 
    def run_experiment(self, ) -> None:
        """
        Executes the resdep experiment in a separate thread. \\
        resdep is wrapped in a worker class that attaches emitted progress, status, and plot updates (info)
        """

        # disable appropriate buttons
        # 
        #  
        # enable abort button (and turn red)
        self.enable_abort_button()
        # update status bar
        self.on_status_update("Starting up...")
            
        # call resdep
        self._running_experiment = True
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
    def on_status_update(self, message) -> None:
        """
        Updates the GUI statues (primarily from running to sleeping on injection)
        """
        self.status_bar.showMessage(f"Status: {message}")
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_data_path_update(self, data_path: Path) -> None:
        """
        Assign data path from resdep to GUI button 
        Spawn error logger
        """
        self.data_path = data_path
        self.button_data_path.setEnabled(True)


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
        Update states, buttons, progress bar. \\
        Perform data analysis (automagic fit) \\
        Write fit results to GUI (and PV?) \\
        Start timers for repolarisation and countdown to next scan (if automatic scans enabled).
        """
        self.on_status_update("Experiment finished. Performing data analysis...")

        # reset state
        self._running_experiment = False
        self._abort_requested = False
        # disable abort button
        self.disable_abort_button()

        # re-enable appropriate buttons

        # make sure progress bar reads 100%
        self.progress_bar.setValue(100)
        self.progress_bar.setMaximum(100)

        E0_mean, E0_mean_sigfig, fitted_beam_energy_string, error = self.fitting.automagic_fit()
        # update GUI
        if error:
            self.error_label.setText(error)
        else:
            self.beam_energy_label.setText(fitted_beam_energy_string)
        # TODO: write to PV????
        # beam_energy_PV.put(E0_mean_sigfig)


        # Timer things
        # self.timer.stop()
        self.repolarisation_timer.start()
        if self._automatic_scan_enabled:
            self.start_automatic_scan_countdown()
            self.on_status_update("Waiting for next automatic scan...")
        else:
            self.on_status_update("Ready")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def start_automatic_scan_countdown(self, ) -> None:
            # update countdown duration from GUI input
            self.automatic_scan_countdown = int(self.time_between_automatic_scans.value() * 3600)
            self.automatic_scan_timer.start()
            return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def update_automatic_scan_timer(self, ) -> None:
        """
        Use QTimer to countdown and trigger the next automatic scan.
        """
        self.automatic_scan_countdown += -1
        self.automatic_scan_countdown_label.setText(f"{datetime.timedelta(seconds=self.automatic_scan_countdown)}")
        
        if not self._automatic_scan_enabled:
            self.automatic_scan_timer.stop()
            self.automatic_scan_countdown = self.automatic_scan_countdown
            self.automatic_scan_countdown_label.setText("")

        elif self.automatic_scan_countdown <= 0:
            self.automatic_scan_timer.stop()
            self.automatic_scan()
        
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
            
        if self._running_experiment:
            self.repolarisation_timer.stop()
            self.repolarisation_time_label.setText("--> 0%")

        # stop after enough time
        if self.repolarisation_time >= 7790:
            self.repolarisation_timer.stop()

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def fit_beam_energy(self, ) -> None:
        """
        Need to figure this out
        """

        self.processed_data.calculate_ratio_loss(sigma=5)

        # self.fitting.automagic_fit()

        

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def check_if_experiment_can_run(self, scan_type: Literal["automatic", "manual"]) -> tuple[bool, str]:
        """
        Check if the experiment can run based on the state of the machine \\
        
        # Current requirements: 
        - More that 150 mA of beam current
        - At least 95% beam polarisation
            - Considers both time since recent injection and last diagnostic scan
        - Must be in "User Beam" if automatic scans are enabled

        Parameters
        ----------
        scan_type: Literal["automatic", "manual"]
            Automatic scans require the beam mode: "User Beam", while manual scans do not.

        Returns
        -------
        verdict: bool
            Answer to whether the experiment can run
        error: str
            Error message for why (specifically or first offending requirement) the experiment cannot run \\
            Displayed on the results panel.
        """
        verdict: bool = False
        error  : str  = "No error"

        self.error_label.setText("")

        if self.checkbox_machine_studies.isChecked():
            verdict = True
            return verdict, error

        beam_mode: Union[int, None] = self.beam_mode_PV.get()
        current: Union[float, None] = self.current_PV.get()
        time.sleep(0.5)

        # if PVs return None, exit early
        if beam_mode is None:
            error = f"beam_mode (FS01:BEAM_MODE_MONITOR) returned None. Expected any of:\n{self.beam_modes}\nAborting request to run resdep."
            warnings.warn(error)
            return False, error
        
        if current is None:
            error = "Current PV (DCCT) returned None.\nAborting request to run resdep."
            warnings.warn(error)
            return False, error

        # Assume can run, else check for errors
        scan_type_specific_requirements = [
            scan_type == "automatic" and beam_mode >= 8, # all user beam modes
            scan_type == "manual" # manual scans can run anytime
        ]
        recent_beam_injection = check_for_recent_beam_injection()

        if all([
            any(scan_type_specific_requirements),
            current             >= 150, # mA. More current = more resolution. Should ideally run at 200 mA
            self.polarisation   >= 95,   # %
            not recent_beam_injection
        ]):
            verdict= True
        elif current < 150: # mA
            error = f"Less than 150 mA beam current.\n{current:0.0f} mA is not enough resolution for measurement.\nAborting request to run resdep."
            warnings.warn(error)
            return False, error
        elif self.polarisation < 95: # %
            error = f"Beam polarisation is less than 95%; not enough resolution.\nAborting request to run resdep."
            warnings.warn(error)
            return False, error
        elif recent_beam_injection:
            error = f"Beam has been injected too recently and has not have enought time to polarise (requires at least 39 minutes)."
            warnings.warn(error)
            return False, error
        elif scan_type == "automatic" and beam_mode < 8: # not "User Beam" in automatic mode
            error = f"beam_mode (FS01:BEAM_MODE_MONITOR) returned \"{self.beam_modes[beam_mode]}\". Expected any form of 'User Beam'.\nAborting request to run resdep."
            warnings.warn(error)
            return False, error
        
        return verdict, error 
    # *--------------------------------* #
	# *---------- Scan Types ----------* #
	# *--------------------------------* #
    def automatic_scan(self, ) -> None:
        """
        Automatically runs resdep every hour using countdown timer \\
        """
        able_to_run_experiment, error = self.check_if_experiment_can_run(scan_type="automatic")

        if able_to_run_experiment:
            self.apply_default_scan_settings()
            self.run_experiment()
        else:
            self.error_label.setText(error)
            self.start_automatic_scan_countdown()
        
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def normal_scan(self, ) -> None:
        """
        Runs a typical beam energy scan. \\ 
        No different to automatic_scan, just manually triggered.
        """
        
        able_to_run_experiment, error = self.check_if_experiment_can_run(scan_type="manual")

        if able_to_run_experiment:
            self.apply_default_scan_settings()
            self.run_experiment()
        else:
            QMessageBox.critical(self, "Error", f"{error}")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def wide_search(self, ) -> None:
        """
        Runs a wide search for the beam energy (2 hour long scan, 0.35% of beam energy [3.02, 3.04] GeV) \\
        **WARNING**: If betatron tunes are off and within scan range, kicker will drive tunes.
        """

        able_to_run_experiment, error = self.check_if_experiment_can_run(scan_type="manual")

        if able_to_run_experiment:
            answer = QMessageBox.question(
                self, 
                "Continue?", 
                f"WARNING: May drive betatron tunes if they're off.\nDANGER ZONE: v_y = [0.097, 0.145] and v_y = [0.855, 0.903].\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            # if yes
            if answer == QMessageBox.StandardButton.Yes:
                self.close()
                self.resdep.bounds 	    = 0.35/100	# 2 hour scan
                self.resdep.sweep_rate  = 10	    # Hz/s
                self.run_experiment()
            else:
                self.close()

        else:
            QMessageBox.critical(self, "Error", f"{error}")


        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def apply_default_scan_settings(self, ) -> None:
        """
        Default resdep scan settings for normal and automatic
        """
        # --- exp variables
        self.resdep.bounds 	    = 0.05/100	# input %, output decimal
        self.resdep.sweep_rate  = 5	        # Hz/s
        
    # *--------------------------------* #
	# *------ Button Callbacks --------* #
	# *--------------------------------* #
    def on_automatic_scan_clicked(self, ) -> None:
        """
        Toggles states on button click. 
        If enabled -> calls automatic_scan().
        If disabled -> stops countown, asks to abort experiment.
        """
        if self.button_automatic.isChecked():
            self.button_automatic.setText("Enabled")
            self.button_automatic.setStyleSheet("QPushButton {background-color: orange;}")
            self.on_status_update("Waiting for next automatic scan...")
            self._automatic_scan_enabled = True
            self.apply_default_scan_settings()
            self.automatic_scan()

        else: # if unchecked
            self.button_automatic.setText("Disabled")
            self.button_automatic.setStyleSheet("QPushButton {background-color: none;}")
            self._automatic_scan_enabled = False
            if self._running_experiment:
                answer = QMessageBox.question(
                    self, 
                    "Abort experiment?", 
                    f"Diagnostic is still running. Do you want to abort it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if answer == QMessageBox.StandardButton.Yes:
                    self.close()
                    self.resdepQt.abort()
                else: # if no
                    self.close()

            else: # if experiment is not running
                self.on_status_update("Ready")

        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_normal_scan_clicked(self, ) -> None:
        """
        """
        pass
        return None
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    def on_wide_search_clicked(self, ) -> None:
        """
        """
        pass
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
    def abort(self, ) -> None:
        """
        Interrupts resdep experiment loop.
        """
        print("Abort requested!")
        self.disable_abort_button()
        self.resdepQt.abort()

        return None
    # *--------------------------------* #
    # *------------- EPICS ------------* #
    # *--------------------------------* #
    def load_state_PVs(self, ) -> None:
        """
        Loads PVs that track the current state of the beam. \\
        These are used to determine whether resdep is allowed to run. \\
        Provides safeguards and automatic disabling of automatic scans.
        """
        # --- Beam Mode --- #
        self.beam_modes = {
            1:  "Shut down",
            2:  "Maintenance",
            3:  "Machine studies",
            8:  "UserBeam Decay",
            9:  "UserBeam Top Up",
            10: "UserBeam Exotic"
        }

        self.beam_mode_PV = epics.pv.get_pv("FS01:BEAM_MODE_MONITOR", connect=True)
        self.current_PV = epics.pv.get_pv("SR11BCM01:CURRENT_MONITOR", connect=True)



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
    if hasattr(sys, "ps1"): # interactive check
        app.exec()
    else:
        sys.exit(app.exec())