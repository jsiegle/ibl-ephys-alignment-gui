"""Histology track loading and interpolation utilities.

This module provides functions for loading and processing histology track data,
including coordinate interpolation along probe trajectories and brain region lookup.
"""

import logging
from pathlib import Path

import iblatlas.atlas as atlas
import numpy as np
from numpy.typing import NDArray

from ephys_alignment_gui.core.probe_geometry import trace_header

_logger = logging.getLogger(__name__)


def load_track_csv(
    file_track: str | Path, brain_atlas: atlas.BrainAtlas | None = None
) -> NDArray:
    """
    Load a Lasagna track CSV file and convert to IBL-Allen coordinate framework.

    Parameters
    ----------
    file_track : str or Path
        Path to the CSV file containing track coordinates.
    brain_atlas : atlas.BrainAtlas, optional
        Brain atlas instance for coordinate conversion. Defaults to AllenAtlas(25).

    Returns
    -------
    NDArray
        Array of xyz coordinates in IBL-Allen framework, shape (n_points, 3).
        Returns empty array if file is empty.
    """
    brain_atlas = brain_atlas or atlas.AllenAtlas(25)
    # apmldv in the histology file is flipped along y direction
    file_track = Path(file_track)
    if file_track.stat().st_size == 0:
        return np.array([])
    ixiyiz = np.loadtxt(file_track, delimiter=",")[:, [1, 0, 2]]
    ixiyiz[:, 1] = 527 - ixiyiz[:, 1]
    ixiyiz = ixiyiz[np.argsort(ixiyiz[:, 2]), :]
    xyz = brain_atlas.bc.i2xyz(ixiyiz)
    return xyz


def get_picked_tracks(
    histology_path: str | Path,
    glob_pattern: str = "*_pts_transformed.csv",
    brain_atlas: atlas.BrainAtlas | None = None,
) -> dict:
    """
    Read Lasagna output files and convert picked tracks to IBL coordinates.

    Parameters
    ----------
    histology_path : str or Path
        Folder path containing track files, or path to a single track file.
    glob_pattern : str, optional
        Glob pattern for finding track files. Default: "*_pts_transformed.csv"
    brain_atlas : atlas.BrainAtlas, optional
        Brain atlas instance. Defaults to AllenAtlas().

    Returns
    -------
    dict
        Dictionary with keys:
        - 'files': list of Path objects for found track files
        - 'xyz': list of xyz coordinate arrays for each track
    """
    brain_atlas = brain_atlas or atlas.AllenAtlas()
    xyzs = []
    histology_path = Path(histology_path)
    if histology_path.is_file():
        files_track = [histology_path]
    else:
        files_track = list(histology_path.rglob(glob_pattern))
    for file_track in files_track:
        xyzs.append(load_track_csv(file_track, brain_atlas=brain_atlas))
    return {"files": files_track, "xyz": xyzs}


def interpolate_along_track(
    track_annos_and_ends_ras: NDArray, depths: NDArray
) -> NDArray:
    """
    Get 3D coordinates of points along a track at specified distances from the first point.

    Performs linear interpolation along the cumulative distance of the track
    to compute xyz coordinates at arbitrary depth positions.

    Parameters
    ----------
    track_annos_and_ends_ras : NDArray
        Array of shape (n_points, 3) defining the track in RAS coordinates.
        Usually the first point is the deepest (most ventral).
    depths : NDArray
        Array of distances from the first point of the track.
        Convention: deepest point is 0, values increase going dorsally.

    Returns
    -------
    NDArray
        Array of shape (len(depths), 3) with interpolated xyz coordinates
        in RAS space.
    """
    # Compute cumulative distance from the lowest picked point (first)
    distance = np.cumsum(
        np.r_[
            0, np.sqrt(np.sum(np.diff(track_annos_and_ends_ras, axis=0) ** 2, axis=1))
        ]
    )
    channel_locations_ras = np.zeros((depths.shape[0], 3))
    for m in np.arange(3):
        channel_locations_ras[:, m] = np.interp(
            depths, distance, track_annos_and_ends_ras[:, m]
        )
    return channel_locations_ras


def get_brain_regions(
    xyz: NDArray,
    channels_positions: NDArray | None = None,
    brain_atlas: atlas.BrainAtlas | None = None,
) -> tuple:
    """
    Get brain regions for electrode channels along a probe trajectory.

    Given 3D coordinates of a picked track, computes the brain region
    for each electrode channel position along the probe.

    Parameters
    ----------
    xyz : NDArray
        Array of shape (n_points, 3) with 3D coordinates of the picked track.
        The deepest point is assumed to be the probe tip.
    channels_positions : NDArray, optional
        Array of shape (n_channels, 2) with [lateral, axial] positions of
        channels in micrometers. Defaults to Neuropixel 1.0 geometry.
    brain_atlas : atlas.BrainAtlas, optional
        Brain atlas instance. Defaults to AllenAtlas(25).

    Returns
    -------
    tuple
        (brain_regions, insertion) where:
        - brain_regions: dict-like object with region info for each channel,
          including 'xyz', 'lateral', 'axial' fields
        - insertion: atlas.Insertion object defining probe entry and tip

    Raises
    ------
    AssertionError
        If depths along the track are not strictly increasing after processing.
    """
    brain_atlas = brain_atlas or atlas.AllenAtlas(25)
    if channels_positions is None:
        geometry = trace_header(version=1)
        channels_positions = np.c_[geometry["x"], geometry["y"]]

    xyz = xyz[np.argsort(xyz[:, 2]), :]
    d = atlas.cart2sph(
        xyz[:, 0] - xyz[0, 0], xyz[:, 1] - xyz[0, 1], xyz[:, 2] - xyz[0, 2]
    )[0]
    indsort = np.argsort(d)
    xyz = xyz[indsort, :]
    d = d[indsort]
    iduplicates = np.where(np.diff(d) == 0)[0]
    xyz = np.delete(xyz, iduplicates, axis=0)
    d = np.delete(d, iduplicates, axis=0)

    assert np.all(np.diff(d) > 0), "Depths should be strictly increasing"

    # Get the probe insertion from the coordinates
    insertion = atlas.Insertion.from_track(xyz, brain_atlas)

    # Interpolate channel positions along the probe depth and get brain locations
    TIP_SIZE_UM = 200
    xyz_channels = interpolate_along_track(
        xyz, (channels_positions[:, 1] + TIP_SIZE_UM) / 1e6
    )

    # Get the brain regions
    brain_regions = brain_atlas.regions.get(brain_atlas.get_labels(xyz_channels))
    brain_regions["xyz"] = xyz_channels
    brain_regions["lateral"] = channels_positions[:, 0]
    brain_regions["axial"] = channels_positions[:, 1]
    assert np.unique([len(brain_regions[k]) for k in brain_regions]).size == 1

    return brain_regions, insertion
