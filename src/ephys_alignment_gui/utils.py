"""Utility functions for data processing and visualization.

This module provides helper functions for histogram computation,
interpolation, and other numerical operations used throughout
the ephys alignment GUI.
"""

import numpy as np
from numpy.typing import NDArray
from pathlib import Path
import copy

class Bunch(dict):
    """A subclass of dictionary with an additional dot syntax."""

    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self

    def copy(self, deep=False):
        """Return a new Bunch instance which is a copy of the current Bunch instance.

        Parameters
        ----------
        deep : bool
            If True perform a deep copy (see notes). By default a shallow copy is returned.

        Returns
        -------
        Bunch
            A new copy of the Bunch.

        Notes
        -----
        - A shallow copy constructs a new Bunch object and then (to the extent possible) inserts
        references into it to the objects found in the original.
        - A deep copy constructs a new Bunch and then, recursively, inserts copies into it of the
         objects found in the original.
        """
        return copy.deepcopy(self) if deep else Bunch(super(Bunch, self).copy())

    def save(self, npz_file, compress=False):
        """
        Saves a npz file containing the arrays of the bunch.

        :param npz_file: output file
        :param compress: bool (False) use compression
        :return: None
        """
        if compress:
            np.savez_compressed(npz_file, **self)
        else:
            np.savez(npz_file, **self)

    @staticmethod
    def load(npz_file):
        """
        Loads a npz file containing the arrays of the bunch.

        :param npz_file: output file
        :return: Bunch
        """
        if not Path(npz_file).exists():
            raise FileNotFoundError(f'{npz_file}')
        return Bunch(np.load(npz_file))


def _fcn_extrap(x: NDArray, f, bounds: list | NDArray) -> NDArray:
    """
    Extrapolate a flat value before and after bounds.

    Parameters
    ----------
    x : NDArray
        Array to be filtered.
    f : callable
        Function to be applied between bounds.
    bounds : list or NDArray
        Two-element array defining the bounds [lower, upper].

    Returns
    -------
    NDArray
        Filtered array with flat extrapolation outside bounds.
    """
    y = f(x)
    y[x < bounds[0]] = f(bounds[0])
    y[x > bounds[1]] = f(bounds[1])
    return y


def fcn_cosine(bounds: list | NDArray):
    """
    Return a soft thresholding function with a cosine taper.

    Creates a function that applies cosine tapering between two bounds:
    - values <= bounds[0]: 0
    - bounds[0] < values < bounds[1]: cosine taper from 0 to 1
    - values >= bounds[1]: 1

    Parameters
    ----------
    bounds : list or NDArray
        Two-element array [lower, upper] defining the taper region.

    Returns
    -------
    callable
        Function that applies the cosine taper to input arrays.
    """

    def _cos(x):
        return (1 - np.cos((x - bounds[0]) / (bounds[1] - bounds[0]) * np.pi)) / 2

    func = lambda x: _fcn_extrap(x, _cos, bounds)  # noqa
    return func


def bincount2D(
    x: NDArray,
    y: NDArray,
    xbin: float | NDArray = 0,
    ybin: float | NDArray = 0,
    xlim: list | None = None,
    ylim: list | None = None,
    weights: NDArray | None = None,
) -> tuple[NDArray, NDArray, NDArray]:
    """
    Compute a 2D histogram by aggregating values in a 2D array.

    Parameters
    ----------
    x : NDArray
        Values to bin along the 2nd dimension (columns).
    y : NDArray
        Values to bin along the 1st dimension (rows).
    xbin : float or NDArray, optional
        If scalar > 0: bin size along 2nd dimension.
        If 0: aggregate according to unique values.
        If array: aggregate according to exact values (count reduce operation).
    ybin : float or NDArray, optional
        Same as xbin but for 1st dimension.
    xlim : list, optional
        Two values [min, max] that restrict range along 2nd dimension.
    ylim : list, optional
        Two values [min, max] that restrict range along 1st dimension.
    weights : NDArray, optional
        Weights to apply to each value for aggregation.

    Returns
    -------
    tuple[NDArray, NDArray, NDArray]
        (histogram, xscale, yscale) where:
        - histogram: 2D array of shape [ny, nx]
        - xscale: 1D array of x bin centers
        - yscale: 1D array of y bin centers
    """
    # if no bounds provided, use min/max of vectors
    if xlim is None:
        xlim = [np.min(x), np.max(x)]
    if ylim is None:
        ylim = [np.min(y), np.max(y)]

    def _get_scale_and_indices(v, bin, lim):
        # if bin is a nonzero scalar, this is a bin size: create scale and indices
        if np.isscalar(bin) and bin != 0:
            scale = np.arange(lim[0], lim[1] + bin / 2, bin)
            ind = (np.floor((v - lim[0]) / bin)).astype(np.int64)
        # if bin == 0, aggregate over unique values
        else:
            scale, ind = np.unique(v, return_inverse=True)
        return scale, ind

    xscale, xind = _get_scale_and_indices(x, xbin, xlim)
    yscale, yind = _get_scale_and_indices(y, ybin, ylim)
    # aggregate by using bincount on absolute indices for a 2d array
    nx, ny = [xscale.size, yscale.size]
    ind2d = np.ravel_multi_index(np.c_[yind, xind].transpose(), dims=(ny, nx))
    r = np.bincount(ind2d, minlength=nx * ny, weights=weights).reshape(ny, nx)

    # if a set of specific values is requested output an array matching the scale dimensions
    if not np.isscalar(xbin) and xbin.size > 1:
        _, iout, ir = np.intersect1d(xbin, xscale, return_indices=True)
        _r = r.copy()
        r = np.zeros((ny, xbin.size))
        r[:, iout] = _r[:, ir]
        xscale = xbin

    if not np.isscalar(ybin) and ybin.size > 1:
        _, iout, ir = np.intersect1d(ybin, yscale, return_indices=True)
        _r = r.copy()
        r = np.zeros((ybin.size, r.shape[1]))
        r[iout, :] = _r[ir, :]
        yscale = ybin

    return r, xscale, yscale
