"""
Base functionality for reading, writting, determining file formats, and scanning
Das Data.
"""
import os.path
from abc import ABC
from functools import cache
from pathlib import Path
from typing import List, Optional, Union

import pkg_resources

import dascore
from dascore.constants import PatchSummaryDict, StreamType, timeable_types
from dascore.exceptions import InvalidFileFormatter, UnknownFiberFormat
from dascore.utils.docs import compose_docstring

# ------------- Protocol for File Format support

_IO_INSTANCES = {}  # a dict of formatters
_LOADED_ENTRY_POINTS = {}  # entry points loaded for formatters


# load entry points (Maybe cache this somehow for faster startup?)
@cache
def load_fiber_io_from_plugins():
    """A function to load all the IO into memory."""
    for ep in pkg_resources.iter_entry_points(group="dascore.plugin.fiber_io"):
        _LOADED_ENTRY_POINTS[ep.name] = {ep.load()}


def _register_fiber_io(formatter):
    """Register a new formatter."""
    _IO_INSTANCES[formatter.name.upper()] = formatter


class FiberIO(ABC):
    """
    An interface which adds support for a given filer format.

    This class should be subclassed when adding support for new Patch/Spool
    formats.
    """

    name: str = ""
    preferred_extensions: tuple[str] = ()

    def read(self, path, **kwargs) -> StreamType:
        """
        Load data from a path.

        *kwargs should include support for selecting expected dimensions. For
        example, distance=(100, 200) would only read data which distance from
        100 to 200.
        """
        msg = f"FileFormatter: {self.name} has no read method"
        raise NotImplementedError(msg)

    def scan(self, path) -> List[PatchSummaryDict]:
        """
        Returns a list of summary info for patches contained in file.
        """
        # default scan method reads in the file and returns required attributes
        try:
            stream = self.read(path)
        except NotImplementedError:
            msg = f"FileFormatter: {self.name} has no scan method"
            raise NotImplementedError(msg)
        expected_keys = sorted(list(PatchSummaryDict.__annotations__))
        out = [{x: pa.attrs[x] for x in expected_keys} for pa in stream]
        return out

    def write(self, stream: StreamType, path: Union[str, Path]):
        """
        Write the file to disk
        """
        msg = f"FileFormatter: {self.name} has no write method"
        raise NotImplementedError(msg)

    def get_format(self, path) -> tuple[str, str]:
        """
        Return a tuple of (format_name, version_numbers).

        This only works if path is supported, otherwise raise UnknownFiberError
        or return False.
        """
        msg = f"FileFormatter: {self.name} has no get_version method"
        raise NotImplementedError(msg)

    def __init_subclass__(cls, **kwargs):
        """
        Hook for registering subclasses.
        """
        # check that the subclass is valid
        if not cls.name:
            msg = "You must specify the file format with the name field."
            raise InvalidFileFormatter(msg)
        # register formatter
        instance = cls()
        _register_fiber_io(instance)


def read(
    path: Union[str, Path],
    format: Optional[str] = None,
    version: Optional[str] = None,
    time: Optional[tuple[Optional[timeable_types], Optional[timeable_types]]] = None,
    distance: Optional[tuple[Optional[float], Optional[float]]] = None,
    **kwargs,
) -> StreamType:
    """
    Read a fiber file.

    Parameters
    ----------
    path
        A path to the file to read.
    format
        A string indicating the file format. If not provided dascore will
        try to estimate the format.
    version
        An optional string indicating the format version.
    time
        An optional tuple of time ranges.
    distance
        An optional tuple of distances.
    *kwargs
        All kwargs are passed to the format-specific read functions.
    """
    if format is None:
        format = get_format(path)[0].upper()
    formatter = _IO_INSTANCES[format.upper()]
    return formatter.read(path, version=version, time=time, distance=distance, **kwargs)


@compose_docstring(fields=list(PatchSummaryDict.__annotations__))
def scan_file(
    path: Union[Path, str],
    format: Optional[str] = None,
) -> List[PatchSummaryDict]:
    """
    Scan a file, return the summary dictionary.

    Parameters
    ----------
    path
        The path the to file to scan
    format
        Format of the file. If not provided DASCore will try to determine it.

    Notes
    -----
    The summary dictionaries contain the following fields:
        {fields}
    """
    # dispatch to file format handlers
    if format is None:
        format = get_format(path)[0]
    return _IO_INSTANCES[format].scan(path)


def get_format(path: Union[str, Path]) -> (str, str):
    """
    Return the name of the format contained in the file and version number.

    Parameters
    ----------
    path
        The path to the file.

    Returns
    -------
    A tuple of (file_format_name, version) both as strings.

    Raises
    ------
    dascore.exceptions.UnknownFiberFormat - Could not determine the fiber format.

    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} does not exist.")
    for name, formatter in _IO_INSTANCES.items():
        try:
            format = formatter.get_format(path)
        except Exception:  # NOQA
            continue
        if format:
            return format
    else:
        msg = f"Could not determine file format of {path}"
        raise UnknownFiberFormat(msg)


def write(patch_or_stream, path: Union[str, Path], format: str, **kwargs):
    """
    Write a Patch or Stream to disk.

    Parameters
    ----------
    path
        The path to the file.
    format
        The string indicating the format to write.

    Raises
    ------
    dascore.exceptions.UnknownFiberFormat - Could not determine the fiber format.

    """
    formatter = _IO_INSTANCES[format.upper()]
    if not isinstance(patch_or_stream, dascore.Stream):
        patch_or_stream = dascore.Stream([patch_or_stream])
    formatter.write(patch_or_stream, path, **kwargs)
