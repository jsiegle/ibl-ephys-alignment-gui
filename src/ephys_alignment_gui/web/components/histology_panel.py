"""Histology panel component for the web frontend.

Displays brain region boundaries along the probe trajectory as colored
bars with region labels.
"""

import logging
from typing import TYPE_CHECKING

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts

from ephys_alignment_gui.web.state import AppState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Configure HoloViews
hv.extension("bokeh")


class HistologyPanel(param.Parameterized):
    """Component for displaying brain region histology.

    Renders colored bars representing brain regions along the probe
    trajectory, with optional region labels. Shows both the current
    (aligned) and reference (original) histology views.

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
        state.param.watch(self._on_labels_toggled, "show_labels")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event."""
        if event.new:
            self.param.trigger("refresh")

    def _on_labels_toggled(self, event) -> None:
        """Handle label visibility toggle."""
        self.param.trigger("refresh")

    def _create_region_bars(
        self,
        hist_data: dict,
        x_offset: float = 0,
        width: float = 1,
    ) -> hv.Overlay:
        """Create colored bars for brain regions.

        Parameters
        ----------
        hist_data : dict
            Dictionary with 'region', 'colour', and 'axis_label' keys.
        x_offset : float
            X position offset for the bars.
        width : float
            Width of the bars.

        Returns
        -------
        hv.Overlay
            Overlay of colored rectangle elements.
        """
        if not hist_data or "region" not in hist_data:
            return hv.Overlay([])

        elements = []
        regions = hist_data.get("region", [])
        colours = hist_data.get("colour", [])
        labels = hist_data.get("axis_label", [])

        for i, (region, colour) in enumerate(zip(regions, colours)):
            if len(region) < 2:
                continue

            y_min, y_max = region[0], region[1]

            # Convert RGB to hex color
            if isinstance(colour, (list, tuple)) and len(colour) >= 3:
                hex_color = "#{:02x}{:02x}{:02x}".format(
                    int(colour[0]), int(colour[1]), int(colour[2])
                )
            else:
                hex_color = "#808080"  # Default gray

            # Create rectangle for this region
            rect = hv.Rectangles(
                [(x_offset, y_min, x_offset + width, y_max)],
                kdims=["x0", "y0", "x1", "y1"],
            ).opts(
                color=hex_color,
                line_width=0,
                alpha=0.8,
            )
            elements.append(rect)

            # Add label if enabled and available
            if self.state.show_labels and i < len(labels) and labels[i]:
                y_center = (y_min + y_max) / 2
                label = hv.Text(
                    x_offset + width / 2,
                    y_center,
                    labels[i],
                    fontsize=8,
                ).opts(
                    text_align="center",
                    text_color="black",
                )
                elements.append(label)

        return hv.Overlay(elements)

    def _create_probe_bounds(self) -> hv.Overlay:
        """Create horizontal lines for probe tip and top boundaries.

        Returns
        -------
        hv.Overlay
            Overlay with probe boundary lines.
        """
        tip_line = hv.HLine(self.state.probe_tip).opts(
            line_dash="dotted",
            line_width=2,
            line_color="black",
        )
        top_line = hv.HLine(self.state.probe_top).opts(
            line_dash="dotted",
            line_width=2,
            line_color="black",
        )
        return hv.Overlay([tip_line, top_line])

    @param.depends("refresh")
    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the histology visualization.
        """
        hist_data = self.state.hist_data

        if hist_data is None or not hist_data.get("region"):
            return pn.Column(
                pn.pane.Markdown("### Histology"),
                pn.pane.Markdown("*No histology data loaded*"),
                sizing_mode="stretch_both",
            )

        # Create main histology view (aligned)
        main_bars = self._create_region_bars(hist_data, x_offset=0, width=1)
        probe_bounds = self._create_probe_bounds()

        # Combine elements
        plot = (main_bars * probe_bounds).opts(
            opts.Overlay(
                width=150,
                height=500,
                xlabel="",
                ylabel="Distance from probe tip (μm)",
                xlim=(-0.1, 1.1),
                ylim=(
                    self.state.probe_tip - 100,
                    self.state.probe_top + 100,
                ),
                toolbar="above",
                tools=["pan", "wheel_zoom", "reset"],
                active_tools=["wheel_zoom"],
            )
        )

        return pn.Column(
            pn.pane.Markdown("### Histology"),
            pn.pane.HoloViews(plot, sizing_mode="stretch_both"),
            sizing_mode="stretch_both",
        )

    def view_reference(self) -> pn.Column:
        """Return a reference histology view (original, unadjusted).

        Returns
        -------
        pn.Column
            Panel column containing the reference histology.
        """
        # For now, use the same data - in full implementation,
        # this would show the original unaligned histology
        hist_data = self.state.hist_data

        if hist_data is None or not hist_data.get("region"):
            return pn.Column(
                pn.pane.Markdown("### Reference"),
                pn.pane.Markdown("*No data*"),
                sizing_mode="stretch_both",
            )

        ref_bars = self._create_region_bars(hist_data, x_offset=0, width=1)
        probe_bounds = self._create_probe_bounds()

        plot = (ref_bars * probe_bounds).opts(
            opts.Overlay(
                width=150,
                height=500,
                xlabel="",
                ylabel="",
                xlim=(-0.1, 1.1),
                ylim=(
                    self.state.probe_tip - 100,
                    self.state.probe_top + 100,
                ),
                toolbar=None,
            )
        )

        return pn.Column(
            pn.pane.Markdown("### Reference"),
            pn.pane.HoloViews(plot, sizing_mode="stretch_both"),
            sizing_mode="stretch_both",
        )
