"""Web-based frontend for the ephys alignment application.

This subpackage contains a Panel/HoloViews-based web frontend that provides
browser-based access to the alignment tool without requiring PyQt5 installation.

The web frontend reuses the core/, io/, and visualization/ modules for data
handling and computation, only replacing the GUI layer.

Usage:
    # Standalone server
    from ephys_alignment_gui.web.app import main
    main()

    # Or via CLI
    launch-web

    # In Jupyter
    from ephys_alignment_gui.web.app import AlignmentApp
    app = AlignmentApp()
    app.view().servable()
"""

from ephys_alignment_gui.web.app import AlignmentApp, main

__all__ = [
    "AlignmentApp",
    "main",
]
