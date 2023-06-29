"""Utilities for terra15."""

from typing import Optional

import numpy as np
from tables.exceptions import NoSuchNodeError

from dascore.constants import timeable_types
from dascore.core import Patch
from dascore.core.coords import get_coord
from dascore.core.schema import PatchFileSummary
from dascore.utils.misc import get_slice_from_monotonic
from dascore.utils.time import datetime_to_float, to_datetime64, to_timedelta64

# --- Getting format/version


def _get_terra15_version_str(hdf_fi) -> str:
    """
    Return the version string for terra15 file.
    """

    # define a few root attrs that act as a "fingerprint" for terra15 files
    expected_attrs = [
        "acoustic_bandwidth_end",
        "amplifier_incoming_current",
        "file_start_computer_time",
        "file_version",
    ]
    root_attrs = hdf_fi.root._v_attrs
    is_terra15 = all([hasattr(root_attrs, x) for x in expected_attrs])
    if not is_terra15:
        return ""
    return str(root_attrs.file_version)


# --- Getting File summaries


def _get_time_node(data_node):
    """
    Get the time node from data.

    This will prefer GPS time but gets posix time if it is missing.
    """
    try:
        time = data_node["gps_time"]
    except (NoSuchNodeError, IndexError):
        time = data_node["posix_time"]
    return time


def _get_scanned_time_info(data_node):
    """Get the min, max, len, and dt from time array."""
    time = _get_time_node(data_node)
    t_len = len(time)
    # first try fast path by tacking first/last of time
    tmin, tmax = time[0], time[-1]
    # This doesn't work if an incomplete datablock exists at the end of
    # the file. In this case we need to read/filter time array (slower).
    if tmin > tmax:
        time = time[:]
        time_filtered = time[time > 0]
        t_len = len(time_filtered)
        tmin, tmax = time_filtered[0], time_filtered[-1]
    # surprisingly, using gps time column, dt is much different than dt
    # reported in data attrs so we calculate it this way.
    dt = (tmax - tmin) / (t_len - 1)
    tmax = tmin + dt * (t_len - 1)
    return tmin, tmax, t_len, dt


def _get_extra_scan_attrs(self, file_version, path, data_node):
    """Get the extra attributes that go into summary information."""
    tmin, tmax, _, dt = _get_scanned_time_info(data_node)
    out = {
        "time_min": to_datetime64(tmin),
        "time_max": to_datetime64(tmax),
        "d_time": to_timedelta64(dt),
        "path": path,
        "file_format": self.name,
        "file_version": str(file_version),
    }
    return out


def _get_version_data_node(root):
    """Get the version, time, and data node from terra15 file."""
    version = str(root._v_attrs.file_version)
    if version == "4":
        data_type = root._v_attrs.data_product
        data_node = root[data_type]
    elif version in {"5", "6"}:
        data_node = root["data_product"]
    else:
        raise NotImplementedError("Unknown Terra15 version")
    return version, data_node


def _scan_terra15(self, fi, path):
    """Scan a terra15 file, return metadata."""
    root = fi.root
    root_attrs = fi.root._v_attrs
    version, data_node = _get_version_data_node(root)
    out = _get_default_attrs(root_attrs)
    out.update(_get_extra_scan_attrs(self, version, path, data_node))
    return [PatchFileSummary.parse_obj(out)]


#
# --- Reading patch


def _get_start_stop(time_len, time_lims, file_tmin, dt):
    """Get the start/stop index along time axis."""
    # sst start index
    tmin = time_lims[0] or file_tmin
    tmax = time_lims[1] or dt * (time_len - 1) + file_tmin
    # Because float issues we need to round the ratio a bit. The result of
    # this is that if the ratio is within 5% of an int, that int is used.
    # Otherwise floor/ceil will snap to the appropriate int.
    tmin_rounded = np.round((tmin - file_tmin) / dt, 1)
    tmax_rounded = np.round((tmax - file_tmin) / dt, 1)
    # then use floor/ceil to get nearest value.
    start_ind = int(np.ceil(tmin_rounded))
    stop_ind = int(np.floor(tmax_rounded)) + 1
    # enforce upper limit on time end index.
    if stop_ind > time_len:
        stop_ind = time_len
    assert 0 <= start_ind < stop_ind
    return start_ind, stop_ind


def _get_dar_attrs(data_node, root, tar, dar):
    """Get the attributes for the terra15 data array (loaded)"""
    attrs = _get_default_attrs(root._v_attrs)
    attrs["time_min"] = tar.min()
    attrs["time_max"] = tar.max()
    attrs["distance_min"] = dar.min()
    attrs["distance_max"] = dar.max()
    return attrs


def _get_snapped_time_coord(file_start, start_ind, stop_ind, dt):
    """Get a snapped coordinate (user wants evenly sampled coord)"""
    t2 = file_start + dt * (stop_ind - start_ind - 1)
    start = to_datetime64(file_start)
    step = to_timedelta64(dt)
    stop = to_datetime64(t2)
    return get_coord(start=start, stop=stop + step, step=step)


def _get_raw_time_coord(data_node, start_ind, stop_ind):
    """Read the time from the data node and return it."""
    time = _get_time_node(data_node)[start_ind:stop_ind]
    return get_coord(values=to_datetime64(time))


def _read_terra15(
    root,
    time: Optional[tuple[timeable_types, timeable_types]] = None,
    distance: Optional[tuple[float, float]] = None,
    snap_dims: bool = True,
) -> Patch:
    """
    Read a terra15 file.

    Notes
    -----
    The time array is complicated. There is GPS time and Posix time included
    in the file. In version 0.0.6 and less of dascore we just used gps time.
    However, sometimes this results in subsequent samples having a time before
    the previous sample (time did not increase monotonically).

    So now, we use the first GPS sample, the last sample, and length
    to determine the dt (new in dascore>0.0.11).
    """
    # get time array
    time_lims = tuple(
        datetime_to_float(x) if x is not None else None
        for x in (time if time is not None else (None, None))
    )
    _, data_node = _get_version_data_node(root)
    file_t_min, file_t_max, time_len, dt = _get_scanned_time_info(data_node)
    # get the start and stop along the time axis
    start_ind, stop_ind = _get_start_stop(time_len, time_lims, file_t_min, dt)
    req_t_min = file_t_min if start_ind == 0 else file_t_min + dt * start_ind
    # account for files that might not be full, adjust requested max time
    stop_ind = min(stop_ind, time_len)
    assert stop_ind > start_ind
    req_t_max = time_lims[-1] if stop_ind < time_len else file_t_max
    assert req_t_max > req_t_min
    # get time coord
    if snap_dims:
        time_coord = _get_snapped_time_coord(file_t_min, start_ind, stop_ind, dt)
    else:
        time_coord = _get_raw_time_coord(data_node, start_ind, stop_ind)
    time_inds = (start_ind, stop_ind)
    # get data and sliced distance coord
    dist_ar = _get_distance_array(root)
    dslice = get_slice_from_monotonic(dist_ar, distance)
    dist_ar_trimmed = dist_ar[dslice]
    data = data_node.data[slice(*time_inds), dslice]
    coords = {"time": time_coord, "distance": dist_ar_trimmed}
    dims = ("time", "distance")
    attrs = _get_dar_attrs(data_node, root, time_coord, dist_ar_trimmed)
    return Patch(data=data, coords=coords, attrs=attrs, dims=dims)


def _get_default_attrs(root_node_attrs):
    """
    Return the required/default attributes which can be fetched from attributes.

    Note: missing time, distance absolute ranges. Downstream functions should handle
    this.
    """
    out = dict(dims="time, distance")
    _root_attrs = {
        "data_product": "data_type",
        "dx": "d_distance",
        "serial_number": "instrument_id",
        "sensing_range_start": "distance_min",
        "sensing_range_end": "distance_max",
        "data_product_units": "data_units",
    }
    for treble_name, out_name in _root_attrs.items():
        out[out_name] = getattr(root_node_attrs, treble_name)

    return out


def _get_distance_array(root):
    """Get the distance (along fiber) array."""
    # TODO: At least for the v4 test file, sensing_range_start, sensing_range_stop,
    # nx, and dx are not consistent, meaning d_min + dx * nx != d_max
    # so I just used this method. We need to look more into this.
    attrs = root._v_attrs
    dist = (np.arange(attrs.nx) * attrs.dx) + attrs.sensing_range_start
    return dist
