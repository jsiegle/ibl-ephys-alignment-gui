"""Data visualization utilities for electrophysiology analysis.

This subpackage contains PyQt-independent data processing and
visualization utilities. PyQt-dependent GUI code lives in the
'desktop' subpackage.

Modules:
    plot_data: Data processing for scatter/image plots
    create_overview_plots: Static matplotlib-based summary figures
"""

from ephys_alignment_gui.visualization.plot_data import PlotData

__all__ = [
    "PlotData",
]
