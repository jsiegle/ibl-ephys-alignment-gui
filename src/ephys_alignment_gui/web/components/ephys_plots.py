"""Electrophysiology plot components for the web frontend.

Converts PlotData output to HoloViews elements for display in Panel.
Displays three sub-plots side by side: 2D image, line plot, and probe plot.
"""

import logging

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts

from ephys_alignment_gui.visualization.plot_data import PlotData
from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)

# Configure HoloViews
hv.extension("bokeh")

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


class EphysPlots(param.Parameterized):
    """Component for displaying electrophysiology data plots.

    Renders three sub-plots side by side:
    - 2D image plot (firing rate, RMS, correlation, etc.)
    - Line plot (firing rate or amplitude vs depth)
    - Probe plot (RMS or LFP band power on probe geometry)

    Each sub-plot has its own Plot Type selector.

    Parameters
    ----------
    state : AppState
        Shared application state.
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

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state
        self._plot_data: PlotData | None = None

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")

        # Watch local plot type changes
        self.param.watch(self._on_plot_type_changed, "image_plot_type")
        self.param.watch(self._on_plot_type_changed, "line_plot_type")
        self.param.watch(self._on_plot_type_changed, "probe_plot_type")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new and self.state.data is not None:
            self._initialize_plot_data()
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
                # Parse frequency band from plot_type like "lfp_0_4"
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

    def _create_image_plot(self, data: dict, width: int = 350, height: int = 450) -> hv.Image:
        """Create a HoloViews Image from plot data dict."""
        img = data["img"]
        scale = data["scale"]
        offset = data["offset"]
        levels = data["levels"]
        y_range = self._get_y_range()

        # Calculate bounds: (left, bottom, right, top)
        bounds = (
            offset[0],
            offset[1],
            offset[0] + img.shape[0] * scale[0],
            offset[1] + img.shape[1] * scale[1],
        )

        image = hv.Image(
            img.T,
            bounds=bounds,
            kdims=["x", "y"],
        )

        return image.opts(
            opts.Image(
                cmap=data.get("cmap", "viridis"),
                clim=tuple(levels),
                xlabel=data.get("xaxis", ""),
                ylabel="Depth (μm)",
                title="",
                colorbar=True,
                width=width,
                height=height,
                ylim=y_range,
                tools=["hover", "box_zoom", "reset"],
                margin=0,
            )
        )

    def _create_line_plot(self, data: dict, width: int = 150, height: int = 450) -> hv.Path:
        """Create a HoloViews Path (line plot) from plot data dict."""
        x_vals = data["x"]
        y_vals = data["y"]
        y_range = self._get_y_range()

        # Use Path with x, y kdims to match Image plots for axis linking
        path = hv.Path(
            [np.column_stack([x_vals, y_vals])],
            kdims=["x", "y"],
        )

        return path.opts(
            opts.Path(
                line_width=2,
                color="#1f77b4",
                xlabel=data.get("xaxis", ""),
                ylabel="",
                width=width,
                height=height,
                ylim=y_range,
                yaxis=None,
                tools=["hover"],
                margin=0,
            )
        )

    def _create_scatter_plot(self, data: dict, width: int = 350, height: int = 450) -> hv.Points:
        """Create a HoloViews scatter plot from plot data dict."""
        x = data["x"]
        y = data["y"]
        colors = data.get("colours")
        y_range = self._get_y_range()

        # Handle color data
        if colors is not None and len(colors) > 0:
            if isinstance(colors[0], (tuple, list)):
                color_values = np.array([c[0] if c else 0 for c in colors])
            else:
                color_values = np.asarray(colors)
        else:
            color_values = np.ones(len(x))

        points = hv.Points(
            (x, y, color_values),
            kdims=["x", "y"],
            vdims=["color"],
        )

        return points.opts(
            opts.Points(
                color="color",
                cmap=data.get("cmap", "viridis"),
                clim=tuple(data.get("levels", (0, 1))),
                size=3,
                alpha=0.6,
                xlabel=data.get("xaxis", ""),
                ylabel="Depth (μm)",
                title="",
                colorbar=True,
                width=width,
                height=height,
                ylim=y_range,
                tools=["hover", "box_zoom", "reset"],
                margin=0,
            )
        )

    def _create_probe_plot(self, data: dict, width: int = 80, height: int = 450) -> hv.Overlay:
        """Create probe geometry plot from bank data.

        The probe data contains multiple banks (columns) that need to be
        rendered side by side.
        """
        y_range = self._get_y_range()

        if data is None:
            return hv.Text(0, 0, "No data").opts(width=width, height=height)

        img_list = data.get("img", [])
        scale = data.get("scale")
        offset = data.get("offset")
        levels = data.get("levels", (0, 1))
        cmap = data.get("cmap", "viridis")

        if not img_list or scale is None or offset is None:
            return hv.Text(0, 0, "No probe data").opts(width=width, height=height)

        # Create overlay of bank images
        images = []
        for i, bank_img in enumerate(img_list):
            if bank_img is None:
                continue
            bank_scale = scale[i] if len(scale.shape) > 1 else scale
            bank_offset = offset[i] if len(offset.shape) > 1 else offset

            bounds = (
                bank_offset[0],
                bank_offset[1],
                bank_offset[0] + bank_img.shape[0] * bank_scale[0],
                bank_offset[1] + bank_img.shape[1] * bank_scale[1],
            )

            img = hv.Image(
                bank_img.T,
                bounds=bounds,
                kdims=["x", "y"],
            )
            images.append(img)

        if not images:
            return hv.Text(0, 0, "No probe data").opts(width=width, height=height)

        overlay = hv.Overlay(images)
        return overlay.opts(
            opts.Image(
                cmap=cmap,
                clim=tuple(levels),
                colorbar=False,
                margin=0,
            ),
            opts.Overlay(
                width=width,
                height=height,
                xlabel="",
                ylabel="",
                ylim=y_range,
                yaxis=None,
                title="",
                tools=["hover"],
                margin=0,
            ),
        )

    def _get_y_range(self) -> tuple:
        """Get the shared Y-axis range for depth plots."""
        return self.state.depth_y_range

    def _create_placeholder_image(self, width: int = 350, height: int = 450) -> hv.Image:
        """Create a placeholder 2D image plot."""
        y_range = self._get_y_range()
        # Create gradient placeholder data
        y = np.linspace(y_range[0], y_range[1], 100)
        x = np.linspace(0, 100, 50)
        xx, yy = np.meshgrid(x, y)
        img = np.sin(yy / 500) * 0.5 + 0.5  # Gentle gradient

        image = hv.Image(
            img,
            bounds=(0, y_range[0], 100, y_range[1]),
            kdims=["x", "y"],
        )
        return image.opts(
            opts.Image(
                cmap="gray",
                clim=(0, 1),
                xlabel="Time (s)",
                ylabel="Depth (μm)",
                title="",
                colorbar=True,
                width=width,
                height=height,
                ylim=y_range,
                alpha=0.3,
                margin=0,
            )
        )

    def _create_placeholder_line(self, width: int = 150, height: int = 450) -> hv.Path:
        """Create a placeholder line plot."""
        y_range = self._get_y_range()
        y_vals = np.linspace(y_range[0], y_range[1], 100)
        x_vals = np.zeros_like(y_vals)  # Flat line

        # Use Path with x, y kdims to match Image plots for axis linking
        path = hv.Path(
            [np.column_stack([x_vals, y_vals])],
            kdims=["x", "y"],
        )
        return path.opts(
            opts.Path(
                line_width=2,
                color="#cccccc",
                xlabel="Firing Rate (Sp/s)",
                ylabel="",
                width=width,
                height=height,
                ylim=y_range,
                yaxis=None,
                margin=0,
            )
        )

    def _create_placeholder_probe(self, width: int = 80, height: int = 450) -> hv.Image:
        """Create a placeholder probe plot."""
        y_range = self._get_y_range()
        # Create a simple vertical gradient
        n_points = int(y_range[1] - y_range[0]) // 10
        img = np.linspace(0, 1, max(n_points, 10)).reshape(-1, 1)

        image = hv.Image(
            img,
            bounds=(0, y_range[0], 10, y_range[1]),
            kdims=["x", "y"],
        )
        return image.opts(
            opts.Image(
                cmap="gray",
                clim=(0, 1),
                xlabel="",
                ylabel="",
                title="",
                colorbar=False,
                width=width,
                height=height,
                ylim=y_range,
                yaxis=None,
                alpha=0.3,
                margin=0,
            )
        )

    def _get_image_plot(self) -> hv.Element:
        """Get the 2D image/scatter plot element."""
        data = self._get_image_data(self.image_plot_type)
        if data is None:
            return self._create_placeholder_image()
        elif "img" in data:
            return self._create_image_plot(data)
        elif "x" in data and "y" in data:
            return self._create_scatter_plot(data)
        else:
            return self._create_placeholder_image()

    def _get_line_plot(self) -> hv.Element:
        """Get the line plot element."""
        data = self._get_line_data(self.line_plot_type)
        if data is None:
            return self._create_placeholder_line()
        else:
            return self._create_line_plot(data)

    def _get_probe_plot(self) -> hv.Element:
        """Get the probe plot element."""
        data = self._get_probe_data(self.probe_plot_type)
        if data is None:
            return self._create_placeholder_probe()
        else:
            return self._create_probe_plot(data)

    def get_linked_plots(self) -> hv.Layout:
        """Return all three plots as a linked HoloViews Layout.

        This allows axis linking with external plots (e.g., histology).

        Returns
        -------
        hv.Layout
            Layout containing image, line, and probe plots with shared Y-axis.
        """
        image_plot = self._get_image_plot()
        line_plot = self._get_line_plot()
        probe_plot = self._get_probe_plot()

        # Combine into a Layout with shared Y-axis
        layout = (image_plot + line_plot + probe_plot).opts(
            opts.Layout(shared_axes=True, merge_tools=True)
        )
        return layout

    @param.depends("refresh", "image_plot_type", "line_plot_type", "probe_plot_type")
    def view(self) -> pn.pane.HoloViews:
        """Return the three-column plot view with linked Y-axes.

        Returns
        -------
        pn.pane.HoloViews
            HoloViews pane containing linked plots.
        """
        layout = self.get_linked_plots()
        return pn.pane.HoloViews(layout, sizing_mode="stretch_both")

    def controls(self) -> pn.Row:
        """Return plot control widgets as a row of selectors.

        Each selector is placed in a fixed-width container matching its
        corresponding plot width (Image: 350px, Line: 150px, Probe: 80px).

        Returns
        -------
        pn.Row
            Row of plot type selectors aligned with their plots.
        """
        # Create selectors with widths matching plot widths
        image_selector = pn.widgets.Select(
            name="2D Plot",
            options=IMAGE_PLOT_OPTIONS,
            value=self.image_plot_type,
            width=120,
        )

        line_selector = pn.widgets.Select(
            name="Line Plot",
            options=LINE_PLOT_OPTIONS,
            value=self.line_plot_type,
            width=120,
        )

        probe_selector = pn.widgets.Select(
            name="Probe Plot",
            options=PROBE_PLOT_OPTIONS,
            value=self.probe_plot_type,
            width=120,
        )

        # Link widgets to params
        image_selector.link(self, value="image_plot_type")
        line_selector.link(self, value="line_plot_type")
        probe_selector.link(self, value="probe_plot_type")

        # Wrap each in a Column with fixed width matching the plot
        # Plot widths: Image=350, Line=150, Probe=80 (+ colorbar ~30)
        image_col = pn.Column(image_selector, width=380, align="center")
        line_col = pn.Column(line_selector, width=150, align="center")
        probe_col = pn.Column(probe_selector, width=80, align="center")

        return pn.Row(
            image_col,
            line_col,
            probe_col,
        )
