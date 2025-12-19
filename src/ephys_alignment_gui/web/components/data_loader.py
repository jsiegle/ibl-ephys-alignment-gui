"""Data loading UI component for the web frontend.

Provides file/folder selection and data loading functionality using Panel widgets.
"""

import asyncio
import logging
from pathlib import Path

import panel as pn
import param

from ephys_alignment_gui.io.data_loader import LoadDataLocal
from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)


class DataLoader(param.Parameterized):
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
        self._load_button = pn.widgets.Button(
            name="Load Data",
            button_type="primary",
            sizing_mode="stretch_width",
        )
        self._status_indicator = pn.indicators.LoadingSpinner(
            value=False,
            size=20,
            color="primary",
        )

        # Wire up callbacks
        self._load_button.on_click(self._on_load_clicked)
        self._input_path_input.param.watch(self._on_input_path_changed, "value")

    def _on_input_path_changed(self, event) -> None:
        """Handle input path text changes."""
        path_str = event.new
        if path_str and Path(path_str).exists():
            self._load_button.disabled = False
            # Try to detect number of shanks
            self._detect_shanks(Path(path_str))
        else:
            self._load_button.disabled = True

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
                self._shank_selector.visible = True
            else:
                self._shank_selector.options = {"Shank 0": 0}
                self._shank_selector.visible = False

            self.state.n_shanks = n_shanks
            logger.info(f"Detected {n_shanks} shank(s)")
        except Exception as e:
            logger.warning(f"Could not detect shanks: {e}")
            self._shank_selector.options = {"Shank 0": 0}

    def _on_load_clicked(self, event) -> None:
        """Handle load button click."""
        input_path = self._input_path_input.value
        if not input_path:
            self.state.set_status("Please enter an input path", is_loading=False)
            return

        # Trigger async load
        asyncio.create_task(self._load_data_async())

    async def _load_data_async(self) -> None:
        """Load data asynchronously to avoid blocking the UI."""
        input_path = Path(self._input_path_input.value)
        output_path = (
            Path(self._output_path_input.value)
            if self._output_path_input.value
            else None
        )
        shank_idx = self._shank_selector.value

        # Update UI state
        self._load_button.disabled = True
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
            self._load_button.disabled = False
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

        logger.info(f"Data loaded successfully from {probe_path}")

    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the data loader UI.
        """
        return pn.Column(
            pn.pane.Markdown("## Load Data"),
            self._input_path_input,
            self._shank_selector,
            self._output_path_input,
            pn.Row(
                self._load_button,
                self._status_indicator,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )
