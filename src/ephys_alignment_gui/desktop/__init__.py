"""Desktop GUI components for the ephys alignment application.

This subpackage contains all PyQt5-dependent code for the desktop GUI,
including the main window, plot widgets, and helper elements.

A web-based frontend could be added in a separate 'web' subpackage
that reuses core and visualization modules without PyQt dependencies.
"""

from ephys_alignment_gui.desktop.launch_gui import MainWindow, main
from ephys_alignment_gui.desktop.plot_elements import ColorBar

__all__ = [
    "MainWindow",
    "main",
    "ColorBar",
]
