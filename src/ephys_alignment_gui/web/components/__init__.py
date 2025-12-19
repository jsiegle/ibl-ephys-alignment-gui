"""Reusable Panel components for the web frontend.

Each component is a param.Parameterized class with a view() method that
returns a Panel/HoloViews object for display.
"""

from ephys_alignment_gui.web.components.data_loader import DataLoader
from ephys_alignment_gui.web.components.ephys_plots import EphysPlots

__all__ = [
    "DataLoader",
    "EphysPlots",
]
