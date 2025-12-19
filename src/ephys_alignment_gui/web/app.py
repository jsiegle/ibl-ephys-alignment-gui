"""Main application entry point for the web frontend.

Provides a Panel-based web interface for the ephys alignment tool.

Usage:
    # Standalone server
    python -m ephys_alignment_gui.web.app

    # Or via CLI (after installation)
    launch-web

    # In Jupyter
    from ephys_alignment_gui.web.app import AlignmentApp
    app = AlignmentApp()
    app.view().servable()
"""

import logging

import panel as pn
import param

from ephys_alignment_gui.web.components.data_loader import DataLoader
from ephys_alignment_gui.web.components.ephys_plots import EphysPlots
from ephys_alignment_gui.web.state import AppState

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configure Panel
pn.extension("tabulator", sizing_mode="stretch_width")


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
        self.data_loader = DataLoader(self.state)
        self.ephys_plots = EphysPlots(self.state)

        # Wire up inter-component communication
        self.data_loader.param.watch(self._on_data_loaded, "load_requested")

        logger.info("AlignmentApp initialized")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event from DataLoader."""
        logger.info("Data load completed, refreshing plots")
        self.ephys_plots.param.trigger("refresh")

    def _create_header(self) -> pn.Row:
        """Create the application header."""
        title = pn.pane.Markdown(
            "# Ephys Alignment GUI",
            sizing_mode="stretch_width",
        )
        status = pn.bind(
            lambda msg, loading: f"**Status:** {msg}" + (" ⏳" if loading else " ✓"),
            self.state.param.status_message,
            self.state.param.loading,
        )
        status_pane = pn.pane.Markdown(status, sizing_mode="fixed", width=300)

        return pn.Row(title, status_pane, sizing_mode="stretch_width")

    def _create_sidebar(self) -> pn.Column:
        """Create the sidebar with controls."""
        return pn.Column(
            self.data_loader.view(),
            pn.layout.Divider(),
            self.ephys_plots.controls(),
            sizing_mode="stretch_width",
            width=300,
        )

    def _create_main_content(self) -> pn.Column:
        """Create the main content area with plots."""
        # Use pn.bind to create reactive plot view
        plot_view = pn.bind(lambda _: self.ephys_plots.view(), self.ephys_plots.param.refresh)

        return pn.Column(
            plot_view,
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


def main():
    """Main entry point for standalone server."""
    logger.info("Starting Ephys Alignment GUI web server...")

    app = AlignmentApp()

    # Serve the application
    pn.serve(
        app.view,
        port=5006,
        show=True,
        title="Ephys Alignment GUI",
        websocket_origin="*",  # Allow connections from any origin for development
    )


if __name__ == "__main__":
    main()
