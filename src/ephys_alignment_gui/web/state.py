"""Centralized application state for the web frontend.

Uses param.Parameterized for reactive state management. Components can watch
parameters for changes and update automatically.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import param

if TYPE_CHECKING:
    from ephys_alignment_gui.core.alignment import EphysAlignment
    from ephys_alignment_gui.io.data_loader import LoadDataLocal
    from ephys_alignment_gui.visualization.plot_data import PlotData

logger = logging.getLogger(__name__)


class AppState(param.Parameterized):
    """Shared state for the alignment application.

    This class holds all application state as param parameters, enabling
    reactive updates when values change. Components can use @param.depends
    to automatically update when relevant state changes.

    Attributes
    ----------
    input_path : Path or None
        Path to the input data directory.
    output_path : Path or None
        Path for saving alignment results.
    data_loaded : bool
        Whether ephys data has been successfully loaded.
    loading : bool
        Whether data is currently being loaded (for busy indicator).
    status_message : str
        Current status message to display to user.
    current_shank : int
        Currently selected shank index (0-based).
    n_shanks : int
        Total number of shanks available.
    current_idx : int
        Current alignment move index.
    total_idx : int
        Total number of alignment moves made.
    probe_tip : float
        Position of probe tip in microns from tip.
    probe_top : float
        Position of probe top in microns from tip.
    reference_lines : list
        List of reference line y-positions for alignment.
    img_plot_type : str
        Currently selected image plot type.
    line_plot_type : str
        Currently selected line plot type.
    probe_plot_type : str
        Currently selected probe plot type.
    slice_plot_type : str
        Currently selected slice plot type.
    """

    # Data loading state
    input_path = param.Path(default=None, doc="Path to input data directory")
    output_path = param.Path(default=None, doc="Path for saving results")
    data_loaded = param.Boolean(default=False, doc="Whether data is loaded")
    loading = param.Boolean(default=False, doc="Whether currently loading")
    status_message = param.String(default="Ready", doc="Status message")

    # Session state
    current_shank = param.Integer(default=0, bounds=(0, None), doc="Current shank index")
    n_shanks = param.Integer(default=1, bounds=(1, None), doc="Number of shanks")

    # Alignment state
    current_idx = param.Integer(default=0, bounds=(0, None), doc="Current move index")
    total_idx = param.Integer(default=0, bounds=(0, None), doc="Total moves made")
    probe_tip = param.Number(default=0, doc="Probe tip position (um)")
    probe_top = param.Number(default=3840, doc="Probe top position (um)")
    reference_lines = param.List(default=[], doc="Reference line positions")
    lin_fit = param.Boolean(default=True, doc="Use linear fit scaling")

    # Shared Y-axis range for depth plots (ephys, histology)
    depth_y_range = param.Tuple(default=(-100, 3940), doc="Shared Y-axis range for depth plots")

    # Plot selection
    img_plot_type = param.Selector(
        default="firing_rate",
        objects=[
            "firing_rate",
            "amplitude",
            "cluster_fr",
            "cluster_p2t",
            "cluster_amp",
            "spike_correlation",
            "rms_ap",
            "rms_lf",
            "lfp_spectrum",
        ],
        doc="Image plot type",
    )
    line_plot_type = param.Selector(
        default="firing_rate",
        objects=["firing_rate", "amplitude"],
        doc="Line plot type",
    )
    probe_plot_type = param.Selector(
        default="rms_ap",
        objects=["rms_ap", "rms_lf"],
        doc="Probe plot type",
    )
    slice_plot_type = param.Selector(
        default="ccf",
        objects=["ccf", "label"],
        doc="Slice plot type",
    )


    def __init__(self, **params):
        super().__init__(**params)

        # Non-param attributes for core objects
        # These are set after data loading
        self._loaddata: "LoadDataLocal | None" = None
        self._ephys_alignment: "EphysAlignment | None" = None
        self._plot_data: "PlotData | None" = None

        # Data containers (set after loading)
        self._data: dict | None = None
        self._hist_data: dict | None = None
        self._slice_data: dict | None = None
        self._probe_path: Path | None = None

    @property
    def loaddata(self) -> "LoadDataLocal | None":
        """Access the data loader instance."""
        return self._loaddata

    @loaddata.setter
    def loaddata(self, value: "LoadDataLocal"):
        self._loaddata = value

    @property
    def ephys_alignment(self) -> "EphysAlignment | None":
        """Access the alignment instance."""
        return self._ephys_alignment

    @ephys_alignment.setter
    def ephys_alignment(self, value: "EphysAlignment"):
        self._ephys_alignment = value

    @property
    def plot_data(self) -> "PlotData | None":
        """Access the plot data instance."""
        return self._plot_data

    @plot_data.setter
    def plot_data(self, value: "PlotData"):
        self._plot_data = value

    @property
    def data(self) -> dict | None:
        """Access the loaded ephys data."""
        return self._data

    @data.setter
    def data(self, value: dict):
        self._data = value

    @property
    def hist_data(self) -> dict | None:
        """Access the histology data."""
        return self._hist_data

    @hist_data.setter
    def hist_data(self, value: dict):
        self._hist_data = value

    @property
    def slice_data(self) -> dict | None:
        """Access the slice data."""
        return self._slice_data

    @slice_data.setter
    def slice_data(self, value: dict):
        self._slice_data = value

    @property
    def probe_path(self) -> Path | None:
        """Access the probe data path."""
        return self._probe_path

    @probe_path.setter
    def probe_path(self, value: Path):
        self._probe_path = value

    def reset_session(self) -> None:
        """Reset session-specific state for a new session."""
        self.current_idx = 0
        self.total_idx = 0
        self.probe_tip = 0
        self.probe_top = 3840
        self.reference_lines = []
        self.lin_fit = True
        self._ephys_alignment = None
        self._plot_data = None
        self._data = None
        self._hist_data = None
        self._slice_data = None
        self._probe_path = None
        logger.info("Session state reset")

    def set_status(self, message: str, is_loading: bool = False) -> None:
        """Update status message and loading state.

        Parameters
        ----------
        message : str
            Status message to display.
        is_loading : bool
            Whether to show loading indicator.
        """
        self.status_message = message
        self.loading = is_loading
        logger.debug(f"Status: {message} (loading={is_loading})")
