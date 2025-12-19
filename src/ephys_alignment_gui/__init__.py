"""IBL Ephys Alignment GUI

A PyQt5-based GUI for aligning electrophysiology data with histology data.

Package Structure:
- core: Core alignment logic (no PyQt dependencies)
- visualization: GUI and plotting components
- io: Data loading and output utilities
"""

__version__ = "0.2.0"

# Re-export key classes for backward compatibility
from ephys_alignment_gui.core.alignment import EphysAlignment
from ephys_alignment_gui.core.atlas import BrainAtlasAnatomical
from ephys_alignment_gui.io.data_loader import LoadDataLocal

__all__ = [
    "EphysAlignment",
    "BrainAtlasAnatomical",
    "LoadDataLocal",
    "__version__",
]
