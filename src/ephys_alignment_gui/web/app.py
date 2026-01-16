import logging

import panel as pn
import param

from ephys_alignment_gui.web.components.data_selection_panel import DataSelectionPanel
from ephys_alignment_gui.web.layouts.main_layout import MainLayout
from ephys_alignment_gui.web.state import AppState

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configure Panel
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")


class AlignmentApp(param.Parameterized):
    """Main application class for the web-based alignment GUI.

    This class coordinates all components and provides the main application
    layout. It uses reactive state management via AppState to synchronize
    state across components.

    Example
    -------
    >>> app = AlignmentApp()
    >>> app.view().servable()  # In Jupyter
    >>> # Or
    >>> pn.serve(app.view)  # Standalone server
    """

    def __init__(self, **params):
        super().__init__(**params)

        # Initialize shared state
        self.state = AppState()

        # Initialize components
        self.selection_panel = DataSelectionPanel(self.state)
        self.main_layout = MainLayout(self.state)

        # Wire up inter-component communication
        self.selection_panel.param.watch(self._on_data_loaded, "load_requested")
        self.selection_panel.param.watch(self._on_reset_clicked, "reset_clicked")
        self.selection_panel.param.watch(self._on_save_clicked, "save_clicked")

        logger.info("AlignmentApp initialized")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event from DataSelectionPanel."""
        logger.info("Data load completed - components will refresh reactively via state changes")
        # Components are reactive via @param.depends on state parameters
        # They will automatically update when state.data_loaded changes
        # No manual refresh needed

    def _on_reset_clicked(self, event) -> None:
        """Handle reset event from DataSelectionPanel."""
        self.main_layout._on_reset_clicked(event)

    def _on_save_clicked(self, event) -> None:
        """Handle save event from DataSelectionPanel."""
        # TODO: Implement save functionality
        logger.info("Save clicked - functionality not yet implemented")

    def _create_sidebar(self) -> pn.Column:
        """Create the sidebar with controls."""
        return pn.Column(
            self.selection_panel.view(),
            sizing_mode="stretch_width",
            width=320,
        )

    def _create_main_content(self) -> pn.Column:
        """Create the main content area with plots."""
        # Use the main layout which coordinates all visualization components
        # Areas are cached internally with their own reactive bindings
        return pn.Column(
            self.main_layout.view(),
            sizing_mode="stretch_both",
        )

    def view(self) -> pn.template.FastListTemplate:
        """Create and return the main application view.

        Returns
        -------
        pn.template.FastListTemplate
            The complete application layout.
        """

        template = pn.template.FastListTemplate(
            title="Ephys Alignment GUI",
            sidebar=[self._create_sidebar()],
            main=[self._create_main_content()],
            accent_base_color="#6B5B95",
            header_background="#6B5B95",
            sidebar_width=320,
        )

        return template
