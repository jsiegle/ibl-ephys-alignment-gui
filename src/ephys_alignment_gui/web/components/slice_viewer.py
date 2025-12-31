"""Slice viewer component for the web frontend.

Displays coronal brain slice images (CCF template, annotations, histology)
using Plotly.
"""

import logging

import numpy as np
import panel as pn
import param
import plotly.graph_objects as go

from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)


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

    def _create_figure(self) -> go.Figure:
        """Create Plotly figure for brain slice viewer.
        
        Returns
        -------
        go.Figure
            Plotly figure with brain slice image.
        """
        slice_data = self.state.slice_data
        img = self._get_slice_image()
        
        if img is None or slice_data is None:
            img = self._create_placeholder_image()
            slice_data = {"scale": [1, 1], "offset": [0, 0]}
        
        fig = go.Figure()
        
        scale = slice_data.get("scale", [1, 1])
        offset = slice_data.get("offset", [0, 0])
        
        if img.ndim == 3 and img.shape[2] >= 3:
            # RGB image
            fig.add_trace(
                go.Image(
                    z=img,
                    x0=offset[0],
                    dx=scale[0],
                    y0=offset[1],
                    dy=scale[1],
                )
            )
        else:
            # Grayscale image
            fig.add_trace(
                go.Heatmap(
                    z=img,
                    x0=offset[0],
                    dx=scale[0],
                    y0=offset[1],
                    dy=scale[1],
                    colorscale="gray",
                    showscale=False,
                )
            )
        
        fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1)
        fig.update_yaxes(visible=False, autorange="reversed")  # Image coordinates
        
        fig.update_layout(
            width=250,
            height=250,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(fixedrange=False),
            yaxis=dict(fixedrange=False),
            dragmode="pan",
        )
        
        return fig

    def _create_placeholder_image(self) -> np.ndarray:
        """Create a placeholder brain slice image.
        
        Returns
        -------
        np.ndarray
            Grayscale placeholder image suggesting brain shape.
        """
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
        
        return img

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
    def view(self) -> pn.pane.Plotly:
        """Return the Plotly slice viewer figure.

        Returns
        -------
        pn.pane.Plotly
            Plotly pane containing the slice visualization.
        """
        try:
            fig = self._create_figure()
            
            return pn.pane.Plotly(
                fig,
                sizing_mode="stretch_both",
                config={
                    "scrollZoom": True,
                    "displayModeBar": False,
                    "displaylogo": False,
                },
            )
        except Exception as e:
            logger.exception(f"Error creating slice view: {e}")
            # Return placeholder figure on error
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error: {e}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
            fig.update_layout(width=250, height=250)
            return pn.pane.Plotly(fig, sizing_mode="stretch_both")
