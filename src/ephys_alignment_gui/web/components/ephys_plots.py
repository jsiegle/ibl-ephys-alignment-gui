"""Electrophysiology plot components for the web frontend.

Converts PlotData output to HoloViews elements for display in Panel.
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


class EphysPlots(param.Parameterized):
    """Component for displaying electrophysiology data plots.

    Renders image plots (firing rate, RMS, etc.) and scatter plots
    using HoloViews/Bokeh. Automatically updates when plot type
    or data changes.

    Parameters
    ----------
    state : AppState
        Shared application state.
    """

    # Trigger manual refresh
    refresh = param.Event(doc="Trigger plot refresh")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state
        self._plot_data: PlotData | None = None

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        state.param.watch(self._on_plot_type_changed, "img_plot_type")
        state.param.watch(self._on_unit_filter_changed, "unit_filter")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new and self.state.data is not None:
            self._initialize_plot_data()
            self.param.trigger("refresh")

    def _on_plot_type_changed(self, event) -> None:
        """Handle plot type change."""
        self.param.trigger("refresh")

    def _on_unit_filter_changed(self, event) -> None:
        """Handle unit filter change."""
        if self._plot_data is not None:
            self._plot_data.filter_units(event.new)
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

    def _get_plot_data_for_type(self, plot_type: str) -> dict | None:
        """Get plot data dict for the specified plot type.

        Parameters
        ----------
        plot_type : str
            Plot type identifier.

        Returns
        -------
        dict or None
            Plot data dictionary or None if not available.
        """
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
                logger.warning(f"Unknown plot type: {plot_type}")
                return None
        except Exception as e:
            logger.exception(f"Error getting plot data for {plot_type}: {e}")
            return None

    def _get_line_data_for_type(self, plot_type: str) -> dict | None:
        """Get line plot data for the specified type.

        Parameters
        ----------
        plot_type : str
            Line plot type identifier.

        Returns
        -------
        dict or None
            Line plot data dictionary or None.
        """
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
            logger.exception(f"Error getting line plot data: {e}")
            return None

    def _create_image_plot(self, data: dict) -> hv.Image:
        """Create a HoloViews Image from plot data dict.

        Parameters
        ----------
        data : dict
            Plot data with keys: img, scale, offset, levels, xrange, xaxis, cmap, title

        Returns
        -------
        hv.Image
            HoloViews Image element.
        """
        img = data["img"]
        scale = data["scale"]
        offset = data["offset"]
        levels = data["levels"]
        xrange = data["xrange"]

        # Calculate bounds: (left, bottom, right, top)
        bounds = (
            offset[0],  # left (x min)
            offset[1],  # bottom (y min)
            offset[0] + img.shape[0] * scale[0],  # right (x max)
            offset[1] + img.shape[1] * scale[1],  # top (y max)
        )

        image = hv.Image(
            img.T,  # Transpose for correct orientation
            bounds=bounds,
            kdims=["x", "y"],
        )

        return image.opts(
            opts.Image(
                cmap=data.get("cmap", "viridis"),
                clim=tuple(levels),
                xlabel=data.get("xaxis", ""),
                ylabel="Distance from probe tip (μm)",
                title=data.get("title", ""),
                colorbar=True,
                width=600,
                height=500,
                tools=["hover", "box_zoom", "reset"],
            )
        )

    def _create_line_plot(self, data: dict) -> hv.Curve:
        """Create a HoloViews Curve (line plot) from plot data dict.

        Parameters
        ----------
        data : dict
            Plot data with keys: x, y, xrange, xaxis

        Returns
        -------
        hv.Curve
            HoloViews Curve element.
        """
        x = data["x"]
        y = data["y"]

        # Create horizontal line plot (y vs x, rotated 90 degrees)
        # For probe-style plots, x is the value and y is the depth
        curve = hv.Curve(
            (x, y),
            kdims=["value"],
            vdims=["depth"],
        )

        return curve.opts(
            opts.Curve(
                line_width=2,
                color="blue",
                xlabel=data.get("xaxis", ""),
                ylabel="Distance from probe tip (μm)",
                width=200,
                height=500,
                tools=["hover"],
            )
        )

    def _create_scatter_plot(self, data: dict) -> hv.Points:
        """Create a HoloViews scatter plot from plot data dict.

        Parameters
        ----------
        data : dict
            Plot data with keys: x, y, colours, size, levels, xrange, xaxis, title, cmap

        Returns
        -------
        hv.Points
            HoloViews Points element.
        """
        x = data["x"]
        y = data["y"]
        colors = data.get("colours")
        sizes = data.get("size", np.ones(len(x)) * 5)

        # Handle color data
        if colors is not None and len(colors) > 0:
            # If colors are RGB tuples, convert to values for colormap
            if isinstance(colors[0], (tuple, list)):
                # Use first color channel as proxy for value
                color_values = np.array([c[0] if c else 0 for c in colors])
            else:
                color_values = np.asarray(colors)
        else:
            color_values = np.ones(len(x))

        # Create Points with color dimension
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
                ylabel="Distance from probe tip (μm)",
                title=data.get("title", ""),
                colorbar=True,
                width=600,
                height=500,
                tools=["hover", "box_zoom", "reset", "lasso_select"],
            )
        )

    @param.depends("refresh")
    def view(self) -> pn.pane.HoloViews | pn.pane.Markdown:
        """Return the current plot view.

        Returns
        -------
        pn.pane.HoloViews or pn.pane.Markdown
            Plot pane or placeholder message.
        """
        if not self.state.data_loaded or self._plot_data is None:
            return pn.pane.Markdown(
                "## No Data Loaded\n\nPlease load ephys data to view plots.",
                sizing_mode="stretch_both",
            )

        plot_type = self.state.img_plot_type
        data = self._get_plot_data_for_type(plot_type)

        if data is None:
            return pn.pane.Markdown(
                f"## No Data Available\n\nNo data available for plot type: {plot_type}",
                sizing_mode="stretch_both",
            )

        # Determine if this is an image or scatter plot
        if "img" in data:
            plot = self._create_image_plot(data)
        elif "x" in data and "y" in data:
            plot = self._create_scatter_plot(data)
        else:
            return pn.pane.Markdown(
                f"## Unknown Data Format\n\nCannot render plot type: {plot_type}",
                sizing_mode="stretch_both",
            )

        return pn.pane.HoloViews(plot, sizing_mode="stretch_both")

    def controls(self) -> pn.Column:
        """Return plot control widgets.

        Returns
        -------
        pn.Column
            Column of control widgets.
        """
        plot_type_selector = pn.widgets.Select(
            name="Plot Type",
            options={
                "Firing Rate": "firing_rate",
                "Amplitude": "amplitude",
                "Cluster FR vs Depth": "cluster_fr",
                "Cluster P2T vs Depth": "cluster_p2t",
                "Cluster Amp vs Depth": "cluster_amp",
                "Spike Correlation": "spike_correlation",
                "RMS AP": "rms_ap",
                "RMS LF": "rms_lf",
                "LFP Spectrum": "lfp_spectrum",
            },
            value=self.state.img_plot_type,
        )

        unit_filter_selector = pn.widgets.Select(
            name="Unit Filter",
            options={
                "All": "all",
                "KS Good": "KS good",
                "KS MUA": "KS mua",
                "IBL Good": "IBL good",
                "AIND QC": "aind_qc",
            },
            value=self.state.unit_filter,
        )

        # Link widgets to state
        plot_type_selector.link(self.state, value="img_plot_type")
        unit_filter_selector.link(self.state, value="unit_filter")

        return pn.Column(
            pn.pane.Markdown("### Plot Options"),
            plot_type_selector,
            unit_filter_selector,
            sizing_mode="stretch_width",
        )
