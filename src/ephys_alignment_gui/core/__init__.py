"""Core alignment and data processing components.

This subpackage contains the core logic for ephys alignment that is
independent of any GUI framework. All modules here must NOT import
PyQt5 or any visualization-specific dependencies.
"""

from ephys_alignment_gui.core.alignment import EphysAlignment
from ephys_alignment_gui.core.atlas import BrainAtlasAnatomical
from ephys_alignment_gui.core.histology import (
    get_brain_regions,
    get_picked_tracks,
    interpolate_along_track,
    load_track_csv,
)
from ephys_alignment_gui.core.probe_geometry import TIP_SIZE_UM, trace_header

__all__ = [
    "EphysAlignment",
    "BrainAtlasAnatomical",
    "load_track_csv",
    "get_picked_tracks",
    "interpolate_along_track",
    "get_brain_regions",
    "trace_header",
    "TIP_SIZE_UM",
]
