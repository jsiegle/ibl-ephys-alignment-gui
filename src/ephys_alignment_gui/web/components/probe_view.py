"""Probe view component for the web frontend.

Displays electrophysiology data arranged according to probe geometry,
such as RMS and LFP spectrum data.
"""

import logging

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts

from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)

# Configure HoloViews
hv.extension("bokeh")


class ProbeView(param.Parameterized):
    """Component for displaying probe geometry data.

    Renders data arranged according to the physical layout of the probe,
    such as RMS values or LFP spectrum data.

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

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        state.param.watch(self._on_plot_type_changed, "probe_plot_type")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new:
            self.param.trigger("refresh")

    def _on_plot_type_changed(self, event) -> None:
        """Handle probe plot type change."""
        self.param.trigger("refresh")

    def _get_probe_data(self) -> dict | None:
        """Get probe data for the selected plot type.

        Returns
        -------
        dict or None
            Probe data dictionary or None if not available.
        """
        if self.state.plot_data is None:
            return None

        plot_type = self.state.probe_plot_type

        try:
            if plot_type == "rms_ap":
                _, data = self.state.plot_data.get_rms_data_img_probe("AP")
                return data
            elif plot_type == "rms_lf":
                _, data = self.state.plot_data.get_rms_data_img_probe("LF")
                return data
            else:
                logger.warning(f"Unknown probe plot type: {plot_type}")
                return None
        except Exception as e:
            logger.exception(f"Error getting probe data: {e}")
            return None

    def _create_probe_image(self, data: dict) -> hv.Image:
        """Create a HoloViews Image for probe data.

        Parameters
        ----------
        data : dict
            Probe data with keys: img, scale, offset, levels, cmap, title

        Returns
        -------
        hv.Image
            HoloViews Image element.
        """
        img = data["img"]
        scale = data["scale"]
        offset = data["offset"]
        levels = data["levels"]

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
                xlabel="",
                ylabel="",
                title=data.get("title", ""),
                colorbar=True,
                width=80,
                height=500,
                toolbar=None,
            )
        )

    def _create_probe_bounds(self) -> hv.Overlay:
        """Create horizontal lines for probe boundaries.

        Returns
        -------
        hv.Overlay
            Overlay with boundary lines.
        """
        tip_line = hv.HLine(self.state.probe_tip).opts(
            line_dash="dotted",
            line_width=1,
            line_color="black",
        )
        top_line = hv.HLine(self.state.probe_top).opts(
            line_dash="dotted",
            line_width=1,
            line_color="black",
        )
        return hv.Overlay([tip_line, top_line])

    def controls(self) -> pn.widgets.Select:
        """Return plot type selector widget.

        Returns
        -------
        pn.widgets.Select
            Select widget for choosing probe plot type.
        """
        return pn.widgets.Select(
            name="Probe Plot",
            options={
                "RMS AP": "rms_ap",
                "RMS LF": "rms_lf",
            },
            value=self.state.probe_plot_type,
        )

    @param.depends("refresh")
    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the probe visualization.
        """
        data = self._get_probe_data()

        if data is None:
            return pn.Column(
                pn.pane.Markdown("### Probe"),
                pn.pane.Markdown("*No probe data*"),
                sizing_mode="stretch_height",
                width=100,
            )

        try:
            probe_img = self._create_probe_image(data)
            bounds = self._create_probe_bounds()
            plot = (probe_img * bounds)

            return pn.Column(
                pn.pane.HoloViews(plot, sizing_mode="stretch_height", width=100),
                sizing_mode="stretch_height",
                width=100,
            )
        except Exception as e:
            logger.exception(f"Error creating probe view: {e}")
            return pn.Column(
                pn.pane.Markdown("### Probe"),
                pn.pane.Markdown(f"*Error: {e}*"),
                sizing_mode="stretch_height",
                width=100,
            )
