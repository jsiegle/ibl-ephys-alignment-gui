"""Colorbar component for the web frontend.

Provides standalone colorbar widgets that can be linked to plots.
"""

import logging

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts

logger = logging.getLogger(__name__)

# Configure HoloViews
hv.extension("bokeh")


class ColorBar(param.Parameterized):
    """Standalone colorbar widget.

    Creates a colorbar that can be displayed alongside plots to show
    the color mapping for data values.

    Parameters
    ----------
    cmap : str
        Colormap name (e.g., 'viridis', 'plasma', 'magma').
    levels : tuple
        (min, max) values for the color scale.
    title : str
        Colorbar title/label.
    orientation : str
        'horizontal' or 'vertical'.
    """

    cmap = param.String(default="viridis", doc="Colormap name")
    levels = param.Tuple(default=(0, 1), doc="(min, max) values")
    title = param.String(default="", doc="Colorbar title")
    orientation = param.Selector(
        default="horizontal",
        objects=["horizontal", "vertical"],
        doc="Colorbar orientation",
    )

    # Trigger refresh
    refresh = param.Event(doc="Trigger colorbar refresh")

    def __init__(self, **params):
        super().__init__(**params)

    def update(
        self,
        cmap: str | None = None,
        levels: tuple | None = None,
        title: str | None = None,
    ) -> None:
        """Update colorbar parameters.

        Parameters
        ----------
        cmap : str, optional
            New colormap name.
        levels : tuple, optional
            New (min, max) values.
        title : str, optional
            New title.
        """
        if cmap is not None:
            self.cmap = cmap
        if levels is not None:
            self.levels = levels
        if title is not None:
            self.title = title
        self.param.trigger("refresh")

    def _create_colorbar_image(self) -> hv.Image:
        """Create a gradient image representing the colormap.

        Returns
        -------
        hv.Image
            HoloViews Image element showing the colormap gradient.
        """
        # Create gradient array
        if self.orientation == "horizontal":
            gradient = np.linspace(self.levels[0], self.levels[1], 256).reshape(1, -1)
            bounds = (self.levels[0], 0, self.levels[1], 1)
        else:
            gradient = np.linspace(self.levels[0], self.levels[1], 256).reshape(-1, 1)
            bounds = (0, self.levels[0], 1, self.levels[1])

        return hv.Image(gradient, bounds=bounds).opts(
            cmap=self.cmap,
            clim=self.levels,
            colorbar=False,
            toolbar=None,
            xaxis=None if self.orientation == "vertical" else "bottom",
            yaxis="left" if self.orientation == "vertical" else None,
        )

    @param.depends("refresh", "cmap", "levels", "title", "orientation")
    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the colorbar.
        """
        img = self._create_colorbar_image()

        if self.orientation == "horizontal":
            plot = img.opts(
                opts.Image(
                    width=200,
                    height=30,
                    xlabel=self.title,
                    ylabel="",
                )
            )
        else:
            plot = img.opts(
                opts.Image(
                    width=30,
                    height=200,
                    xlabel="",
                    ylabel=self.title,
                )
            )

        return pn.pane.HoloViews(plot)


class RangeSliderColorBar(param.Parameterized):
    """Colorbar with interactive range slider.

    Combines a colorbar with a range slider that allows users to
    adjust the displayed color range.

    Parameters
    ----------
    cmap : str
        Colormap name.
    data_range : tuple
        Full range of data values (min, max).
    title : str
        Colorbar title.
    """

    cmap = param.String(default="viridis", doc="Colormap name")
    data_range = param.Tuple(default=(0, 1), doc="Full data range")
    display_range = param.Tuple(default=(0, 1), doc="Current display range")
    title = param.String(default="", doc="Colorbar title")

    # Events
    range_changed = param.Event(doc="Display range changed")

    def __init__(self, **params):
        super().__init__(**params)
        self.display_range = self.data_range

        # Create range slider
        self._slider = pn.widgets.RangeSlider(
            name=self.title,
            start=self.data_range[0],
            end=self.data_range[1],
            value=self.display_range,
            step=(self.data_range[1] - self.data_range[0]) / 100,
        )
        self._slider.param.watch(self._on_slider_changed, "value")

    def _on_slider_changed(self, event) -> None:
        """Handle slider value change."""
        self.display_range = event.new
        self.param.trigger("range_changed")

    def update_data_range(self, data_range: tuple) -> None:
        """Update the data range and reset display range.

        Parameters
        ----------
        data_range : tuple
            New (min, max) data range.
        """
        self.data_range = data_range
        self._slider.start = data_range[0]
        self._slider.end = data_range[1]
        self._slider.step = (data_range[1] - data_range[0]) / 100
        self.display_range = data_range
        self._slider.value = data_range

    @param.depends("display_range", "cmap")
    def colorbar_view(self) -> pn.pane.HoloViews:
        """Return just the colorbar visualization.

        Returns
        -------
        pn.pane.HoloViews
            HoloViews pane with colorbar.
        """
        gradient = np.linspace(
            self.display_range[0], self.display_range[1], 256
        ).reshape(1, -1)
        bounds = (self.display_range[0], 0, self.display_range[1], 1)

        img = hv.Image(gradient, bounds=bounds).opts(
            cmap=self.cmap,
            clim=self.display_range,
            colorbar=False,
            toolbar=None,
            xaxis="bottom",
            yaxis=None,
            width=200,
            height=20,
            xlabel=self.title,
        )
        return pn.pane.HoloViews(img)

    def view(self) -> pn.Column:
        """Return the Panel layout with slider and colorbar.

        Returns
        -------
        pn.Column
            Panel column containing slider and colorbar.
        """
        return pn.Column(
            self._slider,
            self.colorbar_view,
            sizing_mode="stretch_width",
        )
