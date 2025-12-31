"""Main layout for the web frontend.

Organizes all visualization components into a grid layout that
mirrors the desktop application structure.
"""

import logging

import numpy as np
import panel as pn
import param

from ephys_alignment_gui.core.alignment import EphysAlignment
from ephys_alignment_gui.web.components.alignment_controls import AlignmentControls
from ephys_alignment_gui.web.components.ephys_plots import EphysPlots
from ephys_alignment_gui.web.components.histology_panel import HistologyPanel
from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager
from ephys_alignment_gui.web.components.slice_viewer import SliceViewer
from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)

# Maximum number of alignment moves to track in history
MAX_ALIGNMENT_HISTORY = 10

class MainLayout(param.Parameterized):
    """Main layout manager for the alignment GUI.

    Coordinates all visualization components and arranges them in a
    grid layout similar to the desktop application.

    Layout structure (similar to desktop):
    ```
    +-------------------+------------+------------------+
    |                   |            | Slice Viewer     |
    |   Ephys Plots     | Histology  +------------------+
    |   (img + line +   |   Panel    | Controls         |
    |    probe)         |            +------------------+
    |                   |            | Fit Plot         |
    +-------------------+------------+------------------+
    ```

    Parameters
    ----------
    state : AppState
        Shared application state.
    """

    # Trigger layout refresh
    refresh = param.Event(doc="Trigger layout refresh")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state

        # Initialize reference lines manager first (shared by plots)
        self.reference_lines = ReferenceLinesManager(state)

        # Initialize visualization components with reference lines support
        self.ephys_plots = EphysPlots(state, reference_lines=self.reference_lines)
        self.histology_panel = HistologyPanel(
            state, reference_lines=self.reference_lines
        )
        self.slice_viewer = SliceViewer(state)
        self.alignment_controls = AlignmentControls(state)

        # Alignment state - arrays for tracking history
        self._track_history: list[np.ndarray] = []
        self._feature_history: list[np.ndarray] = []
        self._current_align_idx = 0

        # Cache area views so reactive bindings are preserved
        self._ephys_area = None
        self._histology_area = None
        self._control_area = None

        # Wire up inter-component communication
        self._setup_event_handlers()

        # Watch for data loading to initialize alignment
        state.param.watch(self._on_data_loaded, "data_loaded")

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for inter-component communication."""
        # Alignment control events
        self.alignment_controls.param.watch(
            self._on_fit_clicked, "fit_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_offset_clicked, "offset_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_reset_clicked, "reset_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_delete_line_clicked, "delete_line_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_next_clicked, "next_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_prev_clicked, "prev_clicked"
        )

    def _on_data_loaded(self, event) -> None:
        """Initialize alignment when data is loaded."""
        if not event.new:
            return

        loaddata = self.state.loaddata
        if loaddata is None or loaddata.brain_atlas is None:
            logger.warning("Cannot initialize alignment - no atlas data")
            return

        # Get track annotations from loaddata (need to load per shank)
        shank_idx = self.state.current_shank
        try:
            track_annotations = loaddata.get_track_annotations(shank_idx)
        except Exception as e:
            logger.warning(f"No track annotations available for alignment: {e}")
            return

        try:
            # Initialize EphysAlignment
            chn_depths = loaddata.chn_coords_all[:, 1] if loaddata.chn_coords_all is not None else None
            ephys_alignment = EphysAlignment(
                track_annotations_ras=track_annotations,
                chn_depths=chn_depths,
                brain_atlas=loaddata.brain_atlas,
            )
            self.state.ephys_alignment = ephys_alignment

            # Initialize alignment history
            self._track_history = [np.copy(ephys_alignment.track_init)]
            self._feature_history = [np.copy(ephys_alignment.feature_init)]
            self._current_align_idx = 0

            # Set initial histology data
            self._update_histology_data()

            # Load slice data using the interpolated track
            try:
                slice_data, _ = loaddata.get_slice_images(
                    ephys_alignment.track_interpolation_ras
                )
                self.state.slice_data = slice_data
                logger.info("Slice data loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load slice data: {e}")
                self.state.slice_data = None

            # Explicitly refresh all dependent components
            self.slice_viewer.param.trigger("refresh")
            self.histology_panel.param.trigger("refresh")

            logger.info("EphysAlignment initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize EphysAlignment: {e}")

    def _update_histology_data(self) -> None:
        """Update histology data in state from current alignment."""
        ephys_align = self.state.ephys_alignment
        if ephys_align is None:
            return

        if not self._track_history or not self._feature_history:
            return

        idx = min(self._current_align_idx, len(self._track_history) - 1)
        features = self._feature_history[idx]
        track = self._track_history[idx]

        try:
            # Scale histology regions based on current alignment
            region, region_label = ephys_align.scale_histology_regions(features, track)

            # Update state with histology data
            self.state.hist_data = {
                "region": region,
                "axis_label": region_label,
                "colour": ephys_align.region_colour,
            }

            # Trigger histology panel refresh
            self.histology_panel.param.trigger("refresh")
            logger.debug(f"Updated histology data at alignment index {idx}")
        except Exception as e:
            logger.exception(f"Failed to update histology data: {e}")

    def _on_fit_clicked(self, event) -> None:
        """Handle fit button click - apply scaling based on reference lines."""
        ephys_align = self.state.ephys_alignment
        if ephys_align is None:
            logger.warning("No alignment object - cannot fit")
            return

        if not self._track_history or not self._feature_history:
            logger.warning("No alignment history - cannot fit")
            return

        # Get reference line positions
        line_features = self.reference_lines.feature_positions / 1e6  # Convert to meters
        line_tracks = self.reference_lines.track_positions / 1e6

        if len(line_features) == 0:
            logger.info("No reference lines - fit has no effect")
            return

        # Get previous alignment state
        prev_idx = min(self._current_align_idx, len(self._track_history) - 1)
        prev_features = self._feature_history[prev_idx]
        prev_track = self._track_history[prev_idx]

        # Combine reference lines with boundary points
        depths_track = np.sort(np.r_[prev_track[[0, -1]], line_tracks])

        # Compute new track positions
        new_track = ephys_align.feature2track(
            depths_track,
            prev_features,
            prev_track,
        )

        new_features = np.sort(
            np.r_[prev_features[[0, -1]], line_features]
        )

        # Apply linear or uniform extremes adjustment
        if len(new_features) >= 5 and self.state.lin_fit:
            new_features, new_track = ephys_align.adjust_extremes_linear(
                new_features, new_track
            )
        else:
            new_track = ephys_align.adjust_extremes_uniform(new_features, new_track)

        # Store in history (with max size limit)
        self._current_align_idx += 1
        if len(self._track_history) > MAX_ALIGNMENT_HISTORY:
            self._track_history.pop(0)
            self._feature_history.pop(0)
            self._current_align_idx = len(self._track_history)

        self._track_history.append(new_track)
        self._feature_history.append(new_features)

        # Update state counters
        self.state.current_idx = self._current_align_idx
        self.state.total_idx = len(self._track_history) - 1

        # Update histology display
        self._update_histology_data()

        logger.info(f"Fit applied - alignment index now {self._current_align_idx}")
        self.param.trigger("refresh")

    def _on_offset_clicked(self, event) -> None:
        """Handle offset button click - shift alignment by probe tip position."""
        ephys_align = self.state.ephys_alignment
        if ephys_align is None:
            logger.warning("No alignment object - cannot offset")
            return

        if not self._track_history:
            return

        # Calculate offset from probe tip change
        # In the desktop version, this comes from dragging the tip line
        # For now, we'll use a simple offset mechanism
        offset_delta = (self.state.probe_tip - 0) / 1e6  # Convert to meters

        prev_idx = min(self._current_align_idx, len(self._track_history) - 1)
        prev_track = np.copy(self._track_history[prev_idx])
        prev_features = np.copy(self._feature_history[prev_idx])

        # Shift track boundaries
        new_track = np.copy(prev_track)
        new_track[0] += offset_delta
        new_track[-1] += offset_delta

        # Store in history
        self._current_align_idx += 1
        if len(self._track_history) > MAX_ALIGNMENT_HISTORY:
            self._track_history.pop(0)
            self._feature_history.pop(0)
            self._current_align_idx = len(self._track_history)

        self._track_history.append(new_track)
        self._feature_history.append(prev_features)

        # Update state
        self.state.current_idx = self._current_align_idx
        self.state.total_idx = len(self._track_history) - 1

        self._update_histology_data()

        logger.info(f"Offset applied - alignment index now {self._current_align_idx}")
        self.param.trigger("refresh")

    def _on_next_clicked(self, event) -> None:
        """Handle next button click - move forward in alignment history."""
        if self._current_align_idx < len(self._track_history) - 1:
            self._current_align_idx += 1
            self.state.current_idx = self._current_align_idx
            self._update_histology_data()
            self.param.trigger("refresh")

    def _on_prev_clicked(self, event) -> None:
        """Handle previous button click - move backward in alignment history."""
        if self._current_align_idx > 0:
            self._current_align_idx -= 1
            self.state.current_idx = self._current_align_idx
            self._update_histology_data()
            self.param.trigger("refresh")

    def _on_reset_clicked(self, event) -> None:
        """Handle reset button click."""
        # Reset alignment to initial state
        if self.state.ephys_alignment is not None:
            self._track_history = [np.copy(self.state.ephys_alignment.track_init)]
            self._feature_history = [np.copy(self.state.ephys_alignment.feature_init)]
            self._current_align_idx = 0
            self.state.current_idx = 0
            self.state.total_idx = 0
            self._update_histology_data()

        # Clear reference lines
        self.reference_lines.clear_lines()

        # Reset probe bounds
        self.state.probe_tip = 0
        self.state.probe_top = 3840

        logger.info("Alignment reset to initial state")
        self.param.trigger("refresh")

    def _on_delete_line_clicked(self, event) -> None:
        """Handle delete line button click."""
        self.reference_lines.remove_last_line()
        self.param.trigger("refresh")

    def _create_linked_depth_plots(self) -> pn.Column:
        """Create all depth plots with linked Y-axes.

        Combines ephys plots (image, line, probe) and histology into
        separate columns with their controls. Plotly handles Y-axis 
        linking via shared state.

        Returns
        -------
        pn.Column
            Column containing controls and plots.
        """
        # Get controls
        image_selector = self.ephys_plots.controls(selector='image')
        line_selector = self.ephys_plots.controls(selector='line')
        probe_selector = self.ephys_plots.controls(selector='probe')
        hist_selector = self.histology_panel.controls()

        # Create columns with controls above each plot
        image_column = pn.Column(
            image_selector,
            self.ephys_plots.view_image(),
            sizing_mode="stretch_both",
        )
        line_column = pn.Column(
            line_selector,
            self.ephys_plots.view_line(),
            sizing_mode="stretch_both",
        )
        probe_column = pn.Column(
            probe_selector,
            self.ephys_plots.view_probe(),
            sizing_mode="stretch_both",
        )
        hist_column = pn.Column(
            hist_selector,
            self.histology_panel.view(),
            sizing_mode="stretch_both",
        )

        # Create plots row
        plots_row = pn.Row(
            image_column,
            line_column,
            probe_column,
            hist_column,
            sizing_mode="stretch_both",
        )

        return plots_row

    def _create_ephys_area(self) -> pn.Column:
        """Create the ephys and histology visualization area with linked axes.

        Returns
        -------
        pn.Column
            Column containing linked depth plots and controls.
        """
        # Create reactive binding for the linked plots
        plot_view = pn.bind(
            lambda _, __: self._create_linked_depth_plots(),
            self.ephys_plots.param.refresh,
            self.histology_panel.param.refresh,
        )

        # Reference lines controls below the plots
        ref_lines_view = self.reference_lines.controls()
        ref_lines_section = pn.Row(
            pn.pane.Markdown("**Reference Lines:**", margin=(5, 10, 0, 0)),
            ref_lines_view,
            sizing_mode="stretch_width",
        )

        return pn.Column(
            plot_view,
            ref_lines_section,
            sizing_mode="stretch_both",
        )

    def _create_control_area(self) -> pn.Column:
        """Create the controls area.

        Returns
        -------
        pn.Column
            Column containing alignment controls.
        """
        return pn.Column(
            self.alignment_controls.view(),
            sizing_mode="stretch_width",
            min_height=200,
        )
    
    def _create_slice_viewer_area(self) -> pn.Column:
        """Create the slice viewer area.

        Returns
        -------
        pn.Column
            Column containing the slice viewer with its selector.
        """
        slice_view = pn.bind(
            lambda _: self.slice_viewer.view(),
            self.slice_viewer.param.refresh,
        )

        return pn.Column(
            self.slice_viewer.controls(),
            slice_view,
            sizing_mode="stretch_both",
        )

    def _create_fit_area(self) -> pn.Column:
        """Create the fit plot area.

        Returns
        -------
        pn.Column
            Column containing fit plot (if applicable).
        """
        # Placeholder for fit plot - can be expanded as needed
        return pn.Column(
            pn.pane.Markdown("### Fit Plot"),
            pn.pane.Markdown("*Fit plot functionality not yet implemented*"),
            sizing_mode="stretch_both",
        )

    @param.depends("refresh")
    def view(self) -> pn.GridSpec:
        """Create the main grid layout.

        Returns
        -------
        pn.GridSpec
            Grid layout containing all components.
        """
        # Create grid layout
        grid = pn.GridSpec(
            sizing_mode="stretch_both",
            min_height=700,
        )

        # Main ephys + histology area with linked Y-axes (columns 0-7, rows 0-10)
        grid[0:10, 0:7] = self._create_ephys_area()

        # Slice viewer (columns 7-10, rows 0-4) - independent Y-axis
        grid[0:3, 7:10] = self._create_slice_viewer_area()

        # Control area (columns 7-10, rows 4-7)
        grid[3:7, 7:10] = self._create_control_area()

        # Fit area (columns 7-10, rows 7-10)
        grid[7:10, 7:10] = self._create_fit_area()

        return grid
