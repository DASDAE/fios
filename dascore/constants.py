"""Constants used throughout obsplus."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import numpy as np
import pandas as pd

import dascore

PatchType = TypeVar("PatchType", bound="dascore.Patch")

SpoolType = TypeVar("SpoolType", bound="dascore.BaseSpool")


@runtime_checkable
class ExecutorType(Protocol):
    """Protocol for Executors that DASCore can use."""

    def map(self, func, iterables, **kwargs):
        """Map function for applying concurrency of some flavor."""


# Bump this to force re-downloading of all data file
DATA_VERSION = "0.0.0"

# Types dascore can convert into time representations
timeable_types = int | float | str | np.datetime64 | pd.Timestamp
opt_timeable_types = None | timeable_types

# Number types
numeric_types = int | float

# The smallest value an int64 can rep. (used as NaT by datetime64)
MININT64 = np.iinfo(np.int64).min

# The largest value an int64 can rep
MAXINT64 = np.iinfo(np.int64).max

# types used to represent paths
path_types = str | Path

# One second in numpy timedelta speak
ONE_SECOND = np.timedelta64(1, "s")

# One nanosecond
ONE_NANOSECOND = np.timedelta64(1, "ns")

# one billion
ONE_BILLION = 1_000_000_000

# One second with a precision of nano seconds
ONE_SECOND_IN_NS = np.timedelta64(ONE_BILLION, "ns")

# Float printing precision
FLOAT_PRECISION = 3

# Valid strings for "datatype" attribute
VALID_DATA_TYPES = (
    "",  # unspecified
    "velocity",
    "strain_rate",
    "phase",
    "strain",
    "temperature",
    "temperature_gradient",
)

# Valid categories (of instruments)
VALID_DATA_CATEGORIES = ("", "DAS", "DTS", "DSS")

max_lens = {
    "path": 120,
    "file_format": 15,
    "tag": 100,
    "network": 12,
    "station": 12,
    "dims": 40,
    "file_version": 9,
    "cable_id": 50,
    "instrument_id": 50,
    "data_type": 20,
    "data_category": 4,
}

# Methods FileFormatter needs to support
FILE_FORMATTER_METHODS = ("read", "write", "get_format", "scan")

# Large and small np.datetime64[ns] (used when defaults are needed)
SMALLDT64 = np.datetime64(MININT64 + 5_000_000_000, "ns")
LARGEDT64 = np.datetime64(MAXINT64 - 5_000_000_000, "ns")

# Required shared attributes to merge patches together
PATCH_MERGE_ATTRS = ("network", "station", "dims", "data_type", "data_category")

# A map from the unit name to the code used in numpy.timedelta64
NUMPY_TIME_UNIT_MAPPING = {
    "hour": "h",
    "minute": "m",
    "second": "s",
    "millisecond": "ms",
    "microsecond": "us",
    "nanosecond": "ns",
    "picosecond": "ps",
    "femtosecond": "fs",
    "attosecond": "as",
    "year": "Y",
    "month": "M",
    "week": "W",
    "day": "D",
}

# A description of basic patch metadata.
basic_summary_attrs = f"""
data_type
    The type of data collected (the meaning of the data). Valid values
    are {VALID_DATA_TYPES}.
data_category
    The category of instrument which recorded the data. Valid values
    are {VALID_DATA_CATEGORIES}.
data_units
    The units in which the data are recorded (e.g., strain_rate).
time_step
    The temporal sample spacing. If the patch is not evenly sampled
    this should be set to `np.timedelta64('NaT')`
time_min
    The time represented by the first sample in the patch.
time_max
    The time represented by the last sample in the patch.
time_units
    The units of the time axis (in most cases should be seconds) or
    specified by datetime64 arrays in time coordinate.
distance_step
    The spatial sampling rate, set to NaN if the patch is not evenly sampled
    in space.
distance_min
    The along-fiber distance of the first channel in the patch.
distance_max
    The along-fiber distance of the last channel in the patch.
d_distance
    The spatial sampling rate, set to NaN if the patch is not evenly sampled
    in space.
distance_units
    The units of the distance axis. In most cases should be 'm'.
instrument_id
    A unique identifier of the instrument.
cable_id
    A Unique identifier of the cable, or composition of cables.
distance_units
    The units of distance, defaults to m.
network
    The network code an ascii-compatible string up to 2 characters.
station
    The station code an ascii-compatible string up to 5 characters
instrument_id
    The identifier of the instrument.
dims
    A tuple of dimension names in the same order as the data dimensions.
tag
    A custom string up to 100 chars.
station
    A network code (up to 8 chars).
network
    A network code (up to 8 chars).
history
    A list of strings indicating what processing has occurred on the patch.
"""

# description of samples argument
samples_arg_description = """
If True, the values in kwargs and step represent samples along a
dimension. Must be integers. Otherwise, values are assumed to have
same units as the specified dimension, or have units attached.
"""

attr_conflict_description = """
Indicates how to handle conflicts in attributes other than those
indicated by dim (eg tag, history, station, etc). If "drop" simply
drop conflicting attributes, or attributes not shared by all models.
If "raise" raise an
[AttributeMergeError](`dascore.exceptions.AttributeMergeError`] when
issues are encountered. If "keep_first", just keep the first value
for each attribute.
"""


# Rich styles for various object displays.
dascore_styles = dict(
    np_array_threshold=100,  # max number of elements to show in array
    patch_history_array_threshold=10,  # max elements of array in hist str.
    dc_blue="#002868",
    dc_red="#cf0029",
    dc_yellow="#ffc934",
    default_coord="bold white",
    coord_range="bold green",
    coord_array="bold #cd0000",
    coord_monotonic="bold #d64806",
    coord_degenerate="bold #d40000",
    units="#cca3e1",
    dtypes="#a2bf48",
    keys="#a2bf48",
    # these are for formatting datetimes
    ymd="#e96baa",
    hms="#e96baa",
    dec="#e96baa",
)
