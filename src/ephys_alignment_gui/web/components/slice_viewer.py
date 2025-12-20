"""Slice viewer component for the web frontend.

Displays coronal brain slice images (CCF template, annotations, histology)
with probe trajectory overlay and channel markers.
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


class SliceViewer(param.Parameterized):
    """Component for displaying coronal brain slice images.

    Renders CCF template, annotation labels, or histology images as
    coronal slices through the brain at the probe location.

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
        state.param.watch(self._on_plot_type_changed, "slice_plot_type")
        state.param.watch(self._on_channels_toggled, "show_channels")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new:
            self.param.trigger("refresh")

    def _on_plot_type_changed(self, event) -> None:
        """Handle slice plot type change."""
        self.param.trigger("refresh")

    def _on_channels_toggled(self, event) -> None:
        """Handle channel visibility toggle."""
        self.param.trigger("refresh")

    def _get_slice_image(self) -> np.ndarray | None:
        """Get slice image data for the selected plot type.

        Returns
        -------
        np.ndarray or None
            Slice image array or None if not available.
        """
        slice_data = self.state.slice_data
        if slice_data is None:
            return None

        plot_type = self.state.slice_plot_type

        try:
            if plot_type in slice_data:
                return slice_data[plot_type]
            else:
                logger.warning(f"Slice type '{plot_type}' not in slice data")
                return slice_data.get("ccf")
        except Exception as e:
            logger.exception(f"Error getting slice data: {e}")
            return None

    def _create_slice_image(self, img: np.ndarray, slice_data: dict) -> hv.RGB | hv.Image:
        """Create a HoloViews image from slice data.

        Parameters
        ----------
        img : np.ndarray
            Slice image array (2D grayscale or 3D RGB).
        slice_data : dict
            Slice data with scale and offset information.

        Returns
        -------
        hv.RGB or hv.Image
            HoloViews image element.
        """
        scale = slice_data.get("scale", [1, 1])
        offset = slice_data.get("offset", [0, 0])

        # Calculate bounds
        if img.ndim == 3:
            # RGB image
            h, w = img.shape[:2]
        else:
            h, w = img.shape

        bounds = (
            offset[0],
            offset[1],
            offset[0] + w * scale[0],
            offset[1] + h * scale[1],
        )

        if img.ndim == 3 and img.shape[2] >= 3:
            # RGB image
            return hv.RGB(img, bounds=bounds)
        else:
            # Grayscale image
            return hv.Image(img, bounds=bounds)

    def _create_channel_overlay(self) -> hv.Points | None:
        """Create channel marker overlay.

        Returns
        -------
        hv.Points or None
            Points element for channel markers or None.
        """
        if not self.state.show_channels:
            return None

        # Channel locations would come from the alignment data
        # For now, return empty overlay
        # In full implementation, this would use ephys_alignment.channel_locations
        return None

    def controls(self) -> pn.widgets.Select:
        """Return plot type selector widget.

        Returns
        -------
        pn.widgets.Select
            Select widget for choosing slice plot type.
        """
        # Get available slice types from data
        options = {"CCF Template": "ccf", "Annotations": "label"}

        slice_data = self.state.slice_data
        if slice_data is not None:
            # Add any additional histology channels
            for key in slice_data.keys():
                if key not in ["ccf", "label", "scale", "offset"]:
                    options[key] = key

        return pn.widgets.Select(
            name="Slice Plot",
            options=options,
            value=self.state.slice_plot_type,
        )

    @param.depends("refresh")
    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the slice visualization.
        """
        slice_data = self.state.slice_data
        img = self._get_slice_image()

        if img is None or slice_data is None:
            return pn.Column(
                pn.pane.Markdown("### Brain Slice"),
                pn.pane.Markdown("*No slice data loaded*"),
                sizing_mode="stretch_both",
            )

        try:
            slice_img = self._create_slice_image(img, slice_data)

            # Configure plot options
            plot_opts = opts.RGB if img.ndim == 3 else opts.Image
            plot = slice_img.opts(
                plot_opts(
                    width=300,
                    height=300,
                    xlabel="ML (μm)",
                    ylabel="DV (μm)",
                    toolbar="above",
                    tools=["pan", "wheel_zoom", "reset"],
                    active_tools=["wheel_zoom"],
                )
            )

            # Add channel overlay if available
            channels = self._create_channel_overlay()
            if channels is not None:
                plot = plot * channels

            return pn.Column(
                pn.pane.Markdown("### Brain Slice"),
                pn.pane.HoloViews(plot, sizing_mode="stretch_both"),
                sizing_mode="stretch_both",
            )
        except Exception as e:
            logger.exception(f"Error creating slice view: {e}")
            return pn.Column(
                pn.pane.Markdown("### Brain Slice"),
                pn.pane.Markdown(f"*Error: {e}*"),
                sizing_mode="stretch_both",
            )
