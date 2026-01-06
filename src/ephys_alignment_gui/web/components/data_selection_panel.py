"""Data loading UI component for the web frontend.

Provides file/folder selection and data loading functionality using Panel widgets.
"""

import asyncio
import logging
from pathlib import Path

import panel as pn
import param

from ephys_alignment_gui.core.alignment import EphysAlignment
from ephys_alignment_gui.visualization.plot_data import PlotData

from ephys_alignment_gui.io.data_loader import LoadDataLocal
from ephys_alignment_gui.web.state import AppState
        

logger = logging.getLogger(__name__)


class DataSelectionPanel(param.Parameterized):
    """Component for selecting and loading ephys data.

    Provides a UI for:
    - Selecting input data directory
    - Selecting output directory for results
    - Choosing shank (for multi-shank probes)
    - Loading data with progress feedback

    Parameters
    ----------
    state : AppState
        Shared application state.
    """

    # Events triggered by user actions
    load_requested = param.Event(doc="Triggered when user clicks Load")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state

        # Create widgets
        self._input_path_input = pn.widgets.TextInput(
            name="Input Directory",
            placeholder="/path/to/ephys/data",
            sizing_mode="stretch_width",
        )
        self._output_path_input = pn.widgets.TextInput(
            name="Output Directory",
            placeholder="/path/to/output (optional)",
            sizing_mode="stretch_width",
        )
        self._shank_selector = pn.widgets.Select(
            name="Shank",
            options={"Shank 0": 0},
            value=0,
            sizing_mode="stretch_width",
        )
        self._status_indicator = pn.indicators.LoadingSpinner(
            value=False,
            size=20,
            color="primary",
        )
        
        # Button created in view() method with reactive disabled state

    def _is_valid_path(self, path_str: str) -> bool:
        """Check if the given path string is a valid directory.
        
        Parameters
        ----------
        path_str : str
            Path string to validate.
            
        Returns
        -------
        bool
            True if path exists and is a directory.
        """
        if not path_str:
            return False
        
        try:
            path = Path(path_str)
            return path.exists() and path.is_dir()
        except Exception as e:
            logger.warning(f"Error checking path '{path_str}': {e}")
            return False
    
    def _check_path_and_update(self, path_str: str) -> None:
        """Check path validity and update shank detection.
        
        This is called when the path changes to detect available shanks.
        """
        if not path_str:
            return
            
        try:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                logger.debug(f"Valid directory found: {path}")
                # Try to detect number of shanks
                self._detect_shanks(path)
        except Exception:
            pass

    def _detect_shanks(self, input_path: Path) -> None:
        """Detect available shanks from the input path."""
        try:
            # Use LoadDataLocal to detect shanks without full load
            temp_loader = LoadDataLocal()
            we_are_in_code_ocean = (
                Path("/results/").is_dir() and Path("/data/").is_dir()
            )
            temp_loader.set_input_paths(input_path, we_are_in_code_ocean)
            temp_loader.load_channel_info(input_path)
            n_shanks = temp_loader.n_shanks

            if n_shanks > 1:
                options = {f"Shank {i}": i for i in range(n_shanks)}
                self._shank_selector.options = options
            else:
                self._shank_selector.options = {"Shank 0": 0}

            self.state.n_shanks = n_shanks
            logger.info(f"Detected {n_shanks} shank(s)")
        except Exception as e:
            logger.warning(f"Could not detect shanks: {e}")
            self._shank_selector.options = {"Shank 0": 0}

    def _on_load_clicked(self, event) -> None:
        """Handle load button click."""
        input_path = self._input_path_input.value
        logger.debug(f"Load button clicked with input path: {input_path}")
        if not input_path:
            self.state.set_status("Please enter an input path", is_loading=False)
            return

        # Trigger async load using Panel's execution method
        pn.state.execute(self._load_data_async)

    async def _load_data_async(self) -> None:
        """Load data asynchronously to avoid blocking the UI."""
        input_path = Path(self._input_path_input.value)
        logger.debug(f"Starting async data load from: {input_path}")
        output_path = (
            Path(self._output_path_input.value)
            if self._output_path_input.value
            else None
        )
        shank_idx = self._shank_selector.value

        # Update UI state (button disabled state is handled by reactive value)
        self._status_indicator.value = True
        self.state.set_status("Loading data...", is_loading=True)

        try:
            # Run blocking I/O in thread pool
            await asyncio.to_thread(
                self._load_data_sync, input_path, output_path, shank_idx
            )

            self.state.data_loaded = True
            self.state.input_path = input_path
            self.state.output_path = output_path
            self.state.current_shank = shank_idx
            self.state.set_status("Data loaded successfully", is_loading=False)

            # Trigger event for other components
            self.param.trigger("load_requested")

        except Exception as e:
            logger.exception("Failed to load data")
            self.state.set_status(f"Error: {e}", is_loading=False)
            self.state.data_loaded = False

        finally:
            self._status_indicator.value = False

    def _load_data_sync(
        self, input_path: Path, output_path: Path | None, shank_idx: int
    ) -> None:
        """Synchronous data loading (runs in thread pool).

        Parameters
        ----------
        input_path : Path
            Path to input data directory.
        output_path : Path or None
            Path for output files.
        shank_idx : int
            Shank index to load.
        """
        logger.info(f"Loading data from {input_path}, shank {shank_idx}")

        # Detect Code Ocean environment
        we_are_in_code_ocean = (
            Path("/results/").is_dir() and Path("/data/").is_dir()
        )

        # Initialize data loader
        loaddata = LoadDataLocal()
        loaddata.set_input_paths(input_path, we_are_in_code_ocean)
        loaddata.load_channel_info(input_path)

        # Load ephys data
        probe_path, chn_depths, sess_notes, data = loaddata.get_ephys_data(shank_idx)

        if not probe_path:
            raise ValueError("Failed to load ephys data - no probe path returned")

        # Store in state
        self.state.loaddata = loaddata
        self.state.data = data
        self.state.probe_path = probe_path

        # Load atlas and histology if not already loaded
        if loaddata.brain_atlas is None:
            logger.info("Loading atlas and histology...")
            loaddata.load_atlas_and_histology()

        # Initialize alignment and populate hist_data
        logger.info("Initializing alignment...")
        from ephys_alignment_gui.core.alignment import EphysAlignment
        from ephys_alignment_gui.visualization.plot_data import PlotData
        
        # Get track annotations for the current shank
        track_annotations_ras = loaddata.get_track_annotations(shank_idx)
        
        # Create alignment object
        ephys_alignment = EphysAlignment(
            track_annotations_ras,
            chn_depths=chn_depths,
            brain_atlas=loaddata.brain_atlas,
            speedy=False,
        )
        
        # Get initial feature/track arrays from alignment
        features, track, _ = ephys_alignment.get_track_and_feature()
        self.state.features = features
        self.state.track = track
        
        # Get ALIGNED histology using current features/track
        hist_regions, hist_axis_labels = ephys_alignment.scale_histology_regions(
            features, track
        )
        self.state.hist_data = {
            "region": hist_regions,
            "axis_label": hist_axis_labels,
            "colour": ephys_alignment.region_colour,
        }
        
        # Get REFERENCE (unaligned) histology using track_extent
        hist_regions_ref, hist_axis_labels_ref = ephys_alignment.scale_histology_regions(
            ephys_alignment.track_extent, ephys_alignment.track_extent
        )
        self.state.hist_data_ref = {
            "region": hist_regions_ref,
            "axis_label": hist_axis_labels_ref,
            "colour": ephys_alignment.region_colour,
        }
        
        # Store alignment object in state
        self.state.ephys_alignment = ephys_alignment
        
        # Set probe bounds from alignment track extent (convert m to µm)
        probe_tip_um = ephys_alignment.track_extent[0] * 1e6
        probe_top_um = ephys_alignment.track_extent[1] * 1e6
        self.state.probe_tip = probe_tip_um
        self.state.probe_top = probe_top_um
        
        # Set depth_y_range from probe bounds with padding
        padding = 100  # µm
        self.state.depth_y_range = (probe_tip_um - padding, probe_top_um + padding)
        logger.info(f"Set depth_y_range to ({probe_tip_um - padding:.1f}, {probe_top_um + padding:.1f}) µm")
        
        # Load LFP correlation data if available
        lfp_corr_data = loaddata.load_lfp_correlation_data(probe_path)
        
        # Create PlotData with correct arguments
        self.state.plot_data = PlotData(
            probe_path, data, shank_idx, lfp_correlation_data=lfp_corr_data
        )
        
        logger.info(f"Data loaded successfully from {probe_path}")

    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the data loader UI.
        """
        # Create load button with reactive disabled state
        # The button is disabled when the path is invalid
        @pn.depends(self._input_path_input.param.value, watch=False)
        def create_button(path_value):
            is_valid = self._is_valid_path(path_value)
            button = pn.widgets.Button(
                name="Load Data",
                button_type="primary",
                sizing_mode="stretch_width",
                disabled=not is_valid,
            )
            button.on_click(self._on_load_clicked)
            
            # Also trigger shank detection when path becomes valid
            if is_valid:
                self._check_path_and_update(path_value)
            
            return button
        
        button_pane = pn.panel(create_button)
        
        return pn.Column(
            self._input_path_input,
            self._shank_selector,
            self._output_path_input,
            pn.Row(
                button_pane,
                self._status_indicator,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )
