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
from ephys_alignment_gui.web.components.fit_plot import FitPlot
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
        self.fit_plot = FitPlot(state, reference_lines=self.reference_lines)

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
        print(f"DEBUG: MainLayout._setup_event_handlers, alignment_controls={id(self.alignment_controls)}")
        # Alignment control events
        self.alignment_controls.param.watch(
            self._on_fit_clicked, "fit_clicked"
        )
        self.alignment_controls.param.watch(
            self._on_offset_clicked, "offset_clicked"
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

        # Use existing ephys_alignment if already created by data_selection_panel
        ephys_alignment = self.state.ephys_alignment
        if ephys_alignment is None:
            # Create alignment if not already done
            shank_idx = self.state.current_shank
            try:
                track_annotations = loaddata.get_track_annotations(shank_idx)
            except Exception as e:
                logger.warning(f"No track annotations available for alignment: {e}")
                return

            try:
                chn_depths = loaddata.chn_coords_all[:, 1] if loaddata.chn_coords_all is not None else None
                ephys_alignment = EphysAlignment(
                    track_annotations_ras=track_annotations,
                    chn_depths=chn_depths,
                    brain_atlas=loaddata.brain_atlas,
                )
                self.state.ephys_alignment = ephys_alignment
            except Exception as e:
                logger.exception(f"Failed to initialize EphysAlignment: {e}")
                return

        # Initialize alignment history
        self._track_history = [np.copy(ephys_alignment.track_init)]
        self._feature_history = [np.copy(ephys_alignment.feature_init)]
        self._current_align_idx = 0

        # Update state with initial feature/track arrays
        self.state.features = self._feature_history[0]
        self.state.track = self._track_history[0]

        # Update histology data (may have been set by data_selection_panel,
        # but main_layout manages its own history tracking)
        self._update_histology_data()

        # Update slice viewer
        self._update_slice_viewer()

        logger.info("Alignment state initialized successfully")

    def _update_slice_viewer(self) -> None:
        """Refresh the slice viewer."""
        # Load slice data using the interpolated track
        try:
            slice_data, _ = self.state.loaddata.get_slice_images(
                self.state.ephys_alignment.track_interpolation_ras
            )
            self.state.slice_data = slice_data
            logger.info("Slice data loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load slice data: {e}")
            self.state.slice_data = None

        # Explicitly refresh slice viewer
        self.slice_viewer._refresh_counter += 1

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
            self.histology_panel._refresh_counter += 1
            logger.debug(f"Updated histology data at alignment index {idx}")
        except Exception as e:
            logger.exception(f"Failed to update histology data: {e}")

    def _on_fit_clicked(self, event) -> None:
        """Handle fit button click - apply scaling based on reference lines."""
        print(f"DEBUG: MainLayout._on_fit_clicked called! event={event}")
        logger.debug("Fit button clicked")
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

        # Update state with current feature/track arrays
        self.state.features = new_features
        self.state.track = new_track

        # Update histology display
        self._update_histology_data()

        # Refresh fit plot
        self.fit_plot.refresh()

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

        # Update state with current feature/track arrays
        self.state.features = prev_features
        self.state.track = new_track

        self._update_histology_data()

        # Refresh fit plot
        self.fit_plot.refresh()

        logger.info(f"Offset applied - alignment index now {self._current_align_idx}")
        self.param.trigger("refresh")

    def _on_next_clicked(self, event) -> None:
        """Handle next button click - move forward in alignment history."""
        if self._current_align_idx < len(self._track_history) - 1:
            self._current_align_idx += 1
            self.state.current_idx = self._current_align_idx
            # Update state with feature/track arrays for this history index
            self.state.features = self._feature_history[self._current_align_idx]
            self.state.track = self._track_history[self._current_align_idx]
            self._update_histology_data()
            self.fit_plot.refresh()
            self.param.trigger("refresh")

    def _on_prev_clicked(self, event) -> None:
        """Handle previous button click - move backward in alignment history."""
        if self._current_align_idx > 0:
            self._current_align_idx -= 1
            self.state.current_idx = self._current_align_idx
            # Update state with feature/track arrays for this history index
            self.state.features = self._feature_history[self._current_align_idx]
            self.state.track = self._track_history[self._current_align_idx]
            self._update_histology_data()
            self.fit_plot.refresh()
            self.param.trigger("refresh")

    def _on_reset_clicked(self, event) -> None:
        """Handle reset button click."""
        # Reset alignment to initial state
        if self.state.ephys_alignment is not None:
            ephys_align = self.state.ephys_alignment
            self._track_history = [np.copy(ephys_align.track_init)]
            self._feature_history = [np.copy(ephys_align.feature_init)]
            self._current_align_idx = 0
            self.state.current_idx = 0
            self.state.total_idx = 0
            # Update state with initial feature/track arrays
            self.state.features = self._feature_history[0]
            self.state.track = self._track_history[0]
            self._update_histology_data()
            
            # Reset probe bounds from alignment track extent (convert m to µm)
            probe_tip_um = ephys_align.track_extent[0] * 1e6
            probe_top_um = ephys_align.track_extent[1] * 1e6
            self.state.probe_tip = probe_tip_um
            self.state.probe_top = probe_top_um
            
            # Reset depth_y_range from probe bounds with padding
            padding = 100  # µm
            self.state.depth_y_range = (probe_tip_um - padding, probe_top_um + padding)

        # Clear reference lines
        self.reference_lines.clear_lines()

        # Refresh fit plot
        self.fit_plot.refresh()

        logger.info("Alignment reset to initial state")
        self.param.trigger("refresh")

    def _on_delete_line_clicked(self, event) -> None:
        """Handle delete line button click."""
        self.reference_lines.remove_last_line()
        self.param.trigger("refresh")

    def _create_linked_depth_plots(self) -> pn.Row:
        """Create all depth plots with linked Y-axes.

        Combines ephys plots (image, line, probe) and histology into
        separate columns with their controls. Each plot is wrapped in
        pn.bind to make it reactive to its own _refresh_counter.

        Returns
        -------
        pn.Row
            Row containing controls and plots.
        """
        # Get controls (static widgets)
        image_selector = self.ephys_plots.controls(selector='image')
        line_selector = self.ephys_plots.controls(selector='line')
        probe_selector = self.ephys_plots.controls(selector='probe')
        hist_selector = self.histology_panel.controls()

        # Wrap each view method in pn.bind to make it reactive.
        # Each plot only updates when its own parameters change.
        # Use lambdas because the view methods have @param.depends decorators
        # which conflict with direct pn.bind usage.
        image_view = pn.bind(
            lambda _1, _2: self.ephys_plots.image_view(),
            self.ephys_plots.param._image_refresh_counter,
            self.ephys_plots.param.image_plot_type,
        )
        line_view = pn.bind(
            lambda _1, _2: self.ephys_plots.line_view(),
            self.ephys_plots.param._line_refresh_counter,
            self.ephys_plots.param.line_plot_type,
        )
        probe_view = pn.bind(
            lambda _1, _2: self.ephys_plots.probe_view(),
            self.ephys_plots.param._probe_refresh_counter,
            self.ephys_plots.param.probe_plot_type,
        )
        hist_view = pn.bind(
            lambda _1, _2: self.histology_panel.histology_view(),
            self.histology_panel.param._refresh_counter,
            self.histology_panel.param.plot_type,
        )

        # Create columns with controls above each plot (no margins for tight layout)
        image_column = pn.Column(
            image_selector,
            image_view,
            sizing_mode="stretch_width",
            height=600,
            margin=0,
        )
        line_column = pn.Column(
            line_selector,
            line_view,
            sizing_mode="fixed",
            height=600,
            margin=0,
        )
        probe_column = pn.Column(
            probe_selector,
            probe_view,
            sizing_mode="fixed",
            height=600,
            margin=0,
        )
        hist_column = pn.Column(
            hist_selector,
            hist_view,
            sizing_mode="fixed",
            height=600,
            margin=0,
        )

        # Create plots row with no spacing between columns
        plots_row = pn.Row(
            image_column,
            line_column,
            probe_column,
            hist_column,
            sizing_mode="stretch_width",
            margin=0,
        )

        return plots_row

    def _create_ephys_area(self) -> pn.Column:
        """Create the ephys and histology visualization area with linked axes.

        Returns
        -------
        pn.Column
            Column containing linked depth plots and controls.
        """
        # Create the linked depth plots - each view is wrapped in pn.bind
        # to be reactive to its specific parameters only.
        plot_view = self._create_linked_depth_plots()

        # Reference lines controls below the plots
        ref_lines_view = self.reference_lines.controls()
        ref_lines_section = pn.Row(
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
        # Return the cached view directly (already a Column)
        # The view is cached inside AlignmentControls to preserve button instances
        if self._control_area is None:
            print(f"DEBUG: _create_control_area, alignment_controls={id(self.alignment_controls)}")
            self._control_area = self.alignment_controls.view()
        return self._control_area
    
    def _create_slice_viewer_area(self) -> pn.Column:
        """Create the slice viewer area.

        Returns
        -------
        pn.Column
            Column containing the slice viewer with its selector.
        """
        slice_view = pn.bind(
            lambda _: self.slice_viewer.view(),
            self.slice_viewer.param._refresh_counter,
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
            Column containing fit plot.
        """
        # Wrap fit plot view in pn.bind for reactivity
        fit_view = pn.bind(
            lambda _: self.fit_plot.view(),
            self.fit_plot.param._refresh_counter,
        )

        return pn.Column(
            self.fit_plot.controls(),
            fit_view,
            sizing_mode="stretch_both",
        )

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
        grid[3:5, 7:10] = self._create_control_area()

        # Fit area (columns 7-10, rows 7-10)
        grid[5:10, 7:10] = self._create_fit_area()

        return grid
