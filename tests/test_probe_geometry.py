"""Unit tests for ephys_alignment_gui.core.probe_geometry module."""

import unittest

import numpy as np
from numpy.testing import assert_array_equal

from ephys_alignment_gui.core.probe_geometry import (
    TIP_SIZE_UM,
    NC,
    xy2rc,
    rc2xy,
    trace_header,
    dense_layout,
    adc_shifts,
)


class TestConstants(unittest.TestCase):
    """Tests for module constants."""

    def test_tip_size_constant(self):
        """TIP_SIZE_UM should be 200."""
        self.assertEqual(TIP_SIZE_UM, 200)

    def test_nc_constant(self):
        """NC (number of channels) should be 384."""
        self.assertEqual(NC, 384)


class TestXy2Rc(unittest.TestCase):
    """Tests for xy2rc coordinate conversion."""

    def test_np1_origin(self):
        """NP1 origin point conversion."""
        result = xy2rc(11, 20, version=1)
        self.assertEqual(result["col"], 0)
        self.assertEqual(result["row"], 0)

    def test_np1_known_point(self):
        """NP1 known coordinate conversion."""
        # x = 11 + 16 * col, y = 20 + 20 * row
        # x = 27, y = 40 -> col = 1, row = 1
        result = xy2rc(27, 40, version=1)
        self.assertEqual(result["col"], 1)
        self.assertEqual(result["row"], 1)

    def test_np2_origin(self):
        """NP2 origin point conversion."""
        result = xy2rc(0, 0, version=2)
        self.assertEqual(result["col"], 0)
        self.assertEqual(result["row"], 0)

    def test_np2_known_point(self):
        """NP2 known coordinate conversion."""
        # x = 32 * col, y = 15 * row
        # x = 32, y = 15 -> col = 1, row = 1
        result = xy2rc(32, 15, version=2)
        self.assertEqual(result["col"], 1)
        self.assertEqual(result["row"], 1)


class TestRc2Xy(unittest.TestCase):
    """Tests for rc2xy coordinate conversion."""

    def test_np1_origin(self):
        """NP1 origin row/col to um."""
        result = rc2xy(0, 0, version=1)
        self.assertEqual(result["x"], 11)
        self.assertEqual(result["y"], 20)

    def test_np1_round_trip(self):
        """NP1 xy -> rc -> xy should be identity."""
        x_orig, y_orig = 27, 60
        rc = xy2rc(x_orig, y_orig, version=1)
        xy = rc2xy(rc["row"], rc["col"], version=1)
        self.assertAlmostEqual(xy["x"], x_orig)
        self.assertAlmostEqual(xy["y"], y_orig)

    def test_np2_origin(self):
        """NP2 origin row/col to um."""
        result = rc2xy(0, 0, version=2)
        self.assertEqual(result["x"], 0)
        self.assertEqual(result["y"], 0)

    def test_np2_round_trip(self):
        """NP2 xy -> rc -> xy should be identity."""
        x_orig, y_orig = 64, 30
        rc = xy2rc(x_orig, y_orig, version=2)
        xy = rc2xy(rc["row"], rc["col"], version=2)
        self.assertAlmostEqual(xy["x"], x_orig)
        self.assertAlmostEqual(xy["y"], y_orig)


class TestDenseLayout(unittest.TestCase):
    """Tests for dense_layout function."""

    def test_np1_has_384_channels(self):
        """NP1 should have 384 channels."""
        layout = dense_layout(version=1)
        self.assertEqual(len(layout["ind"]), 384)
        self.assertEqual(len(layout["row"]), 384)
        self.assertEqual(len(layout["col"]), 384)
        self.assertEqual(len(layout["x"]), 384)
        self.assertEqual(len(layout["y"]), 384)

    def test_np1_has_4_columns(self):
        """NP1 dense layout should have 4 columns."""
        layout = dense_layout(version=1)
        unique_cols = np.unique(layout["col"])
        assert_array_equal(sorted(unique_cols), [0, 1, 2, 3])

    def test_np2_single_shank_has_2_columns(self):
        """NP2 single shank should have 2 columns."""
        layout = dense_layout(version=2, nshank=1)
        unique_cols = np.unique(layout["col"])
        assert_array_equal(sorted(unique_cols), [0, 1])

    def test_np2_4shank_has_4_shanks(self):
        """NP2 4-shank should have 4 distinct shank values."""
        layout = dense_layout(version=2, nshank=4)
        unique_shanks = np.unique(layout["shank"])
        assert_array_equal(sorted(unique_shanks), [0, 1, 2, 3])

    def test_indices_are_sequential(self):
        """Channel indices should be 0 to NC-1."""
        layout = dense_layout(version=1)
        assert_array_equal(layout["ind"], np.arange(384))


class TestTraceHeader(unittest.TestCase):
    """Tests for trace_header function."""

    def test_includes_adc_shifts(self):
        """trace_header should include sample_shift and adc keys."""
        h = trace_header(version=1)
        self.assertIn("sample_shift", h)
        self.assertIn("adc", h)

    def test_inherits_dense_layout(self):
        """trace_header should include all dense_layout keys."""
        h = trace_header(version=1)
        for key in ["ind", "row", "col", "x", "y", "shank"]:
            self.assertIn(key, h)


class TestAdcShifts(unittest.TestCase):
    """Tests for adc_shifts function."""

    def test_np1_returns_correct_length(self):
        """NP1 should return 384-length arrays."""
        sample_shift, adc = adc_shifts(version=1)
        self.assertEqual(len(sample_shift), 384)
        self.assertEqual(len(adc), 384)

    def test_np1_custom_nc(self):
        """Custom channel count should be respected."""
        sample_shift, adc = adc_shifts(version=1, nc=100)
        self.assertEqual(len(sample_shift), 100)
        self.assertEqual(len(adc), 100)

    def test_np2_returns_correct_length(self):
        """NP2 should return 384-length arrays."""
        sample_shift, adc = adc_shifts(version=2)
        self.assertEqual(len(sample_shift), 384)
        self.assertEqual(len(adc), 384)

    def test_sample_shifts_in_range(self):
        """Sample shifts should be in [0, 1)."""
        sample_shift, _ = adc_shifts(version=1)
        self.assertTrue(np.all(sample_shift >= 0))
        self.assertTrue(np.all(sample_shift < 1))

    def test_np1_has_32_adcs(self):
        """NP1 uses 32 ADCs."""
        _, adc = adc_shifts(version=1)
        # Each ADC samples 12 channels, 32 ADCs total
        self.assertEqual(len(np.unique(adc)), 32)

    def test_np2_has_24_adcs(self):
        """NP2 uses 24 ADCs."""
        _, adc = adc_shifts(version=2)
        # Each ADC samples 16 channels, 24 ADCs total
        self.assertEqual(len(np.unique(adc)), 24)


if __name__ == "__main__":
    unittest.main()
