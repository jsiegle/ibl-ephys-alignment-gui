"""Electrophysiology plot components using Plotly for the web frontend.

Converts PlotData output to Plotly figures for display in Panel.
Displays three sub-plots in a single linked figure: 2D image, line plot, and probe plot.

Supports draggable reference lines for alignment workflow.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import panel as pn
import param
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ephys_alignment_gui.visualization.plot_data import PlotData
from ephys_alignment_gui.web.state import AppState

if TYPE_CHECKING:
    from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager

logger = logging.getLogger(__name__)

# Plot type options for each sub-plot
IMAGE_PLOT_OPTIONS = {
    "Firing Rate": "firing_rate",
    "Amplitude (scatter)": "amplitude",
    "Cluster FR vs Depth": "cluster_fr",
    "Cluster P2T vs Depth": "cluster_p2t",
    "Cluster Amp vs Depth": "cluster_amp",
    "Spike Correlation": "spike_correlation",
    "RMS AP": "rms_ap",
    "RMS LF": "rms_lf",
    "LFP Spectrum": "lfp_spectrum",
}

LINE_PLOT_OPTIONS = {
    "Firing Rate": "firing_rate",
    "Amplitude": "amplitude",
}

PROBE_PLOT_OPTIONS = {
    "RMS AP": "rms_ap",
    "RMS LF": "rms_lf",
    "LFP 0-4 Hz": "lfp_0_4",
    "LFP 4-10 Hz": "lfp_4_10",
    "LFP 10-30 Hz": "lfp_10_30",
    "LFP 30-80 Hz": "lfp_30_80",
    "LFP 80-200 Hz": "lfp_80_200",
}

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


class EphysPlots(param.Parameterized):
    """Component for displaying electrophysiology data plots using Plotly.

    Renders three sub-plots side by side:
    - 2D image plot (firing rate, RMS, correlation, etc.)
    - Line plot (firing rate or amplitude vs depth)
    - Probe plot (RMS or LFP band power on probe geometry)

    Each sub-plot has its own Plot Type selector.

    Supports draggable reference lines for alignment workflow.

    Parameters
    ----------
    state : AppState
        Shared application state.
    reference_lines : ReferenceLinesManager, optional
        Reference lines manager for alignment workflow.
    """

    # Trigger manual refresh
    refresh = param.Event(doc="Trigger plot refresh")

    # Individual plot type selections
    image_plot_type = param.Selector(
        default="firing_rate",
        objects=list(IMAGE_PLOT_OPTIONS.values()),
        doc="Type of 2D image plot to display",
    )
    line_plot_type = param.Selector(
        default="firing_rate",
        objects=list(LINE_PLOT_OPTIONS.values()),
        doc="Type of line plot to display",
    )
    probe_plot_type = param.Selector(
        default="rms_ap",
        objects=list(PROBE_PLOT_OPTIONS.values()),
        doc="Type of probe plot to display",
    )

    def __init__(
        self,
        state: AppState,
        reference_lines: "ReferenceLinesManager | None" = None,
        **params,
    ):
        super().__init__(**params)
        self.state = state
        self._plot_data: PlotData | None = None
        self._reference_lines = reference_lines

        # Cache placeholder data (generated once)
        self._placeholder_image_data: dict | None = None
        self._placeholder_line_data: dict | None = None
        self._placeholder_probe_data: dict | None = None
        
        # Track last click time for double-click detection
        self._last_click_time: float = 0
        self._last_click_y: float | None = None

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        state.param.watch(self._on_y_range_changed, "depth_y_range")

        # Watch local plot type changes
        self.param.watch(self._on_plot_type_changed, "image_plot_type")
        self.param.watch(self._on_plot_type_changed, "line_plot_type")
        self.param.watch(self._on_plot_type_changed, "probe_plot_type")

        # Watch reference lines changes if provided
        if reference_lines is not None:
            reference_lines.param.watch(
                self._on_reference_lines_changed, "lines_changed"
            )

    def _on_reference_lines_changed(self, event) -> None:
        """Handle reference lines change."""
        self.param.trigger("refresh")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new and self.state.data is not None:
            self._initialize_plot_data()
            self.param.trigger("refresh")

    def _on_y_range_changed(self, event) -> None:
        """Handle Y-range change from another plot (for synchronization)."""
        self.param.trigger("refresh")

    def _on_plot_type_changed(self, event) -> None:
        """Handle plot type change."""
        self.param.trigger("refresh")

    def _initialize_plot_data(self) -> None:
        """Initialize PlotData instance from loaded data."""
        if self.state.probe_path is None or self.state.data is None:
            return

        try:
            self._plot_data = PlotData(
                self.state.probe_path,
                self.state.data,
                self.state.current_shank,
            )
            self.state.plot_data = self._plot_data
            logger.info("PlotData initialized")
        except Exception as e:
            logger.exception(f"Failed to initialize PlotData: {e}")

    def _get_image_data(self, plot_type: str) -> dict | None:
        """Get 2D image/scatter plot data for the specified type."""
        if self._plot_data is None:
            return None

        try:
            if plot_type == "firing_rate":
                return self._plot_data.get_fr_img()
            elif plot_type == "amplitude":
                return self._plot_data.get_depth_data_scatter()
            elif plot_type == "cluster_fr":
                data, _, _ = self._plot_data.get_fr_p2t_data_scatter()
                return data
            elif plot_type == "cluster_p2t":
                _, data, _ = self._plot_data.get_fr_p2t_data_scatter()
                return data
            elif plot_type == "cluster_amp":
                _, _, data = self._plot_data.get_fr_p2t_data_scatter()
                return data
            elif plot_type == "spike_correlation":
                return self._plot_data.get_spike_correlation_data_img()
            elif plot_type == "rms_ap":
                data, _ = self._plot_data.get_rms_data_img_probe("AP")
                return data
            elif plot_type == "rms_lf":
                data, _ = self._plot_data.get_rms_data_img_probe("LF")
                return data
            elif plot_type == "lfp_spectrum":
                data, _ = self._plot_data.get_lfp_spectrum_data("lf")
                return data
            else:
                logger.warning(f"Unknown image plot type: {plot_type}")
                return None
        except Exception as e:
            logger.exception(f"Error getting image data for {plot_type}: {e}")
            return None

    def _get_line_data(self, plot_type: str) -> dict | None:
        """Get line plot data for the specified type."""
        if self._plot_data is None:
            return None

        try:
            fr_data, amp_data = self._plot_data.get_fr_amp_data_line()
            if plot_type == "firing_rate":
                return fr_data
            elif plot_type == "amplitude":
                return amp_data
            return None
        except Exception as e:
            logger.exception(f"Error getting line data for {plot_type}: {e}")
            return None

    def _get_probe_data(self, plot_type: str) -> dict | None:
        """Get probe plot data for the specified type."""
        if self._plot_data is None:
            return None

        try:
            if plot_type == "rms_ap":
                _, data = self._plot_data.get_rms_data_img_probe("AP")
                return data
            elif plot_type == "rms_lf":
                _, data = self._plot_data.get_rms_data_img_probe("LF")
                return data
            elif plot_type.startswith("lfp_"):
                _, data_dict = self._plot_data.get_lfp_spectrum_data("lf")
                band_map = {
                    "lfp_0_4": "0 - 4 Hz",
                    "lfp_4_10": "4 - 10 Hz",
                    "lfp_10_30": "10 - 30 Hz",
                    "lfp_30_80": "30 - 80 Hz",
                    "lfp_80_200": "80 - 200 Hz",
                }
                band_key = band_map.get(plot_type)
                if band_key and data_dict:
                    return data_dict.get(band_key)
                return None
            else:
                logger.warning(f"Unknown probe plot type: {plot_type}")
                return None
        except Exception as e:
            logger.exception(f"Error getting probe data for {plot_type}: {e}")
            return None

    def _get_placeholder_image_data(self) -> dict:
        """Get cached placeholder image data when no real data is loaded."""
        if self._placeholder_image_data is None:
            # Use fixed range for placeholder (full probe depth)
            y_min, y_max = -100, 3940
            # Create a gradient pattern
            n_y = 200
            n_x = 50
            y = np.linspace(y_min, y_max, n_y)
            x = np.linspace(0, 100, n_x)
            
            # Create interesting pattern (sine wave gradient)
            xx, yy = np.meshgrid(x, y)
            img = np.sin(yy / 500) * 0.5 + np.sin(xx / 10) * 0.3 + 0.5
            
            self._placeholder_image_data = {
                "img": img.T,
                "scale": [x[1] - x[0], (y_max - y_min) / n_y],
                "offset": [0, y_min],
                "levels": (0, 1),
                "cmap": "Viridis",
            }
        return self._placeholder_image_data

    def _get_placeholder_line_data(self) -> dict:
        """Get cached placeholder line data when no real data is loaded."""
        if self._placeholder_line_data is None:
            # Use fixed range for placeholder (full probe depth)
            y_min, y_max = -100, 3940
            y = np.linspace(y_min, y_max, 100)
            # Random walk
            np.random.seed(42)
            x = np.cumsum(np.random.randn(100) * 0.5) + 50
            
            self._placeholder_line_data = {"x": x, "y": y}
        return self._placeholder_line_data

    def _get_placeholder_probe_data(self) -> dict:
        """Get cached placeholder probe data when no real data is loaded."""
        if self._placeholder_probe_data is None:
            # Use fixed range for placeholder (full probe depth)
            y_min, y_max = -100, 3940
            n_y = 200
            y = np.linspace(y_min, y_max, n_y)
            
            # Create a simple vertical gradient (single bank)
            img = np.linspace(0, 1, n_y).reshape(-1, 1).T
            
            self._placeholder_probe_data = {
                "img": [img],
                "scale": np.array([[10, (y_max - y_min) / n_y]]),
                "offset": np.array([[0, y_min]]),
                "levels": (0, 1),
                "cmap": "Viridis",
            }
        return self._placeholder_probe_data

    def _create_image_figure(self) -> go.Figure:
        """Create the image plot figure."""
        fig = go.Figure()
        y_range = self.state.depth_y_range
        image_data = self._get_image_data(self.image_plot_type)

        # Use placeholder data if no real data
        if image_data is None:
            image_data = self._get_placeholder_image_data()

        # Add image or scatter trace
        if image_data and "img" in image_data:
            self._add_image_trace(fig, image_data)
        elif image_data and "x" in image_data and "y" in image_data:
            self._add_scatter_trace(fig, image_data)

        # Add reference lines
        if self._reference_lines is not None:
            self._add_reference_lines_to_figure(fig)

        # Update axes
        fig.update_xaxes(
            showticklabels=False, 
            showgrid=False, 
            zeroline=False)
        
        fig.update_yaxes(
            range=[y_range[0], y_range[1]],
            title_text="Depth (μm)",
            showgrid=False,
            fixedrange=False,
        )

        # Update layout
        fig.update_layout(
            height=600,
            autosize=False,
            showlegend=False,
            margin=dict(l=50, r=10, t=10, b=10),
            hovermode="closest",
            dragmode="pan",
            xaxis=dict(fixedrange=True),  # Lock X-axis
            yaxis=dict(fixedrange=False),  # Allow Y-axis pan/zoom
        )

        return fig

    def _create_line_figure(self) -> go.Figure:
        """Create the line plot figure."""
        fig = go.Figure()
        y_range = self.state.depth_y_range
        line_data = self._get_line_data(self.line_plot_type)

        # Use placeholder data if no real data
        if line_data is None:
            line_data = self._get_placeholder_line_data()



        # Add line trace
        if line_data:
            self._add_line_trace(fig, line_data)

        # Add reference lines
        if self._reference_lines is not None:
            self._add_reference_lines_to_figure(fig)

        # Update axes
        fig.update_xaxes(
            showticklabels=False, 
            showgrid=False, 
            zeroline=False)
        
        fig.update_yaxes(
            range=[y_range[0], y_range[1]],
            showticklabels=False,
            showgrid=False,
            fixedrange=False,
        )

        logger.debug(f"Creating background heatmap with y_range: {fig.layout.yaxis.range}")

        # Add invisible heatmap covering full plot area to capture all clicks
        # This is the key - heatmaps respond to clicks anywhere within their bounds
        y_invisible = np.linspace(fig.layout.yaxis.range[0], fig.layout.yaxis.range[1], 100)
        x_invisible = np.linspace(np.min(line_data['x']), np.max(line_data['x']), 100)
        z_invisible = np.zeros((len(x_invisible), len(y_invisible)))
        
        fig.add_trace(
            go.Heatmap(
                x=x_invisible,
                y=y_invisible,
                z=z_invisible,
                colorscale=[[0, "white"], [1, "white"]],
                showscale=False,
                opacity=1,
                hoverinfo='none',
            )
        )

        # Update layout
        fig.update_layout(
            height=600,
            width=120,
            autosize=False,
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=10),
            hovermode="closest",
            clickmode="event",  # Generate click events even on empty space
            dragmode="pan",
            xaxis=dict(fixedrange=True),  # Lock X-axis
            yaxis=dict(fixedrange=False),  # Allow Y-axis pan/zoom
        )

        return fig

    def _create_probe_figure(self) -> go.Figure:
        """Create the probe plot figure."""
        fig = go.Figure()
        y_range = self.state.depth_y_range
        probe_data = self._get_probe_data(self.probe_plot_type)

        logger.debug("Creating probe figure")

        # Use placeholder data if no real data
        if probe_data is None:
            probe_data = self._get_placeholder_probe_data()

        # Add probe trace
        if probe_data:
            self._add_probe_trace(fig, probe_data)

        # Add reference lines
        if self._reference_lines is not None:
            self._add_reference_lines_to_figure(fig)

        # Update axes
        fig.update_xaxes(
            showticklabels=False, 
            showgrid=False, 
            zeroline=False)
        fig.update_yaxes(
            range=[y_range[0], y_range[1]],
            showticklabels=False,
            showgrid=False,
            fixedrange=False,
        )

        # Update layout
        fig.update_layout(
            height=600,
            width=120,
            autosize=False,
            showlegend=False,
            margin=dict(l=0, r=10, t=10, b=10),
            hovermode="closest",
            dragmode="pan",
            xaxis=dict(fixedrange=True),  # Lock X-axis
            yaxis=dict(fixedrange=False),  # Allow Y-axis pan/zoom
        )

        return fig

    def _add_image_trace(self, fig: go.Figure, data: dict) -> None:
        """Add heatmap trace to figure."""
        img = data["img"]
        scale = data["scale"]
        offset = data["offset"]
        levels = data["levels"]
        cmap = data.get("cmap", "Viridis")

        # Create coordinate arrays for the heatmap
        x_coords = offset[0] + np.arange(img.shape[0]) * scale[0]
        y_coords = offset[1] + np.arange(img.shape[1]) * scale[1]

        fig.add_trace(
            go.Heatmap(
                z=img.T,
                x=x_coords,
                y=y_coords,
                colorscale=cmap,
                zmin=levels[0],
                zmax=levels[1],
                hoverinfo='none',
                showscale=True,
                colorbar=dict(thickness=10, len=0.7),
            )
        )

    def _add_scatter_trace(self, fig: go.Figure, data: dict) -> None:
        """Add scatter plot trace to figure."""
        x = data["x"]
        y = data["y"]
        colors = data.get("colours")
        levels = data.get("levels", (0, 1))
        cmap = data.get("cmap", "Viridis")

        # Handle color data
        if colors is not None and len(colors) > 0:
            if isinstance(colors[0], (tuple, list)):
                color_values = np.array([c[0] if c else 0 for c in colors])
            else:
                color_values = np.asarray(colors)
        else:
            color_values = np.ones(len(x))

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                marker=dict(
                    size=3,
                    color=color_values,
                    colorscale=cmap,
                    cmin=levels[0],
                    cmax=levels[1],
                    showscale=True,
                    colorbar=dict(thickness=10, len=0.7),
                ),
            )
        )

    def _add_line_trace(self, fig: go.Figure, data: dict) -> None:
        """Add line plot trace to figure."""
        x_vals = data["x"]
        y_vals = data["y"]

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines",
                hoverinfo='skip',
                line=dict(color="#1f77b4", width=2),
            )
        )

    def _add_probe_trace(self, fig: go.Figure, data: dict) -> None:
        """Add probe geometry plot traces to figure."""
        img_list = data.get("img", [])
        scale = data.get("scale")
        offset = data.get("offset")
        levels = data.get("levels", (0, 1))
        cmap = data.get("cmap", "Viridis")

        logger.debug(f"Adding probe trace with {len(img_list)} banks")

        if not img_list or scale is None or offset is None:
            return

        # Add each bank as a separate heatmap
        for i, bank_img in enumerate(img_list):

            logger.debug(f"Adding bank {i} to probe plot")
            if bank_img is None:
                continue
            bank_scale = scale[i] if len(scale.shape) > 1 else scale
            bank_offset = offset[i] if len(offset.shape) > 1 else offset

            x_coords = bank_offset[0] + np.arange(bank_img.shape[0]) * bank_scale[0]
            y_coords = bank_offset[1] + np.arange(bank_img.shape[1]) * bank_scale[1]

            #logger.debug(f"Bank {i} x_coords: {x_coords}")
            #logger.debug(f"Bank {i} y_coords: {y_coords}")  
            #logger.debug(f"Bank {i} img shape: {bank_img.shape}")

            fig.add_trace(
                go.Heatmap(
                    z=bank_img.T,
                    x=x_coords,
                    y=y_coords,
                    colorscale=cmap,
                    zmin=levels[0],
                    zmax=levels[1],
                    showscale=False,
                    hoverinfo='none',
                )
            )

    def _add_reference_lines_to_figure(self, fig: go.Figure) -> None:
        """Add draggable reference lines as shapes to the figure.
        
        Plotly allows shapes to be made draggable with editable=True.
        """
        if not self._reference_lines or not self._reference_lines.lines:
            return

        for i, (y_feature, _) in enumerate(self._reference_lines.lines):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            is_selected = i == self._reference_lines.selected_index

            # Add horizontal line shape (spans all three subplots)
            fig.add_shape(
                type="line",
                x0=0,
                x1=1,
                xref="paper",  # Span full width
                y0=y_feature,
                y1=y_feature,
                yref="y",
                line=dict(
                    color=color,
                    width=3 if is_selected else 2,
                    dash="solid" if is_selected else "dash",
                ),
                editable=True,  # Make draggable!
                name=f"line_{i}",
            )

    def _on_click(self, click_data: dict) -> None:
        """Handle Plotly click events for double-click line creation.
        
        Parameters
        ----------
        click_data : dict
            Click event data from Plotly containing point coordinates.
        """
        logger.info(f"EphysPlots._on_click called with data: {click_data}")
        
        if not click_data or not self._reference_lines:
            logger.info(f"Ignoring click: click_data={bool(click_data)}, reference_lines={bool(self._reference_lines)}")
            return
        
        logger.debug(f"Click event data: {click_data}")
        
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
            logger.info(f"Double-click: added reference line at y={y_pos:.1f}")
            
            # Reset click tracking
            self._last_click_time = 0
            self._last_click_y = None
        else:
            logger.info(f"Single-click at {y_clicked:.1f}")
            # First click - store it
            self._last_click_time = current_time
            self._last_click_y = y_clicked
    
    def _on_relayout(self, relayout_data: dict) -> None:
        """Handle Plotly relayout events (shape drags, zoom, etc.).
        
        Parameters
        ----------
        relayout_data : dict
            Relayout event data from Plotly.
        """
        if not relayout_data:
            return
        
        logger.debug(f"Relayout event: {relayout_data}")

        # Parse shape drag events
        for key, value in relayout_data.items():
            if key.startswith("shapes[") and ".y0" in key:
                # Extract shape index from key like 'shapes[2].y0'
                try:
                    shape_idx = int(key.split("[")[1].split("]")[0])
                    if self._reference_lines is not None and 0 <= shape_idx < len(self._reference_lines.lines):
                        # Get current track position
                        _, y_track = self._reference_lines.lines[shape_idx]
                        # Update feature position (y_track stays the same)
                        self._reference_lines.update_line_position(shape_idx, value, y_track)
                        logger.debug(f"Updated line {shape_idx} feature position to {value:.1f}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse shape drag event: {e}")

            # Parse Y-axis zoom/pan events for synchronization
            elif key == "yaxis.range[0]":
                y_min = relayout_data.get("yaxis.range[0]")
                y_max = relayout_data.get("yaxis.range[1]")
                if y_min is not None and y_max is not None:
                    self.state.depth_y_range = (y_min, y_max)
                    logger.debug(f"Updated Y-range to ({y_min:.1f}, {y_max:.1f})")

    @param.depends("refresh", "image_plot_type")
    def image_view(self) -> pn.pane.Plotly:
        """Return the image plot pane.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing image plot.
        """
        fig = self._create_image_figure()
        
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
        
        pane.param.watch(
            lambda event: self._on_relayout(event.new), "relayout_data"
        )
        pane.param.watch(
            lambda event: self._on_click(event.new), "click_data"
        )
        
        return pane

    @param.depends("refresh", "line_plot_type")
    def line_view(self) -> pn.pane.Plotly:
        """Return the line plot pane.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing line plot.
        """
        fig = self._create_line_figure()
        
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
        
        pane.param.watch(
            lambda event: self._on_relayout(event.new), "relayout_data"
        )
        pane.param.watch(
            lambda event: self._on_click(event.new), "click_data"
        )
        
        return pane

    @param.depends("refresh", "probe_plot_type")
    def probe_view(self) -> pn.pane.Plotly:
        """Return the probe plot pane.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing probe plot.
        """
        fig = self._create_probe_figure()
        
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
        
        pane.param.watch(
            lambda event: self._on_relayout(event.new), "relayout_data"
        )
        pane.param.watch(
            lambda event: self._on_click(event.new), "click_data"
        )
        
        return pane

    def controls(self, selector: str) -> pn.widgets.Select:
        """Return plot control widgets.

        Parameters
        ----------
        selector : str
            One of 'image', 'line', or 'probe'.

        Returns
        -------
        pn.widgets.Select
            Select widget for plot type.
        """
        if selector == "image":
            widget = pn.widgets.Select(
                name="2D Plot",
                options=IMAGE_PLOT_OPTIONS,
                value=self.image_plot_type,
                width=120,
            )
            widget.link(self, value="image_plot_type")
            return widget
        elif selector == "line":
            widget = pn.widgets.Select(
                name="Line Plot",
                options=LINE_PLOT_OPTIONS,
                value=self.line_plot_type,
                width=120,
            )
            widget.link(self, value="line_plot_type")
            return widget
        elif selector == "probe":
            widget = pn.widgets.Select(
                name="Probe Plot",
                options=PROBE_PLOT_OPTIONS,
                value=self.probe_plot_type,
                width=100,
            )
            widget.link(self, value="probe_plot_type")
            return widget
        else:
            raise ValueError(f"Unknown selector type: {selector}")
