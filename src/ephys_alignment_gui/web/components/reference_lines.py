"""Reference lines component for the web frontend.

Manages draggable reference lines used for alignment between
ephys features and histology boundaries.

Supports double-click to add lines via HoloViews DoubleTap stream.
"""

import logging
from typing import TYPE_CHECKING, Callable

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts, streams
from holoviews.streams import DoubleTap, Tap

from ephys_alignment_gui.web.state import AppState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Configure HoloViews
hv.extension("bokeh")

# Color palette for reference lines
LINE_COLORS = [
    "#e41a1c",  # red
    "#377eb8",  # blue
    "#4daf4a",  # green
    "#984ea3",  # purple
    "#ff7f00",  # orange
    "#ffff33",  # yellow
    "#a65628",  # brown
    "#f781bf",  # pink
    "#999999",  # gray
    "#000000",  # black
]


class ReferenceLinesManager(param.Parameterized):
    """Manages reference lines for alignment.

    Provides functionality to add, remove, and move reference lines
    that connect ephys features to histology boundaries.

    Parameters
    ----------
    state : AppState
        Shared application state.
    """

    # Events
    lines_changed = param.Event(doc="Reference lines changed")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state

        # Internal line storage: list of (y_feature, y_track) tuples
        self._lines: list[tuple[float, float]] = []

        # Watch state changes
        state.param.watch(self._on_lines_changed, "reference_lines")

    def _on_lines_changed(self, event) -> None:
        """Handle reference lines state change."""
        self.param.trigger("lines_changed")

    @property
    def lines(self) -> list[tuple[float, float]]:
        """Get current reference lines."""
        return list(self._lines)

    @property
    def feature_positions(self) -> np.ndarray:
        """Get feature (ephys) positions of lines."""
        if not self._lines:
            return np.array([])
        return np.array([line[0] for line in self._lines])

    @property
    def track_positions(self) -> np.ndarray:
        """Get track (histology) positions of lines."""
        if not self._lines:
            return np.array([])
        return np.array([line[1] for line in self._lines])

    def add_line(self, y_feature: float, y_track: float | None = None) -> int:
        """Add a new reference line.

        Parameters
        ----------
        y_feature : float
            Y position on the ephys feature plot.
        y_track : float, optional
            Y position on the histology plot. Defaults to same as y_feature.

        Returns
        -------
        int
            Index of the new line.
        """
        if y_track is None:
            y_track = y_feature

        self._lines.append((y_feature, y_track))
        self._update_state()
        logger.info(f"Added reference line at feature={y_feature}, track={y_track}")
        return len(self._lines) - 1

    def remove_line(self, index: int) -> None:
        """Remove a reference line by index.

        Parameters
        ----------
        index : int
            Index of the line to remove.
        """
        if 0 <= index < len(self._lines):
            removed = self._lines.pop(index)
            self._update_state()
            logger.info(f"Removed reference line {index}: {removed}")

    def remove_last_line(self) -> None:
        """Remove the most recently added reference line."""
        if self._lines:
            self.remove_line(len(self._lines) - 1)

    def clear_lines(self) -> None:
        """Remove all reference lines."""
        self._lines.clear()
        self._update_state()
        logger.info("Cleared all reference lines")

    def update_line(
        self,
        index: int,
        y_feature: float | None = None,
        y_track: float | None = None,
    ) -> None:
        """Update a reference line position.

        Parameters
        ----------
        index : int
            Index of the line to update.
        y_feature : float, optional
            New feature position.
        y_track : float, optional
            New track position.
        """
        if 0 <= index < len(self._lines):
            old_feature, old_track = self._lines[index]
            new_feature = y_feature if y_feature is not None else old_feature
            new_track = y_track if y_track is not None else old_track
            self._lines[index] = (new_feature, new_track)
            self._update_state()

    def _update_state(self) -> None:
        """Update state with current lines."""
        self.state.reference_lines = [
            {"feature": f, "track": t} for f, t in self._lines
        ]
        self.param.trigger("lines_changed")

    def get_line_color(self, index: int) -> str:
        """Get color for a line by index.

        Parameters
        ----------
        index : int
            Line index.

        Returns
        -------
        str
            Hex color string.
        """
        return LINE_COLORS[index % len(LINE_COLORS)]

    def create_feature_lines_overlay(self) -> hv.Overlay:
        """Create HoloViews overlay of reference lines for feature plot.

        Returns
        -------
        hv.Overlay
            Overlay of horizontal lines at feature positions.
        """
        elements = []
        for i, (y_feature, _) in enumerate(self._lines):
            line = hv.HLine(y_feature).opts(
                line_color=self.get_line_color(i),
                line_dash="dashed",
                line_width=2,
            )
            elements.append(line)
        return hv.Overlay(elements) if elements else hv.Overlay([])

    def create_track_lines_overlay(self) -> hv.Overlay:
        """Create HoloViews overlay of reference lines for track plot.

        Returns
        -------
        hv.Overlay
            Overlay of horizontal lines at track positions.
        """
        elements = []
        for i, (_, y_track) in enumerate(self._lines):
            line = hv.HLine(y_track).opts(
                line_color=self.get_line_color(i),
                line_dash="dashed",
                line_width=2,
            )
            elements.append(line)
        return hv.Overlay(elements) if elements else hv.Overlay([])

    def create_tap_stream(self, source: hv.Element = None) -> DoubleTap:
        """Create a DoubleTap stream for adding lines on double-click.

        Parameters
        ----------
        source : hv.Element, optional
            HoloViews element to attach the stream to.

        Returns
        -------
        DoubleTap
            Stream that triggers on double-click.
        """
        stream = DoubleTap(source=source, x=None, y=None)
        return stream

    def handle_double_tap(self, x: float | None, y: float | None) -> None:
        """Handle double-tap event to add a reference line.

        Parameters
        ----------
        x : float or None
            X coordinate of tap (ignored for horizontal lines).
        y : float or None
            Y coordinate of tap - becomes the line position.
        """
        if y is not None:
            self.add_line(y)
            logger.info(f"Added reference line at y={y:.1f} via double-tap")

    def create_interactive_overlay(
        self,
        base_plot: hv.Element,
        on_feature_plot: bool = True,
    ) -> hv.DynamicMap:
        """Create a DynamicMap that shows lines and responds to double-clicks.

        Parameters
        ----------
        base_plot : hv.Element
            The base plot to overlay lines on.
        on_feature_plot : bool
            If True, use feature positions; if False, use track positions.

        Returns
        -------
        hv.DynamicMap
            Interactive plot with reference lines overlay.
        """
        # Create double-tap stream attached to base plot
        tap_stream = self.create_tap_stream(source=base_plot)

        def update_and_overlay(x, y):
            # Handle new tap if coordinates provided
            if y is not None:
                self.handle_double_tap(x, y)

            # Return current lines overlay
            if on_feature_plot:
                return self.create_feature_lines_overlay()
            else:
                return self.create_track_lines_overlay()

        # Create DynamicMap that updates on tap
        lines_dmap = hv.DynamicMap(update_and_overlay, streams=[tap_stream])

        return base_plot * lines_dmap

    def view(self) -> pn.Column:
        """Return a Panel view showing line information.

        Returns
        -------
        pn.Column
            Panel column with line count and list.
        """
        if not self._lines:
            return pn.pane.Markdown("*No reference lines*\n\n*Double-click on plot to add*")

        lines_text = f"**{len(self._lines)} reference line(s)**\n\n"
        for i, (feat, track) in enumerate(self._lines):
            color = self.get_line_color(i)
            lines_text += f"- Line {i+1}: feature={feat:.0f}μm, track={track:.0f}μm\n"
        lines_text += "\n*Double-click on plot to add more*"

        return pn.pane.Markdown(lines_text)
