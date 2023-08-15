"""Utilities for terra15."""
from __future__ import annotations

import numpy as np

import dascore as dc
from dascore.core.attrs import PatchAttrs
from dascore.core.coordmanager import get_coord_manager
from dascore.core.coords import get_coord

# --- Getting format/version


def _get_prodml_version_str(hdf_fi) -> str:
    """Return the version string for prodml file."""
    # define a few root attrs that act as a "fingerprint" for terra15 files

    acquisition = getattr(hdf_fi.root, "Acquisition", None)
    if acquisition is None:
        return ""
    acq_attrs = acquisition._v_attrs
    expected_attrs = (
        "GaugeLength",
        "PulseRate",
        "PulseWidth",
        "NumberOfLoci",
        "schemaVersion",
        "uuid",
    )
    is_prodml = all([hasattr(acq_attrs, x) for x in expected_attrs])
    return str(acq_attrs.schemaVersion.decode()) if is_prodml else ""


def _get_raw_node_dict(acquisition_node):
    """Get a dict of {Raw[x]: node}."""
    out = {
        x._v_name: x
        for x in acquisition_node._f_iter_nodes()
        if x._v_name.startswith("Raw")
    }
    return dict(sorted(out.items()))


def _get_distance_coord(acq):
    """Get the distance ranges and spacing."""

    def get_distance_units(vattrs):
        """Get distance units, works for both v2 and v3."""
        name_v2_0 = "SpatialSamplingIntervalUnit"
        name_v2_1 = "SpatialSamplingInterval.uom"
        if hasattr(vattrs, name_v2_0):
            return getattr(vattrs, name_v2_0)
        if hasattr(vattrs, name_v2_1):
            return getattr(vattrs, name_v2_1)

    vattrs = acq._v_attrs
    step = vattrs.SpatialSamplingInterval
    num_dist_channels = vattrs.NumberOfLoci
    start = vattrs.StartLocusIndex * step
    stop = start + num_dist_channels * step
    units = get_distance_units(vattrs)
    return get_coord(start=start, stop=stop, units=units, step=step)


def _get_time_coord(node):
    """Get the time information from a Raw node."""
    time_attrs = node.RawDataTime._v_attrs
    start_str = time_attrs.PartStartTime.decode().split("+")[0]
    start = np.datetime64(start_str.rstrip("Z"))
    end_str = time_attrs.PartEndTime.decode().split("+")[0]
    end = np.datetime64(end_str.rstrip("Z"))
    step = (end - start) / (len(node.RawDataTime) - 1)
    return get_coord(start=start, stop=end + step, step=step, units="s")


def _get_data_unit_and_type(node):
    """Get the data type and units."""
    attrs = node._v_attrs
    out = dict(
        data_type=attrs.RawDescription.decode().lower().replace(" ", "_"),
        data_units=attrs.RawDataUnit.decode(),
    )
    return out


def _get_prodml_attrs(fi, extras=None, cls=PatchAttrs) -> list[PatchAttrs]:
    """Scan a prodML file, return metadata."""
    _root_attrs = {
        "PulseWidth": "pulse_width",
        "PulseWidthUnits": "pulse_width_units",
        "PulseWidth.uom": "pulse_width_units",
        "PulseRate": "pulse_rate",
        "PulseRateUnit": "pulse_rate_units",
        "PulseRate.uom": "pulse_rate_units",
        "GaugeLength": "gauge_length",
        "GaugeLengthUnit": "gauge_length_units",
        "GaugeLength.uom": "gauge_length_units",
        "schemaVersion": "schema_version",
    }
    base_info = {}
    acq = fi.root.Acquisition
    d_coord = _get_distance_coord(acq)
    base_info.update(d_coord.get_attrs_dict("distance"))
    raw_nodes = _get_raw_node_dict(acq)
    # Iterate each raw data node. I have only ever seen 1 in a file but since
    # it is indexed like Raw[0] there might be more.
    out = []
    for node in raw_nodes.values():
        info = dict(base_info)
        t_coord = _get_time_coord(node)
        info.update(t_coord.get_attrs_dict("time"))
        info.update(_get_data_unit_and_type(node))
        info["dims"] = ["time", "distance"]
        if extras is not None:
            info.update(extras)
        info["_time_coord"] = t_coord
        info["_distance_coord"] = d_coord
        out.append(cls(**info))
    return out


def _get_data_attr(attrs, node, time, distance):
    """Get a new attributes with adjusted time/distance and data array."""
    coords = {
        "distance": attrs["_distance_coord"],
        "time": attrs["_time_coord"],
    }
    cm = get_coord_manager(coords, dims=("time", "distance"))
    new_cm, data = cm.select(array=node.RawData, time=time, distance=distance)
    return data, new_cm


def _read_prodml(fi, distance=None, time=None, attr_cls=dc.PatchAttrs):
    """Read the prodml values into a patch."""
    attr_list = _get_prodml_attrs(fi, cls=attr_cls)
    nodes = list(_get_raw_node_dict(fi.root.Acquisition).values())
    out = []
    for attrs, node in zip(attr_list, nodes):
        data, coords = _get_data_attr(attrs, node, time, distance)
        dims = ("time", "distance")  # dims are fixed for this file format
        if data.size:
            out.append(dc.Patch(data=data, attrs=attrs, dims=dims, coords=coords))
    return out
