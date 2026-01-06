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

from ephys_alignment_gui.web.components.reference_lines import LINE_COLORS
from ephys_alignment_gui.web.state import AppState

if TYPE_CHECKING:
    from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager

logger = logging.getLogger(__name__)


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

    # Plot type selection
    plot_type = param.Selector(
        default="aligned",
        objects=["aligned", "reference"],
        doc="Histology view type",
    )
    
    # Internal counter to force refresh when needed
    _refresh_counter = param.Integer(default=0, precedence=-1)

    def __init__(
        self,
        state: AppState,
        reference_lines: "ReferenceLinesManager | None" = None,
        **params,
    ):
        super().__init__(**params)
        self.state = state
        self._reference_lines = reference_lines

        logger.debug("Initializing HistologyPanel")

        # Cache placeholder histology data
        self._placeholder_hist_data: dict | None = None
        
        # Track last click time for double-click detection
        self._last_click_time: float = 0
        self._last_click_y: float | None = None

        # Watch plot type changes only - data loading is handled by MainLayout
        # to avoid duplicate refresh triggers
        self.param.watch(self._on_plot_type_changed, "plot_type")

        # Watch Y-range changes for axis synchronization with ephys plots
        state.param.watch(self._on_y_range_changed, "depth_y_range")

        # Watch reference lines changes if provided
        if reference_lines is not None:
            reference_lines.param.watch(
                self._on_reference_lines_changed, "lines_changed"
            )

    def _on_reference_lines_changed(self, event) -> None:
        """Handle reference lines change."""
        self._refresh_counter += 1

    def _on_plot_type_changed(self, event) -> None:
        """Handle plot type change."""
        self._refresh_counter += 1

    def _on_y_range_changed(self, event) -> None:
        """Handle Y-range change from ephys plots (for synchronization)."""
        #self._refresh_counter += 1
        y_range = self.state.depth_y_range
        self.histology_fig.update_yaxes(
            range=[y_range[0], y_range[1]],
            showticklabels=False,
            showgrid=False,
            fixedrange=False,
        )

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
            RGB image (n_pixels, width, 3) representing colored region bars.
        """
        n_pixels = 500
        width = 10  # Make bar wider for better visibility
        img = np.zeros((n_pixels, width, 3), dtype=np.uint8)
        
        if not hist_data or "region" not in hist_data:
            return img
        
        regions = hist_data.get("region", [])
        colours = hist_data.get("colour", [])
        
        logger.debug(f"Rendering {len(regions)} histology regions, y_range={y_range}")

        for i, (region, colour) in enumerate(zip(regions, colours)):
            if len(region) < 2:
                continue
            y_min, y_max = region[0], region[1]

            logger.debug(f"Region {i}: y=({y_min:.1f},{y_max:.1f}) colour={colour} name={region}")
            
            # Convert y positions to pixel indices
            idx_min = int((y_min - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
            idx_max = int((y_max - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
            idx_min = max(0, min(n_pixels - 1, idx_min))
            idx_max = max(0, min(n_pixels, idx_max))

            logger.debug(f"Region {i} pixel indices: ({idx_min}, {idx_max})")
            
            if isinstance(colour, (list, tuple)) and len(colour) >= 3:
                img[idx_min:idx_max, :, 0] = int(colour[0])
                img[idx_min:idx_max, :, 1] = int(colour[1])
                img[idx_min:idx_max, :, 2] = int(colour[2])
            else:
                img[idx_min:idx_max, :, :] = 128  # Gray default
        
        # Log summary of rendered image
        non_zero_pixels = np.sum(np.any(img > 0, axis=(1, 2)))
        logger.info(f"Rendered histology image: shape={img.shape}, non_zero_rows={non_zero_pixels}/{n_pixels}, dtype={img.dtype}")
        
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
            n_regions = 5
            region_height = (y_max - y_min) / n_regions
            
            regions = []
            colours = []
            labels = []
            
            # Color palette for regions (varied colors)
            color_palette = [
                (162, 177, 216),
                (152, 214, 249),
                (31, 157, 90),
                (89, 179, 99),
                (0, 0, 0),
            ]
            
            for i in range(n_regions):
                y_start = y_min + i * region_height
                y_end = y_start + region_height
                regions.append([y_start, y_end])
                colours.append(color_palette[i % len(color_palette)])
                labels.append([0, "---"])
            
            self._placeholder_hist_data = {
                "region": regions,
                "colour": colours,
                "axis_label": labels
            }
        return self._placeholder_hist_data

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
            
            # Extend line far beyond visible area so endpoints are not accessible
            fig.add_shape(
                type="line",
                x0=-10,
                x1=10,
                xref="paper",  # Paper coordinates: 0-1 is visible, beyond is clipped
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
        # Select aligned or reference histology based on plot_type
        if self.plot_type == "aligned":
            hist_data = self.state.hist_data
        else:  # "reference"
            hist_data = self.state.hist_data_ref
        
        y_range = self._get_y_range()
        
        # Use placeholder data if no real data
        regions = hist_data.get("region") if hist_data else None
        if hist_data is None or regions is None or len(regions) == 0:
            hist_data = self._get_placeholder_hist_data()
            logger.info(f"Using placeholder histology data (real data not available)")
        else:
            logger.info(f"Using {self.plot_type} histology data with {len(regions)} regions")

        logger.debug(f"Creating histology figure with y_range {y_range}")
        
        fig = go.Figure()
        
        # Get regions and colours from hist_data (already validated above)
        regions = hist_data.get("region", [])
        colours = hist_data.get("colour", [])
        axis_labels = hist_data.get("axis_label", [])

        # Add each brain region as a bar (cannot be edited, unlike shapes)
        # We'll use horizontal bars spanning the full width

        text_x_positions = []
        text_y_positions = []
        text_labels = []

        for i in range(len(regions)):
            region = regions[i]
            colour = colours[i]
            label = axis_labels[i]

            logger.debug(f"Processing region {i}: {region} colour={colour} label={label}")
            
            if len(region) < 2:
                continue

            y_min, y_max = region[0], region[1]
            y_center = (y_min + y_max) / 2
            height = y_max - y_min

            colour_str = f"rgb({colour[0]},{colour[1]},{colour[2]})"
            
            logger.debug(f"Adding region bar {i}: y=({y_min:.1f},{y_max:.1f}) colour={colour} label={label}")

            # Add as a horizontal bar trace
            fig.add_trace(
                  go.Bar(
                    x=[1],  # Width of 1 to span the plot
                    y=[y_center],
                    width=[height],  # Bar height in y-direction
                    marker=dict(color=colour_str, line=dict(width=0)),
                    orientation='h',
                    showlegend=False,
                    base=0,
                    hoverinfo='skip',
                )
            )

            text_x_positions.append(0.5)  # Centered in x
            text_y_positions.append(y_center)
            text_labels.append(label[1])

        fig.add_trace(go.Scatter(
            x=text_x_positions,
            y=text_y_positions,
            mode="text",
            text=text_labels,
            textposition="middle center"
        ))
            
        logger.debug(f'Added {len(regions)} region bars')

        # Set axis ranges using physical coordinates
        fig.update_xaxes(
            visible=False,
            range=[0, 1],
            scaleanchor=None,
        )
        fig.update_yaxes(
            visible=True,
            range=[y_range[0], y_range[1]],
            showgrid=False,
            showticklabels=False,
            autorange=False,
            scaleanchor=None,
            fixedrange=False,  # Allow zoom
        )

        logger.debug(f"Creating background heatmap with y_range: {fig.layout.yaxis.range}")
        logger.debug(f"Creating background heatmap with x_range: {fig.layout.xaxis.range}")

        # Add invisible heatmap covering full plot area to capture all clicks
        # Heatmaps respond to clicks anywhere within their bounds
        y_invisible = np.linspace(fig.layout.yaxis.range[0], fig.layout.yaxis.range[1], 100)
        x_invisible =  np.linspace(fig.layout.xaxis.range[0], fig.layout.xaxis.range[1], 100)
        z_invisible = np.zeros((len(x_invisible), len(y_invisible)))
        
        fig.add_trace(
            go.Heatmap(
                x=x_invisible,
                y=y_invisible,
                z=z_invisible,
                colorscale=[[0, "white"], [1, "white"]],
                showscale=False,
                hovertemplate="",
                opacity=0,
                hoverinfo='none',
            )
        )

        # Add reference lines if available
        self._add_reference_lines_to_figure(fig)

        logger.debug(f'Final axis ranges - X: {fig.layout.xaxis.range}, Y: {fig.layout.yaxis.range}')
        
        fig.update_layout(
            width=100,
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(fixedrange=True, constrain='domain'),
            yaxis=dict(scaleanchor=None, constrain='domain'),
            hovermode="closest",
            clickmode="event",  # Generate click events even on empty space
            dragmode="pan",  # Allow panning, but shapes can still be dragged
            barmode='overlay',  # Overlay bars instead of stacking
            bargap=0,  # No gap between bars
        )
        
        return fig
    
    def _on_click(self, click_data: dict) -> None:
        """Handle Plotly click events for double-click line creation.
        
        Parameters
        ----------
        click_data : dict
            Click event data from Plotly containing point coordinates.
        """
        logger.info(f"HistologyPanel._on_click called with data: {click_data}")
        
        if not click_data or not self._reference_lines:
            logger.info(f"Ignoring click: click_data={bool(click_data)}, reference_lines={bool(self._reference_lines)}")
            return
        
        # Extract Y coordinate from click (already in physical coordinates)
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
        
        # Collect shape Y-position changes (handle both y0 and y1 to keep lines horizontal)
        shape_y_changes: dict[int, float] = {}
        for key, value in relayout_data.items():
            if key.startswith("shapes[") and (".y0" in key or ".y1" in key):
                try:
                    shape_idx = int(key.split("[")[1].split("]")[0])
                    # Use the value (if both y0 and y1 change, last one wins - they should be same)
                    shape_y_changes[shape_idx] = value
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse shape drag event: {e}")
        
        # Apply shape position updates (track position in histology)
        for shape_idx, new_y in shape_y_changes.items():
            if self._reference_lines is not None and 0 <= shape_idx < len(self._reference_lines.lines):
                # Get current feature position
                y_feat, _ = self._reference_lines.lines[shape_idx]
                # Update track position (y_feat stays the same)
                self._reference_lines.update_line_position(shape_idx, y_feat, new_y)
                logger.debug(f"Updated line {shape_idx} track position to {new_y:.1f}")

        # Parse Y-axis zoom/pan events for synchronization
        if "yaxis.range[0]" in relayout_data:
            y_min = relayout_data.get("yaxis.range[0]")
            y_max = relayout_data.get("yaxis.range[1]")
            if y_min is not None and y_max is not None:
                # Only update if range actually changed (avoid infinite loop)
                current_range = self.state.depth_y_range
                if current_range != (y_min, y_max):
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

    @param.depends("_refresh_counter", "plot_type")
    def histology_view(self) -> pn.pane.Plotly:
        """Return the Plotly histology figure.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing the histology visualization.
        """
        logger.info(f"Creating histology figure (refresh_counter={self._refresh_counter}, plot_type={self.plot_type})")
        fig = self._create_figure()
        
        pane = pn.pane.Plotly(
            fig,
            sizing_mode="stretch_both",
            config={
                "scrollZoom": True,
                "displayModeBar": False,
                "displaylogo": False,
                "editable": True,  # Enable editing
                "doubleClick": False,  # Disable double-click reset/zoom to allow custom handling
                "edits": {
                    "shapePosition": True,  # Allow dragging shapes (reference lines)
                    "annotationPosition": False,
                    "annotationTail": False,
                    "annotationText": False,
                    "axisTitleText": False,  # Disable axis title editing
                    "colorbarPosition": False,
                    "colorbarTitleText": False,
                    "legendPosition": False,
                    "legendText": False,
                    "titleText": False,  # Disable plot title editing
                },
                "modeBarButtonsToRemove": ["select2d", "lasso2d"],
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

        self.histology_fig = fig  # Store for later access
        
        return pane
