"""Core alignment and data processing components.

This subpackage contains the core logic for ephys alignment that is
independent of any GUI framework. All modules here must NOT import
PyQt5 or any visualization-specific dependencies.
"""

from ephys_alignment_gui.core.alignment import EphysAlignment, interpolate_along_track
from ephys_alignment_gui.core.atlas import BrainAtlasAnatomical

__all__ = [
    "EphysAlignment",
    "BrainAtlasAnatomical",
    "interpolate_along_track"
]
