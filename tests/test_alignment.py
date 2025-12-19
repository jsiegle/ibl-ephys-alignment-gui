"""Unit tests for ephys_alignment_gui.core.alignment module."""

import unittest

import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_equal

from ephys_alignment_gui.core.alignment import (
    EphysAlignment,
    _cumulative_distance,
)


class TestCumulativeDistance(unittest.TestCase):
    """Tests for _cumulative_distance helper function."""

    def test_single_point(self):
        """Single point should return [0]."""
        xyz = np.array([[0, 0, 0]])
        result = _cumulative_distance(xyz)
        assert_array_equal(result, [0])

    def test_two_points_unit_distance(self):
        """Two points 1 unit apart."""
        xyz = np.array([[0, 0, 0], [1, 0, 0]])
        result = _cumulative_distance(xyz)
        assert_array_almost_equal(result, [0, 1])

    def test_three_points_diagonal(self):
        """Three points along diagonal."""
        xyz = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]])
        expected_step = np.sqrt(3)
        expected = [0, expected_step, 2 * expected_step]
        result = _cumulative_distance(xyz)
        assert_array_almost_equal(result, expected)

    def test_vertical_line(self):
        """Points along vertical (z) axis."""
        xyz = np.array([[0, 0, 0], [0, 0, 1], [0, 0, 3]])
        result = _cumulative_distance(xyz)
        assert_array_almost_equal(result, [0, 1, 3])


class TestFeatureTrackConversions(unittest.TestCase):
    """Tests for static feature/track conversion methods."""

    def test_feature2track_identity(self):
        """When feature == track, output should equal input."""
        feature_ref = np.array([0, 1, 2])
        track_ref = np.array([0, 1, 2])
        feature_new = np.array([0.5, 1.5])
        result = EphysAlignment.feature2track(feature_new, feature_ref, track_ref)
        assert_array_almost_equal(result, feature_new)

    def test_feature2track_scaling(self):
        """Track space is 2x feature space."""
        feature_ref = np.array([0, 1])
        track_ref = np.array([0, 2])
        feature_new = np.array([0.5])
        result = EphysAlignment.feature2track(feature_new, feature_ref, track_ref)
        assert_array_almost_equal(result, [1.0])

    def test_track2feature_inverse(self):
        """track2feature should be inverse of feature2track."""
        feature_ref = np.array([0, 1, 2])
        track_ref = np.array([0, 2, 5])
        feature_new = np.array([0.5, 1.0, 1.5])

        track_new = EphysAlignment.feature2track(feature_new, feature_ref, track_ref)
        recovered = EphysAlignment.track2feature(track_new, feature_ref, track_ref)
        assert_array_almost_equal(recovered, feature_new)

    def test_feature2track_extrapolation(self):
        """Should extrapolate beyond reference points."""
        feature_ref = np.array([0, 1])
        track_ref = np.array([0, 2])
        feature_new = np.array([-1, 2])  # Outside [0, 1]
        result = EphysAlignment.feature2track(feature_new, feature_ref, track_ref)
        assert_array_almost_equal(result, [-2, 4])

    def test_feature2track_lin_insufficient_points(self):
        """With < 5 points, returns 0."""
        feature = np.array([0, 1, 2])  # Only 3 points
        track = np.array([0, 1, 2])
        trk = np.array([0.5])
        result = EphysAlignment.feature2track_lin(trk, feature, track)
        self.assertEqual(result, 0)

    def test_feature2track_lin_with_enough_points(self):
        """With >= 5 points, returns linear fit."""
        feature = np.array([0, 1, 2, 3, 4])
        track = np.array([0, 2, 4, 6, 8])  # 2x scaling
        trk = np.array([1.5])
        result = EphysAlignment.feature2track_lin(trk, feature, track)
        # Linear fit through middle points [1,2,3] -> [2,4,6] gives slope=2
        self.assertAlmostEqual(result[0], 3.0, places=5)


class TestAdjustExtremes(unittest.TestCase):
    """Tests for adjust_extremes_uniform method."""

    def test_adjust_extremes_uniform_no_change(self):
        """When feature == track, extremes should not change."""
        feature = np.array([0.0, 1.0, 2.0, 3.0])
        track = np.array([0.0, 1.0, 2.0, 3.0])
        result = EphysAlignment.adjust_extremes_uniform(feature.copy(), track.copy())
        assert_array_almost_equal(result, track)

    def test_adjust_extremes_uniform_with_offset(self):
        """Extremes adjusted when middle points differ."""
        feature = np.array([0.0, 1.0, 2.0, 3.0])
        track = np.array([0.0, 1.5, 2.5, 3.0])  # Middle shifted by 0.5
        result = EphysAlignment.adjust_extremes_uniform(feature.copy(), track.copy())
        # diff = [0.5, 0.5, -0.5] for feature - track differences
        # track[0] -= diff[0] = 0 - 0.5 = -0.5... actually let's compute correctly
        diff = np.diff(feature - track)  # [-0.5, 0, 0.5]
        expected_track = track.copy()
        expected_track[0] -= diff[0]
        expected_track[-1] += diff[-1]
        assert_array_almost_equal(result, expected_track)


class TestGetHistologyRegions(unittest.TestCase):
    """Tests for get_histology_regions static method."""

    def test_empty_coordinates_raises(self):
        """Empty coordinate array should raise ValueError."""
        from iblatlas.atlas import AllenAtlas

        ba = AllenAtlas(25)
        with self.assertRaises(ValueError) as ctx:
            EphysAlignment.get_histology_regions(np.array([]), np.array([]), ba)
        self.assertIn("Empty coordinate array", str(ctx.exception))

    def test_wrong_shape_raises(self):
        """Non-Nx3 array should raise ValueError."""
        from iblatlas.atlas import AllenAtlas

        ba = AllenAtlas(25)
        xyz = np.array([[0, 0], [1, 1]])  # Nx2 instead of Nx3
        depths = np.array([0, 1])
        with self.assertRaises(ValueError) as ctx:
            EphysAlignment.get_histology_regions(xyz, depths, ba)
        self.assertIn("Nx3", str(ctx.exception))

    def test_mismatched_lengths_raises(self):
        """Mismatched xyz and depth lengths should raise ValueError."""
        from iblatlas.atlas import AllenAtlas

        ba = AllenAtlas(25)
        xyz = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]])
        depths = np.array([0, 1])  # Only 2 depths for 3 coords
        with self.assertRaises(ValueError) as ctx:
            EphysAlignment.get_histology_regions(xyz, depths, ba)
        self.assertIn("same length", str(ctx.exception))

    def test_nan_coordinates_raises(self):
        """NaN in coordinates should raise ValueError."""
        from iblatlas.atlas import AllenAtlas

        ba = AllenAtlas(25)
        xyz = np.array([[0, 0, 0], [np.nan, 1, 1]])
        depths = np.array([0, 1])
        with self.assertRaises(ValueError) as ctx:
            EphysAlignment.get_histology_regions(xyz, depths, ba)
        self.assertIn("NaN", str(ctx.exception))

    def test_single_point_raises(self):
        """Single point should raise ValueError (need at least 2)."""
        from iblatlas.atlas import AllenAtlas

        ba = AllenAtlas(25)
        xyz = np.array([[0, 0, 0]])
        depths = np.array([0])
        with self.assertRaises(ValueError) as ctx:
            EphysAlignment.get_histology_regions(xyz, depths, ba)
        self.assertIn("at least 2", str(ctx.exception))


class TestArrangeIntoRegions(unittest.TestCase):
    """Tests for arrange_into_regions static method."""

    def test_single_region(self):
        """All points in same region."""
        depth_coords = np.array([0, 1, 2, 3])
        region_ids = np.array([1, 1, 1, 1])
        distance = np.array([10, 20, 30, 40])
        # Note: colours should NOT include '#' - the function adds it
        colours = ["FF0000", "FF0000", "FF0000", "FF0000"]

        x, y, col = EphysAlignment.arrange_into_regions(
            depth_coords, region_ids, distance, colours
        )

        self.assertEqual(len(x), 1)
        self.assertEqual(len(y), 1)
        self.assertEqual(len(col), 1)
        self.assertEqual(col[0], "#FF0000")

    def test_two_regions(self):
        """Two distinct regions."""
        depth_coords = np.array([0, 1, 2, 3])
        region_ids = np.array([1, 1, 2, 2])
        distance = np.array([10, 20, 30, 40])
        # Note: colours should NOT include '#' - the function adds it
        colours = ["FF0000", "FF0000", "00FF00", "00FF00"]

        x, y, col = EphysAlignment.arrange_into_regions(
            depth_coords, region_ids, distance, colours
        )

        self.assertEqual(len(x), 2)
        self.assertEqual(len(y), 2)
        self.assertEqual(col[0], "#FF0000")
        self.assertEqual(col[1], "#00FF00")

    def test_handles_non_string_colour(self):
        """Non-string colours should be replaced with white."""
        depth_coords = np.array([0, 1])
        region_ids = np.array([1, 1])
        distance = np.array([10, 20])
        colours = [None, None]  # Non-string

        x, y, col = EphysAlignment.arrange_into_regions(
            depth_coords, region_ids, distance, colours
        )

        self.assertEqual(col[0], "#FFFFFF")


class TestGetScaleFactor(unittest.TestCase):
    """Tests for get_scale_factor method."""

    def test_uniform_scaling(self):
        """All regions scaled by same factor."""
        # Create a minimal mock with region attribute
        # Note: region_orig is in METERS (the function multiplies by 1e6)
        class MockAlignment:
            region = np.array([[0, 1e-6], [1e-6, 2e-6], [2e-6, 3e-6]])  # meters

        mock = MockAlignment()

        # Scaled regions in micrometers (after 1e6 multiplication): 2x scaling
        # Original: [0, 1], [1, 2], [2, 3] um -> Scaled: [0, 2], [2, 4], [4, 6] um
        region = np.array([[0, 2], [2, 4], [4, 6]])  # micrometers

        scaled_region, scale_factor = EphysAlignment.get_scale_factor(mock, region)

        # All should have scale factor 2.0
        assert_array_almost_equal(scale_factor, [2.0])
        # Single scaled region spanning all
        self.assertEqual(scaled_region.shape[0], 1)

    def test_variable_scaling(self):
        """Different regions scaled by different factors."""
        # Note: region_orig is in METERS (the function multiplies by 1e6)
        class MockAlignment:
            region = np.array([[0, 1e-6], [1e-6, 2e-6]])  # meters

        mock = MockAlignment()

        # First region 2x, second region 3x (in micrometers)
        # Original: [0, 1], [1, 2] um -> Scaled: [0, 2], [2, 5] um
        region = np.array([[0, 2], [2, 5]])  # micrometers

        scaled_region, scale_factor = EphysAlignment.get_scale_factor(mock, region)

        self.assertEqual(len(scale_factor), 2)
        self.assertAlmostEqual(scale_factor[0], 2.0, places=2)
        self.assertAlmostEqual(scale_factor[1], 3.0, places=2)


if __name__ == "__main__":
    unittest.main()
