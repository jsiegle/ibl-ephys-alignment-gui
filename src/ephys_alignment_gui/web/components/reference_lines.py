"""Reference lines component for the web frontend (Plotly version).

Manages draggable reference lines used for alignment between
ephys features and histology boundaries.

This version uses Plotly's native editable shapes feature.
"""

import logging

import numpy as np
import panel as pn
import param

from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)

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
]


class ReferenceLinesManager(param.Parameterized):
    """Manages reference lines for Plotly-based alignment.

    Stores line positions and triggers events when they change.
    Plotly figures add shapes directly using `add_shapes_to_figure()`.
    
    Each line has two Y positions:
    - y_feature: Position across ephys plots (image, line, probe)
    - y_track: Independent position on histology plot

    Parameters
    ----------
    state : AppState
        Shared application state.

    Attributes
    ----------
    lines_changed : param.Event
        Triggered when lines are added, removed, or moved.
    selected_index : int
        Index of currently selected line.
    lines : list of tuple
        List of (y_feature, y_track) tuples.
    """

    # Events
    lines_changed = param.Event(doc="Reference lines changed")

    # Selection state
    selected_index = param.Integer(
        default=0,
        doc="Index of selected line",
    )

    # Line storage  
    lines = param.List(default=[], doc="List of (y_feature, y_track) tuples")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state

    @property
    def feature_positions(self) -> np.ndarray:
        """Get feature (ephys) positions of lines."""
        if not self.lines:
            return np.array([])
        return np.array([line[0] for line in self.lines])

    @property
    def track_positions(self) -> np.ndarray:
        """Get track (histology) positions of lines."""
        if not self.lines:
            return np.array([])
        return np.array([line[1] for line in self.lines])

    @property
    def n_lines(self) -> int:
        """Get the number of reference lines."""
        return len(self.lines)

    def add_line(
        self,
        y_feature: float,
        y_track: float | None = None,
    ) -> int:
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

        self.lines = self.lines + [(y_feature, y_track)]
        self.param.trigger("lines_changed")
        logger.info(f"Added reference line at feature={y_feature}, track={y_track}")
        return len(self.lines) - 1

    def remove_line(self, index: int) -> None:
        """Remove a reference line by index.

        Parameters
        ----------
        index : int
            Index of the line to remove.
        """
        if 0 <= index < len(self.lines):
            removed = self.lines[index]
            self.lines = [line for i, line in enumerate(self.lines) if i != index]
            
            # Update selection
            if self.selected_index >= len(self.lines) and len(self.lines) > 0:
                self.selected_index = len(self.lines) - 1
            elif len(self.lines) == 0:
                self.selected_index = 0
                
            self.param.trigger("lines_changed")
            logger.info(f"Removed reference line {index}: {removed}")

    def remove_last_line(self) -> None:
        """Remove the most recently added reference line."""
        if self.lines:
            self.remove_line(len(self.lines) - 1)

    def remove_selected_line(self) -> None:
        """Remove the currently selected reference line."""
        if 0 <= self.selected_index < len(self.lines):
            self.remove_line(self.selected_index)

    def clear_lines(self) -> None:
        """Remove all reference lines."""
        self.lines = []
        self.selected_index = 0
        self.param.trigger("lines_changed")
        logger.info("Cleared all reference lines")

    def select_next_line(self) -> None:
        """Select the next reference line."""
        if self.lines:
            self.selected_index = (self.selected_index + 1) % len(self.lines)
            self.param.trigger("lines_changed")
            logger.debug(f"Selected line {self.selected_index}")

    def select_prev_line(self) -> None:
        """Select the previous reference line."""
        if self.lines:
            self.selected_index = (self.selected_index - 1) % len(self.lines)
            self.param.trigger("lines_changed")
            logger.debug(f"Selected line {self.selected_index}")

    def update_line_position(
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
        if 0 <= index < len(self.lines):
            old_feature, old_track = self.lines[index]
            new_feature = y_feature if y_feature is not None else old_feature
            new_track = y_track if y_track is not None else old_track
            
            # Update the line
            new_lines = list(self.lines)
            new_lines[index] = (new_feature, new_track)
            self.lines = new_lines
            
            self.param.trigger("lines_changed")
            logger.debug(f"Updated line {index} to feature={new_feature:.1f}, track={new_track:.1f}")

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

    def view(self) -> pn.Column:
        """Return a Panel view showing line information and controls.

        Returns
        -------
        pn.Column
            Panel column with line list and controls.
        """
        components = []

        # Add Line button
        def on_add_line(event):
            midpoint = (self.state.probe_tip + self.state.probe_top) / 2
            self.add_line(midpoint)

        add_btn = pn.widgets.Button(
            name="+ Add Line",
            button_type="success",
            width=200,
            margin=(2, 5),
        )
        add_btn.on_click(on_add_line)
        components.append(add_btn)

        if not self.lines:
            components.append(
                pn.pane.Markdown(
                    "*No reference lines yet*",
                    styles={"color": "#666", "font-style": "italic"},
                )
            )
        else:
            # Header
            components.append(
                pn.pane.Markdown(f"**{len(self.lines)} reference line(s)**")
            )

            # Create a button for each line
            for i, (feat, track) in enumerate(self.lines):
                is_selected = i == self.selected_index
                button_type = "primary" if is_selected else "default"
                button_text = f"Line {i+1}: {feat:.0f}μm → {track:.0f}μm"
                if is_selected:
                    button_text = f"● {button_text}"

                btn = pn.widgets.Button(
                    name=button_text,
                    button_type=button_type,
                    width=200,
                    margin=(2, 5),
                )

                def make_select_callback(idx: int):
                    def callback(event):
                        self.selected_index = idx
                        self.param.trigger("lines_changed")
                    return callback

                btn.on_click(make_select_callback(i))
                components.append(btn)

            # Delete button for selected line
            if 0 <= self.selected_index < len(self.lines):
                delete_btn = pn.widgets.Button(
                    name="Delete Selected",
                    button_type="danger",
                    width=200,
                    margin=(10, 5, 2, 5),
                )
                delete_btn.on_click(lambda event: self.remove_selected_line())
                components.append(delete_btn)

        return pn.Column(*components, sizing_mode="stretch_width")

    def controls(self) -> pn.Column:
        """Return a reactive Panel view that updates when lines change.

        Returns
        -------
        pn.Column
            Reactive Panel column.
        """
        return pn.bind(lambda _: self.view(), self.param.lines_changed)
