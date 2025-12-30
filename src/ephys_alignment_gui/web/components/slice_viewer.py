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
            # RGB image - use unique dimension names to avoid axis linking
            return hv.RGB(img, bounds=bounds, kdims=["ml", "dv"])
        else:
            # Grayscale image - use unique dimension names to avoid axis linking
            return hv.Image(img, bounds=bounds, kdims=["ml", "dv"])

    def _create_channel_overlay(self) -> hv.Points | None:
        """Create channel marker overlay.

        Returns
        -------
        hv.Points or None
            Points element for channel markers or None.
        """

        # Channel locations would come from the alignment data
        # For now, return empty overlay
        # In full implementation, this would use ephys_alignment.channel_locations
        return None

    def _create_placeholder_slice(self):
        """Create a placeholder brain slice image."""
        # Create a simple ellipse pattern to suggest brain shape
        size = 100
        y, x = np.ogrid[-size:size, -size:size]
        # Ellipse mask (wider than tall, like coronal slice)
        mask = (x * x) / (size * 0.9) ** 2 + (y * y) / (size * 0.7) ** 2 <= 1
        img = np.zeros((2 * size, 2 * size))
        img[mask] = 0.3  # Light gray brain region

        # Add some internal structure suggestion
        inner_mask = (x * x) / (size * 0.3) ** 2 + (y * y) / (size * 0.4) ** 2 <= 1
        img[inner_mask] = 0.5

        return hv.Image(
            img,
            bounds=(-5000, -8000, 5000, 0),
            kdims=["ml", "dv"],  # Unique dimension names to avoid axis linking
        ).opts(
            opts.Image(
                cmap="gray",
                clim=(0, 1),
                width=250,
                height=250,
                xaxis=None,
                yaxis=None,
                toolbar=None,
                alpha=0.5,
            )
        )

    def controls(self) -> pn.widgets.Select:
        """Return slice type selector widget."""
        # Get available slice types from data
        options = {"CCF Template": "ccf", "Annotations": "label"}

        slice_data = self.state.slice_data
        if slice_data is not None:
            # Add any additional histology channels
            for key in slice_data.keys():
                if key not in ["ccf", "label", "scale", "offset"]:
                    options[key] = key

        selector = pn.widgets.Select(
            name="Brain Slice",
            options=options,
            value=self.state.slice_plot_type,
            width=120,
        )
        selector.link(self.state, value="slice_plot_type")
        return selector

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
            # Show placeholder
            plot = self._create_placeholder_slice()
            return pn.Column(
                pn.pane.HoloViews(plot, sizing_mode="stretch_both"),
                sizing_mode="stretch_both",
            )

        try:
            slice_img = self._create_slice_image(img, slice_data)

            # Configure plot options
            plot_opts = opts.RGB if img.ndim == 3 else opts.Image
            plot = slice_img.opts(
                plot_opts(
                    width=250,
                    height=250,
                    xaxis=None,
                    yaxis=None,
                    toolbar=None,
                )
            )

            # Add channel overlay if available
            channels = self._create_channel_overlay()
            if channels is not None:
                plot = plot * channels

            return pn.Column(
                pn.pane.HoloViews(plot, sizing_mode="stretch_both"),
                sizing_mode="stretch_both",
            )
        except Exception as e:
            logger.exception(f"Error creating slice view: {e}")
            return pn.Column(
                pn.pane.Markdown(f"*Error: {e}*"),
                sizing_mode="stretch_both",
            )
