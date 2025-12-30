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

    # Plot type selection
    plot_type = param.Selector(
        default="aligned",
        objects=["aligned", "reference"],
        doc="Histology view type",
    )

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        self.param.watch(self._on_plot_type_changed, "plot_type")

    def _on_plot_type_changed(self, event) -> None:
        """Handle plot type change."""
        self.param.trigger("refresh")

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
            if i < len(labels) and labels[i]:
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

    def _get_y_range(self) -> tuple:
        """Get the shared Y-axis range for depth plots."""
        return self.state.depth_y_range

    def _create_placeholder_bars(self) -> hv.Overlay:
        """Create placeholder region bars with gray gradient."""
        y_range = self._get_y_range()
        elements = []
        # Create 10 placeholder regions
        total_height = y_range[1] - y_range[0]
        region_height = total_height / 10
        for i in range(10):
            y_min = y_range[0] + i * region_height
            y_max = y_range[0] + (i + 1) * region_height
            # Alternating gray shades
            gray = 180 + (i % 2) * 40
            hex_color = f"#{gray:02x}{gray:02x}{gray:02x}"

            rect = hv.Rectangles(
                [(0, y_min, 100, y_max)],
                kdims=["x0", "y0", "x1", "y1"],
            ).opts(
                color=hex_color,
                line_width=0,
                alpha=0.5,
            )
            elements.append(rect)

        return hv.Overlay(elements)

    def get_plot(self) -> hv.Image:
        """Return the histology plot as an Image for axis linking.

        Uses an Image element with x, y kdims to match other depth plots
        for proper axis linking.

        Returns
        -------
        hv.Image
            The histology plot as an image element.
        """
        hist_data = self.state.hist_data
        y_range = self._get_y_range()
        
        # Create image array from region data
        n_pixels = 500  # Vertical resolution
        img = np.zeros((n_pixels, 1, 3), dtype=np.uint8)  # RGB image, 1 pixel wide
        
        if hist_data is not None and hist_data.get("region"):
            regions = hist_data.get("region", [])
            colours = hist_data.get("colour", [])
            
            for region, colour in zip(regions, colours):
                if len(region) < 2:
                    continue
                y_min, y_max = region[0], region[1]
                
                # Convert y positions to pixel indices
                idx_min = int((y_min - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
                idx_max = int((y_max - y_range[0]) / (y_range[1] - y_range[0]) * n_pixels)
                idx_min = max(0, min(n_pixels - 1, idx_min))
                idx_max = max(0, min(n_pixels, idx_max))
                
                if isinstance(colour, (list, tuple)) and len(colour) >= 3:
                    img[idx_min:idx_max, 0, 0] = int(colour[0])
                    img[idx_min:idx_max, 0, 1] = int(colour[1])
                    img[idx_min:idx_max, 0, 2] = int(colour[2])
                else:
                    img[idx_min:idx_max, 0, :] = 128  # Gray default
        else:
            # Placeholder: alternating gray bars
            bar_height = n_pixels // 10
            for i in range(10):
                gray = 180 + (i % 2) * 40
                img[i * bar_height:(i + 1) * bar_height, 0, :] = gray
        
        # Create RGB image with unique x dim so only y-axis is linked
        plot = hv.RGB(
            img,
            bounds=(0, y_range[0], 1, y_range[1]),
            kdims=["x_hist", "y"],
        )
        
        return plot.opts(
            opts.RGB(
                width=100,
                frame_height=450,
                xlabel="Histology",
                ylabel="",
                xlim=(0, 1),
                toolbar=None,
                default_tools=[],
                tools=["ywheel_zoom", "ypan"],
                active_tools=["ywheel_zoom"],
                xaxis=None,  # Hide x-axis for histology
                yaxis=None,  # Hide y-axis (shared with ephys plots)
                margin=0,
            )
        )

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

    @param.depends("refresh")
    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the histology visualization.
        """
        plot = self.get_plot()

        return pn.Column(
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
