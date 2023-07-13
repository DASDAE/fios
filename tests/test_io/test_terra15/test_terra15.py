"""
Misc. tests for Terra15.
"""
import shutil

import numpy as np
import pandas as pd
import pytest
import tables

import dascore as dc


class TestTerra15:
    """Misc tests for Terra15."""

    @pytest.fixture(scope="class")
    def missing_gps_terra15_hdf5(self, terra15_v5_path, tmp_path_factory):
        """Creates a terra15 file with missing GPS Time."""
        new = tmp_path_factory.mktemp("missing_gps") / "missing.hdf5"
        shutil.copy(terra15_v5_path, new)
        with tables.open_file(new, "a") as fi:
            fi.root.data_product.gps_time._f_remove()
        return new

    def test_missing_gps_time(self, missing_gps_terra15_hdf5):
        """Tests for when GPS time isn't found."""
        patch = dc.read(missing_gps_terra15_hdf5)[0]
        assert isinstance(patch, dc.Patch)
        assert not np.any(pd.isnull(patch.coords["time"]))

    def test_time_slice(self, terra15_v6_path):
        """Ensure time slice within the file works."""
        info = dc.scan_to_df(terra15_v6_path).iloc[0]
        file_t1, file_t2 = info["time_min"], info["time_max"]
        dur = file_t2 - file_t1
        new_dur = dur / 4
        t1, t2 = file_t1 + new_dur, file_t1 + 2 * new_dur
        out = dc.read(terra15_v6_path, time=(t1, t2))[0]
        assert isinstance(out, dc.Patch)
        attrs = out.attrs
        assert attrs.time_min >= t1
        assert attrs.time_max <= t2

    def test_time_slice_no_snap(self, terra15_v6_path):
        """Ensure no snapping returns raw time."""
        info = dc.scan_to_df(terra15_v6_path).iloc[0]
        file_t1, file_t2 = info["time_min"], info["time_max"]
        dur = file_t2 - file_t1
        new_dur = dur / 4
        t1, t2 = file_t1 + new_dur, file_t1 + 2 * new_dur
        out = dc.read(terra15_v6_path, time=(t1, t2), snap_dims=False)[0]
        assert isinstance(out, dc.Patch)
        attrs = out.attrs
        assert attrs.time_min >= t1
        assert attrs.time_max <= t2

    def test_units(self, terra15_das_patch):
        """All units should be defined on terra15 patch."""
        patch = terra15_das_patch
        assert patch.attrs.data_units is not None
        assert patch.attrs.distance_units is not None
        assert patch.attrs.time_units is not None
        assert patch.get_coord("time").units == patch.attrs.time_units
        assert patch.get_coord("distance").units == patch.attrs.distance_units
