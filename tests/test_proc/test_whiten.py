"""Tests for signal whiten."""
import numpy as np
import pytest

from dascore import get_example_patch
from dascore.exceptions import ParameterError
from dascore.units import Hz


class TestWhiten:
    """Tests for the whiten module."""

    @pytest.fixture(scope="class")
    def test_patch(self):
        """Return a shot-record used for testing patch."""
        test_patch = get_example_patch("dispersion_event")
        return test_patch.resample(time=(200 * Hz))

    def test_whiten(self, test_patch):
        """Check consistency of test_dispersion module."""
        # assert velocity dimension
        whitened_patch = test_patch.whiten([10, 50], 5)
        assert "distance" in whitened_patch.dims
        # assert time dimension
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )

        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

    def test_default_whiten_no_input(self, test_patch):
        """Ensure whiten can run without any input."""
        whitened_patch = test_patch.whiten()
        assert "distance" in whitened_patch.dims
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )
        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

    def test_default_whiten_no_smoothing_window(self, test_patch):
        """Ensure whiten can run without smoothing window size."""
        whitened_patch = test_patch.whiten(freq_range=[5, 60])
        assert "distance" in whitened_patch.dims
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )
        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

    def test_default_whiten_no_freq_range(self, test_patch):
        """Ensure whiten can run without frequency range."""
        whitened_patch = test_patch.whiten(freq_smooth_size=10)
        assert "distance" in whitened_patch.dims
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )
        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

    def test_edge_whiten(self, test_patch):
        """Ensure whiten can run with edge cases frequency range."""
        whitened_patch = test_patch.whiten(freq_range=[0, 50], freq_smooth_size=10)
        assert "distance" in whitened_patch.dims
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )
        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

        whitened_patch = test_patch.whiten(freq_range=[50, 99], freq_smooth_size=10)
        assert "distance" in whitened_patch.dims
        assert "time" in whitened_patch.dims
        assert np.array_equal(
            test_patch.coords.get_array("time"), whitened_patch.coords.get_array("time")
        )
        assert np.array_equal(
            test_patch.coords.get_array("distance"),
            whitened_patch.coords.get_array("distance"),
        )

    def test_single_freq_range_raises(self, test_patch):
        """Ensure only one value for frequency range raises ParameterError."""
        msg = "Frequency range must include two values"
        freq_range = np.array([10])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=3)

    def test_freq_negative_raises(self, test_patch):
        """Ensure negative frequency values raise ParameterError."""
        msg = "Minimal and maximal frequencies have to be non-negative"
        freq_range = np.array([-10, 10])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=3)
        msg = "Frequency smoothing size must be positive"
        freq_range = np.array([10, 40])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=0)

    def test_freq_non_increasing_raises(self, test_patch):
        """Ensure that frequency range not increasing raises ParameterError."""
        msg = "Frequency range must be increasing"
        freq_range = np.array([30, 30])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=3)

    def test_freq_above_nyq_raises(self, test_patch):
        """Ensure frequency value above Nyquist raises ParameterError."""
        msg = "Frequency range exceeds Nyquist frequency"
        freq_range = np.array([10, 101])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=3)

    def test_short_windows_raises(self, test_patch):
        """Ensure too narrow frequency choices raise ParameterError."""
        msg = "Frequency range is too narrow"
        freq_range = np.array([10.02, 10.03])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=3)

        msg = "Frequency smoothing size is smaller than default frequency resolution"
        freq_range = np.array([10, 40])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=freq_range, freq_smooth_size=0.001)

    def test_longer_smooth_than_range_raises(self, test_patch):
        """Ensure smoothing window larger than
        frequency range raises ParameterError.
        """
        msg = "Frequency smoothing size is larger than frequency range"
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(freq_range=[10, 40], freq_smooth_size=40)

    def test_taper_param_raises(self, test_patch):
        """Ensures wrong Tukey alpha parameter raises Paremeter Error."""
        msg = "Tukey alpha needs to be between 0 and 1"
        freq_range = np.array([10, 50])
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(
                freq_range=freq_range, freq_smooth_size=3, tukey_alpha=-0.1
            )
        with pytest.raises(ParameterError, match=msg):
            test_patch.whiten(
                freq_range=freq_range, freq_smooth_size=3, tukey_alpha=1.3
            )
