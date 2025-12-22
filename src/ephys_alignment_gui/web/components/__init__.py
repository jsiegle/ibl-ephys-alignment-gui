"""Reusable Panel components for the web frontend.

Each component is a param.Parameterized class with a view() method that
returns a Panel/HoloViews object for display.
"""

from ephys_alignment_gui.web.components.alignment_controls import AlignmentControls
from ephys_alignment_gui.web.components.colorbar import ColorBar, RangeSliderColorBar
from ephys_alignment_gui.web.components.data_selection_panel import DataSelectionPanel
from ephys_alignment_gui.web.components.ephys_plots import EphysPlots
from ephys_alignment_gui.web.components.histology_panel import HistologyPanel
from ephys_alignment_gui.web.components.probe_view import ProbeView
from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager
from ephys_alignment_gui.web.components.slice_viewer import SliceViewer

__all__ = [
    "AlignmentControls",
    "ColorBar",
    "DataSelectionPanel",
    "EphysPlots",
    "HistologyPanel",
    "ProbeView",
    "RangeSliderColorBar",
    "ReferenceLinesManager",
    "SliceViewer",
]
