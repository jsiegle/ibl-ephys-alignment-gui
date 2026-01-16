"""Alignment control buttons for the web frontend.

Provides fit, offset, navigation, and delete line controls for the
alignment workflow. Reset and Save buttons are in the data selection panel.
"""

import logging

import panel as pn
import param

from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)


class AlignmentControls(param.Parameterized):
    """Control panel for alignment operations.

    Provides buttons for fit, offset, navigation (next/prev), and
    delete line. Reset/Save are in the data selection panel.
    Emits events that can be watched by other components to trigger
    alignment logic.

    Parameters
    ----------
    state : AppState
        Shared application state.
    """

    # Events for alignment operations
    fit_clicked = param.Event(doc="Fit button clicked")
    offset_clicked = param.Event(doc="Offset button clicked")
    next_clicked = param.Event(doc="Next button clicked")
    prev_clicked = param.Event(doc="Previous button clicked")
    delete_line_clicked = param.Event(doc="Delete line button clicked")

    def __init__(self, state: AppState, **params):
        super().__init__(**params)
        self.state = state
        print(f"DEBUG: AlignmentControls.__init__ called, self={id(self)}")

        # Create buttons with consistent sizing
        btn_width = 90

        self._fit_button = pn.widgets.Button(
            name="Fit (Enter)",
            button_type="primary",
            width=btn_width,
        )
        self._offset_button = pn.widgets.Button(
            name="(O)ffset",
            button_type="default",
            width=btn_width,
        )
        self._next_button = pn.widgets.Button(
            name="Next →",
            button_type="default",
            width=btn_width,
        )
        self._prev_button = pn.widgets.Button(
            name="← Prev",
            button_type="default",
            width=btn_width,
        )
        self._delete_line_button = pn.widgets.Button(
            name="Delete Line",
            button_type="danger",
            width=btn_width,
        )

        logger.debug("Setting up button click handlers")
        self._fit_button.on_click(self._on_fit_clicked)
        self._offset_button.on_click(self._on_offset_clicked)
        self._next_button.on_click(self._on_next_clicked)
        self._prev_button.on_click(self._on_prev_clicked)
        self._delete_line_button.on_click(self._on_delete_line_clicked)

        # Watch state changes
        state.param.watch(self._on_data_loaded, "data_loaded")
        
        # Cache the view to preserve button instances and their watchers
        self._view_cache = None

    def _on_data_loaded(self, event) -> None:
        """Enable/disable buttons based on data load state."""
        # Buttons are enabled by default for testing without data
        # Uncomment to disable when no data is loaded:
        # enabled = event.new
        # self._fit_button.disabled = not enabled
        # self._offset_button.disabled = not enabled
        # self._next_button.disabled = not enabled
        # self._prev_button.disabled = not enabled
        # self._delete_line_button.disabled = not enabled
        pass

    def _on_fit_clicked(self, event) -> None:
        """Handle fit button click."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
        print(f"\n{'='*60}")
        print(f"DEBUG [{timestamp}]: _on_fit_clicked called!")
        print(f"  event={event}")
        print(f"  self={id(self)}")
        print(f"  button={id(self._fit_button)}")
        print(f"{'='*60}\n")
        logger.info("Fit button clicked")
        self.param.trigger("fit_clicked")

    def _on_offset_clicked(self, event) -> None:
        """Handle offset button click."""
        logger.info("Offset button clicked")
        self.param.trigger("offset_clicked")

    def _on_next_clicked(self, event) -> None:
        """Handle next button click."""
        if self.state.current_idx < self.state.total_idx:
            self.state.current_idx += 1
            logger.info(f"Next: move {self.state.current_idx}/{self.state.total_idx}")
        self.param.trigger("next_clicked")

    def _on_prev_clicked(self, event) -> None:
        """Handle previous button click."""
        if self.state.current_idx > 0:
            self.state.current_idx -= 1
            logger.info(f"Prev: move {self.state.current_idx}/{self.state.total_idx}")
        self.param.trigger("prev_clicked")

    def _on_delete_line_clicked(self, event) -> None:
        """Handle delete line button click."""
        logger.info("Delete line button clicked")
        self.param.trigger("delete_line_clicked")

    def _create_move_indicator(self):
        """Create a reactive move index indicator."""
        return pn.bind(
            lambda idx, total: f"**Move:** {idx}/{total}",
            self.state.param.current_idx,
            self.state.param.total_idx,
        )

    def view(self) -> pn.Column:
        """Return the Panel layout for this component.

        Returns
        -------
        pn.Column
            Panel column containing the alignment controls.
        """
        # Cache the view to preserve button widget instances
        if self._view_cache is None:
            move_indicator = pn.pane.Markdown(self._create_move_indicator())
            print(f"DEBUG: AlignmentControls.view(), fit_button={id(self._fit_button)}, clicks={self._fit_button.clicks}")

            self._view_cache = pn.Column(
                pn.pane.Markdown("### Alignment Controls", margin=(0, 0, 10, 0)),
                pn.Row(
                    self._fit_button,
                    self._offset_button,
                    self._delete_line_button,
                    margin=(0, 0, 5, 0),
                ),
                pn.Row(
                    self._prev_button,
                    self._next_button,
                    move_indicator,
                    align="start",
                    margin=(0, 0, 5, 0),
                ),
                sizing_mode="stretch_width",
                max_width=300,
                margin=(5, 10, 5, 10),
            )
        return self._view_cache
