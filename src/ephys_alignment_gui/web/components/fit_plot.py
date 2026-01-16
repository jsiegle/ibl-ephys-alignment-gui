"""Fit plot component for the web frontend.

Displays the feature-to-track mapping showing how electrophysiology
coordinates map to histology track coordinates after alignment.
"""

import logging

import numpy as np
import panel as pn
import param
import plotly.graph_objects as go

from ephys_alignment_gui.core.alignment import EphysAlignment
from ephys_alignment_gui.web.components.reference_lines import ReferenceLinesManager
from ephys_alignment_gui.web.state import AppState

logger = logging.getLogger(__name__)


class FitPlot(param.Parameterized):
    """Fit plot visualization showing feature-to-track correspondence.

    Displays:
    - Diagonal reference line (y=x) showing "no transformation"
    - Current alignment curve mapping features to track positions
    - Reference line scatter points from user alignment markers
    - Optional linear fit extrapolation line

    Parameters
    ----------
    state : AppState
        Shared application state.
    reference_lines : ReferenceLinesManager
        Manager for reference line positions.
    """

    # Refresh counter for reactive updates
    _refresh_counter = param.Integer(default=0, doc="Refresh trigger")

    def __init__(
        self,
        state: AppState,
        reference_lines: ReferenceLinesManager,
        **params,
    ):
        super().__init__(**params)
        self.state = state
        self.reference_lines = reference_lines

        # Watch for alignment changes
        state.param.watch(self._on_state_changed, ["current_idx", "total_idx", "lin_fit"])
        reference_lines.param.watch(self._on_lines_changed, "lines_changed")

    def _on_state_changed(self, event) -> None:
        """Trigger refresh when alignment state changes."""
        self._refresh_counter += 1

    def _on_lines_changed(self, event) -> None:
        """Trigger refresh when reference lines change."""
        self._refresh_counter += 1

    def refresh(self) -> None:
        """Manually trigger a refresh."""
        self._refresh_counter += 1

    def _create_figure(
        self,
        features: np.ndarray | None,
        track: np.ndarray | None,
    ) -> go.Figure:
        """Create the Plotly fit plot figure.

        Parameters
        ----------
        features : np.ndarray or None
            Current feature-space reference coordinates (meters).
        track : np.ndarray or None
            Current track-space reference coordinates (meters).

        Returns
        -------
        go.Figure
            Plotly figure showing the fit plot.
        """
        fig = go.Figure()

        # Determine axis range based on probe bounds
        probe_tip = self.state.probe_tip
        probe_top = self.state.probe_top
        padding = 500  # μm padding
        axis_min = probe_tip - padding
        axis_max = probe_top + padding

        # If we have alignment data, extend range to cover it
        if features is not None and len(features) > 0:
            feat_um = features * 1e6
            axis_min = min(axis_min, feat_um.min() - padding)
            axis_max = max(axis_max, feat_um.max() + padding)
        if track is not None and len(track) > 0:
            track_um = track * 1e6
            axis_min = min(axis_min, track_um.min() - padding)
            axis_max = max(axis_max, track_um.max() + padding)

        # 1. Diagonal reference line (y=x) - no transformation
        diag_range = np.array([axis_min, axis_max])
        fig.add_trace(
            go.Scatter(
                x=diag_range,
                y=diag_range,
                mode="lines",
                line=dict(color="black", width=1, dash="dot"),
                name="No transform (y=x)",
                hoverinfo="skip",
            )
        )

        # 2. Current alignment mapping (feature -> track)
        if features is not None and track is not None and len(features) > 0:
            # Convert to μm for display
            feat_um = features * 1e6
            track_um = track * 1e6

            # Sort by feature position for proper line drawing
            sort_idx = np.argsort(feat_um)
            feat_sorted = feat_um[sort_idx]
            track_sorted = track_um[sort_idx]

            # Alignment curve
            fig.add_trace(
                go.Scatter(
                    x=feat_sorted,
                    y=track_sorted,
                    mode="lines+markers",
                    line=dict(color="blue", width=2),
                    marker=dict(color="white", size=8, line=dict(color="blue", width=2)),
                    name="Alignment",
                    hovertemplate="Feature: %{x:.0f}μm<br>Track: %{y:.0f}μm<extra></extra>",
                )
            )

            # 3. Linear fit extrapolation (if enabled and enough points)
            if self.state.lin_fit and len(features) >= 5:
                lin_fit = EphysAlignment.feature2track_lin(
                    diag_range / 1e6,  # Convert back to meters for computation
                    features,
                    track,
                )
                if np.any(lin_fit):
                    lin_fit_um = lin_fit * 1e6
                    fig.add_trace(
                        go.Scatter(
                            x=diag_range,
                            y=lin_fit_um,
                            mode="lines",
                            line=dict(color="red", width=2, dash="dash"),
                            name="Linear fit",
                            hoverinfo="skip",
                        )
                    )

        # 4. Reference line points (user-added markers)
        if self.reference_lines.n_lines > 0:
            feat_pts = self.reference_lines.feature_positions
            track_pts = self.reference_lines.track_positions
            fig.add_trace(
                go.Scatter(
                    x=feat_pts,
                    y=track_pts,
                    mode="markers",
                    marker=dict(
                        color="red",
                        size=12,
                        symbol="circle",
                        line=dict(color="darkred", width=2),
                    ),
                    name="Reference lines",
                    hovertemplate="Feature: %{x:.0f}μm<br>Track: %{y:.0f}μm<extra></extra>",
                )
            )

        # Configure layout
        fig.update_layout(
            xaxis=dict(
                title="Original coordinates (μm)",
                range=[axis_min, axis_max],
                showgrid=True,
                gridcolor="lightgray",
                zeroline=False,
            ),
            yaxis=dict(
                title="New coordinates (μm)",
                range=[axis_min, axis_max],
                showgrid=True,
                gridcolor="lightgray",
                zeroline=False,
                scaleanchor="x",  # Keep aspect ratio 1:1
                scaleratio=1,
            ),
            plot_bgcolor="white",
            margin=dict(l=60, r=20, t=30, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            showlegend=True,
        )

        return fig

    @param.depends("_refresh_counter")
    def view(self) -> pn.pane.Plotly:
        """Return the fit plot view.

        Returns
        -------
        pn.pane.Plotly
            Panel Plotly pane with the fit plot.
        """
        # Get current alignment state
        features = self.state.features
        track = self.state.track

        fig = self._create_figure(features, track)

        return pn.pane.Plotly(
            fig,
            sizing_mode="stretch_both",
            min_height=200,
            config={"displayModeBar": False},
        )

    def controls(self) -> pn.Column:
        """Return the fit plot controls (linear fit checkbox).

        Returns
        -------
        pn.Column
            Panel column with controls.
        """
        lin_fit_checkbox = pn.widgets.Checkbox.from_param(
            self.state.param.lin_fit,
            name="Linear fit extrapolation",
        )

        def on_checkbox_change(event):
            self._refresh_counter += 1

        lin_fit_checkbox.param.watch(on_checkbox_change, "value")

        return pn.Column(
            lin_fit_checkbox,
            sizing_mode="stretch_width",
        )
