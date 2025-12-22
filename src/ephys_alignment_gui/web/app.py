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
pn.extension("tabulator", sizing_mode="stretch_width")

# Keyboard shortcut JavaScript
KEYBOARD_SHORTCUTS_JS = """
window.addEventListener('keydown', function(e) {
    // Only handle if not in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    switch(e.key) {
        case 'Enter':
            // Trigger fit
            document.dispatchEvent(new CustomEvent('alignment-fit'));
            e.preventDefault();
            break;
        case 'o':
        case 'O':
            // Trigger offset
            document.dispatchEvent(new CustomEvent('alignment-offset'));
            e.preventDefault();
            break;
        case 'ArrowRight':
            // Next
            document.dispatchEvent(new CustomEvent('alignment-next'));
            e.preventDefault();
            break;
        case 'ArrowLeft':
            // Previous
            document.dispatchEvent(new CustomEvent('alignment-prev'));
            e.preventDefault();
            break;
        case 'r':
            if (e.ctrlKey || e.metaKey) {
                // Reset (Ctrl+R)
                document.dispatchEvent(new CustomEvent('alignment-reset'));
                e.preventDefault();
            }
            break;
        case 's':
            if (e.ctrlKey || e.metaKey) {
                // Save (Ctrl+S)
                document.dispatchEvent(new CustomEvent('alignment-save'));
                e.preventDefault();
            }
            break;
        case 'd':
            if (e.shiftKey) {
                // Delete line (Shift+D)
                document.dispatchEvent(new CustomEvent('alignment-delete-line'));
                e.preventDefault();
            }
            break;
    }
});
console.log('Keyboard shortcuts enabled: Enter=Fit, O=Offset, Arrows=Nav, Ctrl+R=Reset, Ctrl+S=Save, Shift+D=Delete');
"""


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

        logger.info("AlignmentApp initialized")

    def _on_data_loaded(self, event) -> None:
        """Handle data loaded event from DataSelectionPanel."""
        logger.info("Data load completed, refreshing plots")
        # Trigger refresh on all components via the main layout
        self.main_layout.ephys_plots.param.trigger("refresh")
        self.main_layout.histology_panel.param.trigger("refresh")
        self.main_layout.slice_viewer.param.trigger("refresh")
        self.main_layout.alignment_controls.param.trigger("refresh")
        self.main_layout.reference_lines.param.trigger("refresh")

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

    def _create_keyboard_handler(self) -> pn.pane.HTML:
        """Create keyboard shortcut handler.

        Returns
        -------
        pn.pane.HTML
            Hidden HTML pane with keyboard handling script.
        """
        return pn.pane.HTML(
            f"<script>{KEYBOARD_SHORTCUTS_JS}</script>",
            height=0,
            width=0,
            sizing_mode="fixed",
        )

    def view(self) -> pn.template.FastListTemplate:
        """Create and return the main application view.

        Returns
        -------
        pn.template.FastListTemplate
            The complete application layout.
        """
        # Create keyboard handler (injected into sidebar to avoid blank space)
        keyboard_handler = self._create_keyboard_handler()

        template = pn.template.FastListTemplate(
            title="Ephys Alignment GUI",
            sidebar=[keyboard_handler, self._create_sidebar()],
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
