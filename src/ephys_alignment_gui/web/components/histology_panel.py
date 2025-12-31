"""Histology panel component for the web frontend.

Displays brain region boundaries along the probe trajectory as colored
bars using Plotly.

Supports optional reference lines overlay for alignment workflow.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import panel as pn
import param
import plotly.graph_objects as go

from ephys_alignment_gui.web.state import AppState

if TYPE_CHECKING:
    from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager

logger = logging.getLogger(__name__)

# Line colors for reference lines
LINE_COLORS = [
    "#e41a1c",  # red
    "#377eb8",  # blue
    "#4daf4a",  # green
    "#984ea3",  # purple
    "#ff7f00",  # orange
    "#ffff33",  # yellow
    "#a65628",  # brown
    "#f781bf",  # pink
]


class HistologyPanel(param.Parameterized):
    """Component for displaying brain region histology.

    Renders colored bars representing brain regions along the probe
    trajectory, with optional region labels. Shows both the current
    (aligned) and reference (original) histology views.

    Supports optional reference lines overlay via ReferenceLinesManager.

    Parameters
    ----------
    state : AppState
        Shared application state.
    reference_lines : ReferenceLinesManager, optional
        Reference lines manager for alignment workflow. If provided,
        double-click on plot will add reference lines (at track position).
    """

    # Trigger manual refresh
    refresh = param.Event(doc="Trigger plot refresh")

    # Plot type selection
    plot_type = param.Selector(
        default="aligned",
        objects=["aligned", "reference"],
        doc="Histology view type",
    )

    def __init__(
        self,
        state: AppState,
        reference_lines: "ReferenceLinesManager | None" = None,
        **params,
    ):
        super().__init__(**params)
        self.state = state
        self._reference_lines = reference_lines

        # Cache placeholder histology data
        self._placeholder_hist_data: dict | None = None
        
        # Track last click time for double-click detection
        self._last_click_time: float = 0
        self._last_click_y: float | None = None

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        self.param.watch(self._on_plot_type_changed, "plot_type")

        # Watch reference lines changes if provided
        if reference_lines is not None:
            reference_lines.param.watch(
                self._on_reference_lines_changed, "lines_changed"
            )

    def _on_reference_lines_changed(self, event) -> None:
        """Handle reference lines change."""
        self.param.trigger("refresh")

    def _on_plot_type_changed(self, event) -> None:
        """Handle plot type change."""
        self.param.trigger("refresh")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new:
            self.param.trigger("refresh")

    def _render_histology_to_image(self, hist_data: dict, y_range: tuple) -> np.ndarray:
        """Render histology regions as RGB numpy array.
        
        Parameters
        ----------
        hist_data : dict
            Dictionary with 'region' and 'colour' keys.
        y_range : tuple
            (y_min, y_max) depth range.
        
        Returns
        -------
        np.ndarray
            RGB image (n_pixels, 1, 3) representing colored region bars.
        """
        n_pixels = 500
        img = np.zeros((n_pixels, 1, 3), dtype=np.uint8)
        
        if not hist_data or "region" not in hist_data:
            return img
        
        regions = hist_data.get("region", [])
        colours = hist_data.get("colour", [])
        
        for region, colour in zip(regions, colours):
            if len(region) < 2:
                continue
            y_min, y_max = region[0], region[1]
            
            # Convert y positions to pixel indices
            idx_min = int((y_min - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
            idx_max = int((y_max - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
            idx_min = max(0, min(n_pixels - 1, idx_min))
            idx_max = max(0, min(n_pixels, idx_max))
            
            if isinstance(colour, (list, tuple)) and len(colour) >= 3:
                img[idx_min:idx_max, 0, 0] = int(colour[0])
                img[idx_min:idx_max, 0, 1] = int(colour[1])
                img[idx_min:idx_max, 0, 2] = int(colour[2])
            else:
                img[idx_min:idx_max, 0, :] = 128  # Gray default
        
        return img

    def _get_y_range(self) -> tuple:
        """Get the shared Y-axis range for depth plots."""
        return self.state.depth_y_range

    def _get_placeholder_hist_data(self) -> dict:
        """Get cached placeholder histology data with colorful regions.
        
        Returns
        -------
        dict
            Dictionary with 'region' and 'colour' keys representing brain regions.
        """
        if self._placeholder_hist_data is None:
            # Create 10 colorful stacked regions across the probe depth
            y_min, y_max = -100, 3940
            n_regions = 10
            region_height = (y_max - y_min) / n_regions
            
            regions = []
            colours = []
            
            # Color palette for regions (varied colors)
            color_palette = [
                (255, 100, 100),  # Light red
                (100, 150, 255),  # Light blue
                (150, 255, 150),  # Light green
                (255, 200, 100),  # Orange
                (200, 150, 255),  # Purple
                (255, 255, 100),  # Yellow
                (100, 255, 200),  # Cyan
                (255, 150, 200),  # Pink
                (150, 200, 150),  # Sage green
                (200, 200, 255),  # Lavender
            ]
            
            for i in range(n_regions):
                y_start = y_min + i * region_height
                y_end = y_start + region_height
                regions.append([y_start, y_end])
                colours.append(color_palette[i % len(color_palette)])
            
            self._placeholder_hist_data = {
                "region": regions,
                "colour": colours,
            }
        return self._placeholder_hist_data

    def _create_placeholder_image(self, y_range: tuple) -> np.ndarray:
        """Create placeholder histology image with gray gradient.
        
        Parameters
        ----------
        y_range : tuple
            (y_min, y_max) depth range.
            
        Returns
        -------
        np.ndarray
            RGB placeholder image.
        """
        n_pixels = 500
        img = np.zeros((n_pixels, 1, 3), dtype=np.uint8)
        
        # Create alternating gray bars
        bar_height = n_pixels // 10
        for i in range(10):
            gray = 180 + (i % 2) * 40
            img[i * bar_height:(i + 1) * bar_height, 0, :] = gray
        
        return img

    def _add_reference_lines_to_figure(self, fig: go.Figure) -> None:
        """Add draggable reference lines at track positions.
        
        For histology plots, lines are shown at track positions (independent
        from ephys feature positions).
        
        Parameters
        ----------
        fig : go.Figure
            Plotly figure to add shapes to.
        """
        if self._reference_lines is None or not self._reference_lines.lines:
            return
        
        for i, (_, y_track) in enumerate(self._reference_lines.lines):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            is_selected = i == self._reference_lines.selected_index
            
            fig.add_shape(
                type="line",
                x0=0,
                x1=1,
                xref="x",  # Use data coordinates
                y0=y_track,
                y1=y_track,
                yref="y",
                line=dict(
                    color=color,
                    width=3 if is_selected else 2,
                    dash="solid" if is_selected else "dash",
                ),
                editable=True,
                name=f"line_{i}",
            )

    def _create_figure(self) -> go.Figure:
        """Create Plotly figure for histology panel.
        
        Returns
        -------
        go.Figure
            Plotly figure with histology RGB image and reference lines.
        """
        hist_data = self.state.hist_data
        y_range = self._get_y_range()
        
        # Use placeholder data if no real data
        if hist_data is None or not hist_data.get("region"):
            hist_data = self._get_placeholder_hist_data()
        
        # Render histology as RGB image
        img = self._render_histology_to_image(hist_data, y_range)
        
        # Flip image vertically because Plotly Image trace has origin at top-left
        # but we want y-axis to increase upward
        img = np.flip(img, axis=0)
        
        fig = go.Figure()
        
        # Add RGB image
        fig.add_trace(
            go.Image(
                z=img,
                x0=0,
                dx=1,
                y0=y_range[0],
                dy=(y_range[1] - y_range[0]) / img.shape[0],
            )
        )
        
        # Add reference lines if available
        self._add_reference_lines_to_figure(fig)
        
        fig.update_xaxes(visible=False, range=[0, 1])
        fig.update_yaxes(
            range=[y_range[0], y_range[1]],
            visible=True,
            showgrid=False,
            showticklabels=False,
        )
        
        fig.update_layout(
            width=100,
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(fixedrange=True),
            yaxis=dict(fixedrange=False),  # Allow zoom
        )
        
        return fig
    
    def _on_click(self, click_data: dict) -> None:
        """Handle Plotly click events for double-click line creation.
        
        Parameters
        ----------
        click_data : dict
            Click event data from Plotly containing point coordinates.
        """
        if not click_data or not self._reference_lines:
            return
        
        # Extract Y coordinate from click
        points = click_data.get("points", [])
        if not points:
            return
        
        y_clicked = points[0].get("y")
        if y_clicked is None:
            return
        
        # Detect double-click (within 500ms)
        import time
        current_time = time.time()
        time_diff = current_time - self._last_click_time
        
        if time_diff < 0.5 and self._last_click_y is not None:
            # Double-click detected - add reference line
            y_pos = (y_clicked + self._last_click_y) / 2  # Average of two clicks
            self._reference_lines.add_line(y_pos)
            logger.info(f"Double-click on histology: added reference line at y={y_pos:.1f}")
            
            # Reset click tracking
            self._last_click_time = 0
            self._last_click_y = None
        else:
            # First click - store it
            self._last_click_time = current_time
            self._last_click_y = y_clicked
    
    def _on_relayout(self, relayout_data: dict) -> None:
        """Handle Plotly relayout events for Y-range sync and shape drags.
        
        Parameters
        ----------
        relayout_data : dict
            Relayout event data from Plotly.
        """
        if not relayout_data:
            return
        
        # Parse shape drag events (track position updates)
        for key, value in relayout_data.items():
            if key.startswith("shapes[") and ".y0" in key:
                try:
                    shape_idx = int(key.split("[")[1].split("]")[0])
                    if self._reference_lines is not None and 0 <= shape_idx < len(self._reference_lines.lines):
                        # Get current feature position
                        y_feat, _ = self._reference_lines.lines[shape_idx]
                        # Update track position (y_feat stays the same)
                        self._reference_lines.update_line_position(shape_idx, y_feat, value)
                        logger.debug(f"Updated line {shape_idx} track position to {value:.1f}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse shape drag event: {e}")
            
            # Parse Y-axis zoom/pan events for synchronization
            elif key == "yaxis.range[0]":
                y_min = relayout_data.get("yaxis.range[0]")
                y_max = relayout_data.get("yaxis.range[1]")
                if y_min is not None and y_max is not None:
                    self.state.depth_y_range = (y_min, y_max)
                    logger.debug(f"Histology updated Y-range to ({y_min:.1f}, {y_max:.1f})")

    def controls(self) -> pn.widgets.Select:
        """Return histology type selector in fixed-width container.
        
        Width matches the histology plot width (100px).
        """
        selector = pn.widgets.Select(
            name="Histology",
            options={"Aligned": "aligned", "Reference": "reference"},
            value=self.plot_type,
            width=80,
        )
        selector.link(self, value="plot_type")
        # Wrap in Column with fixed width matching plot width
        return selector

    @param.depends("refresh")
    def view(self) -> pn.pane.Plotly:
        """Return the Plotly histology figure.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing the histology visualization.
        """
        fig = self._create_figure()
        
        pane = pn.pane.Plotly(
            fig,
            sizing_mode="stretch_both",
            config={
                "scrollZoom": True,
                "displayModeBar": False,
                "displaylogo": False,
                "editable": True,  # Enable shape editing
            },
        )
        
        # Attach relayout callback for Y-range syncing and shape drags
        pane.param.watch(
            lambda event: self._on_relayout(event.new), "relayout_data"
        )
        # Attach click callback for double-click line creation
        pane.param.watch(
            lambda event: self._on_click(event.new), "click_data"
        )
        
        return pane
