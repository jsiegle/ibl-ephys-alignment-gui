"""Visualization components for the ephys alignment GUI.

This subpackage contains all PyQt5-dependent visualization code,
including the main GUI window, plot widgets, and helper elements.
"""

from ephys_alignment_gui.visualization.launch_gui import MainWindow, main
from ephys_alignment_gui.visualization.plot_data import PlotData
from ephys_alignment_gui.visualization.plot_elements import ColorBar

__all__ = [
    "MainWindow",
    "main",
    "PlotData",
    "ColorBar",
]
