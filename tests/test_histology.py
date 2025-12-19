"""Unit tests for ephys_alignment_gui.core.histology module."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from numpy.testing import assert_array_almost_equal

from ephys_alignment_gui.core.histology import (
    interpolate_along_track,
    load_track_csv,
    get_picked_tracks,
)


class TestInterpolateAlongTrack(unittest.TestCase):
    """Tests for interpolate_along_track function."""

    def test_straight_vertical_line(self):
        """Interpolation along a vertical line (z-axis only)."""
        # Track from z=0 to z=1 (1 meter, in RAS coordinates)
        track = np.array([
            [0, 0, 0],
            [0, 0, 0.5],
            [0, 0, 1.0],
        ])
        # Request positions at 0, 0.25, 0.5, 0.75, 1.0 meters from start
        depths = np.array([0, 0.25, 0.5, 0.75, 1.0])

        result = interpolate_along_track(track, depths)

        self.assertEqual(result.shape, (5, 3))
        # x and y should all be 0
        assert_array_almost_equal(result[:, 0], [0, 0, 0, 0, 0])
        assert_array_almost_equal(result[:, 1], [0, 0, 0, 0, 0])
        # z should match depths for this simple case
        assert_array_almost_equal(result[:, 2], depths)

    def test_diagonal_line(self):
        """Interpolation along a diagonal line."""
        # 45-degree diagonal in x-z plane
        track = np.array([
            [0, 0, 0],
            [1, 0, 1],
        ])
        # Distance from start: 0, sqrt(2)/2, sqrt(2)
        sqrt2 = np.sqrt(2)
        depths = np.array([0, sqrt2 / 2, sqrt2])

        result = interpolate_along_track(track, depths)

        self.assertEqual(result.shape, (3, 3))
        assert_array_almost_equal(result[:, 0], [0, 0.5, 1.0])
        assert_array_almost_equal(result[:, 1], [0, 0, 0])
        assert_array_almost_equal(result[:, 2], [0, 0.5, 1.0])

    def test_single_depth(self):
        """Single depth value."""
        track = np.array([
            [0, 0, 0],
            [0, 0, 1],
        ])
        depths = np.array([0.5])

        result = interpolate_along_track(track, depths)

        self.assertEqual(result.shape, (1, 3))
        assert_array_almost_equal(result[0], [0, 0, 0.5])

    def test_extrapolation_beyond_track(self):
        """Depths beyond track length should extrapolate."""
        track = np.array([
            [0, 0, 0],
            [0, 0, 1],
        ])
        # Request depth beyond track (1.5 > 1.0)
        depths = np.array([1.5])

        result = interpolate_along_track(track, depths)

        # np.interp extrapolates with edge values by default
        assert_array_almost_equal(result[0], [0, 0, 1.0])

    def test_negative_depths(self):
        """Negative depths (before start)."""
        track = np.array([
            [0, 0, 0],
            [0, 0, 1],
        ])
        depths = np.array([-0.5])

        result = interpolate_along_track(track, depths)

        # np.interp clamps to edge values
        assert_array_almost_equal(result[0], [0, 0, 0])

    def test_multi_segment_track(self):
        """Track with multiple segments."""
        # L-shaped track: vertical then horizontal
        track = np.array([
            [0, 0, 0],
            [0, 0, 1],  # 1 unit up
            [1, 0, 1],  # 1 unit right
        ])
        # Total length is 2 units
        depths = np.array([0, 0.5, 1.0, 1.5, 2.0])

        result = interpolate_along_track(track, depths)

        self.assertEqual(result.shape, (5, 3))
        # First half should be on vertical segment
        assert_array_almost_equal(result[0], [0, 0, 0])
        assert_array_almost_equal(result[1], [0, 0, 0.5])
        assert_array_almost_equal(result[2], [0, 0, 1.0])
        # Second half on horizontal segment
        assert_array_almost_equal(result[3], [0.5, 0, 1.0])
        assert_array_almost_equal(result[4], [1.0, 0, 1.0])


class TestLoadTrackCsv(unittest.TestCase):
    """Tests for load_track_csv function."""

    def test_empty_file(self):
        """Empty CSV file should return empty array."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('')  # Empty file
            f.flush()
            result = load_track_csv(f.name)

        self.assertEqual(result.size, 0)

    def test_path_object(self):
        """Should accept Path objects."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('')
            f.flush()
            # Pass Path object instead of string
            result = load_track_csv(Path(f.name))

        self.assertEqual(result.size, 0)


class TestGetPickedTracks(unittest.TestCase):
    """Tests for get_picked_tracks function."""

    def test_empty_directory(self):
        """Directory with no matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_picked_tracks(tmpdir)

        self.assertEqual(result['files'], [])
        self.assertEqual(result['xyz'], [])

    def test_single_file_path(self):
        """Direct file path instead of directory."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='_pts_transformed.csv', delete=False
        ) as f:
            f.write('')
            f.flush()
            result = get_picked_tracks(f.name)

        self.assertEqual(len(result['files']), 1)
        self.assertEqual(len(result['xyz']), 1)

    def test_custom_glob_pattern(self):
        """Custom glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with custom pattern
            custom_file = Path(tmpdir) / "track_custom.csv"
            custom_file.touch()

            # Default pattern shouldn't find it
            result1 = get_picked_tracks(tmpdir)
            self.assertEqual(len(result1['files']), 0)

            # Custom pattern should find it
            result2 = get_picked_tracks(tmpdir, glob_pattern="*_custom.csv")
            self.assertEqual(len(result2['files']), 1)


if __name__ == "__main__":
    unittest.main()
