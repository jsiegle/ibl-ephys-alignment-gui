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

import panel as pn

pn.extension("plotly", "tabulator", sizing_mode="stretch_width")

from ephys_alignment_gui.web.app import AlignmentApp


def main():

    print("ALIGNMENT APP STARTING")

    # Create the full app
    app = AlignmentApp()

    print(f"\n=== TEST 7 SETUP ===")
    print(f"AlignmentControls instance: {id(app.main_layout.alignment_controls)}")
    print(f"Fit button instance: {id(app.main_layout.alignment_controls._fit_button)}")
    print(f"Number of watchers on fit_clicked: {len(app.main_layout.alignment_controls.param.watchers.get('fit_clicked', []))}")
    print(f"===================\n")

    # Serve the full app (use same port and settings as main app for comparison)
    pn.serve(app.view, port=5006, show=False, title="Ephys Alignment GUI", websocket_origin="*")
