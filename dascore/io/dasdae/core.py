"""
Core module for reading and writing pickle format.
"""
import contextlib
from typing import Union

import dascore as dc
from dascore.constants import SpoolType
from dascore.io.core import FiberIO
from dascore.io.dasdae.utils import _read_patch, _save_patch, _write_meta
from dascore.utils.hdf5 import open_hdf5_file


class DASDAEV1(FiberIO):
    """
    Provides IO support for the DASDAE format version 1.

    DASDAE format is loosely based on the Adaptable Seismic Data Format (ASDF)
    which uses hdf5. The hdf5 structure is the following:

    /root
    /root.attrs
        __format__ = "DASDAE"
        __DASDAE_version__ = '1'  # version str
    /root/waveforms/
        DAS__{net}__{sta}__{tag}__{start}__{end}
            data   # patch data array
            data.attrs
            _coords_{coord_name}  # each coordinate array is saved here
        DAS__{net}__{sta}__{tag}__{start}__{end}.attrs
            _attrs_{attr_nme}  # each patch attribute
            _dims  # a str of 'dim1, dim2, dim3'
    """

    name = "DASDAE"
    preferred_extensions = ("h5", "hdf5")
    version = "1"

    def write(self, patch, path, **kwargs):
        """Read a Patch/Spool from disk."""
        with open_hdf5_file(path, mode="a") as h5:
            _write_meta(h5, self.version)
            # get an iterable of patches and save them
            patches = [patch] if isinstance(patch, dc.Patch) else patch
            waveforms = h5.create_group(h5.root, "waveforms")
            for patch in patches:
                _save_patch(patch, waveforms, h5)

    def get_format(self, path) -> Union[tuple[str, str], bool]:
        """Return the format from a dasdae file."""
        with open_hdf5_file(path, mode="r") as fi:
            is_dasdae, version = False, ""  # NOQA
            with contextlib.suppress(KeyError):
                is_dasdae = fi.root._v_attrs["__format__"] == "DASDAE"
                dasdae_file_version = fi.root._v_attrs["__DASDAE_version__"]
            if is_dasdae:
                return (self.name, dasdae_file_version)
            return False

    def read(self, path, **kwargs) -> SpoolType:
        """
        Read a dascore file.
        """
        patches = []
        with open_hdf5_file(path, mode="r") as fi:
            try:
                waveform_group = fi.root["/waveforms"]
            except KeyError:
                return dc.MemorySpool([])
            for patch_group in waveform_group:
                patches.append(_read_patch(patch_group, **kwargs))
        return dc.MemorySpool(patches)


class DASDAEV2(DASDAEV1):
    """
    Provides IO support for the DASDAE format version 2.

    DASDAE V2 adds a query table located at /root/waveforms/.index which
    allows large files to be scanned quickly and read operations planed.

    /root
    /root.attrs
        __format__ = "DASDAE"
        __DASDAE_version__ = '1'  # version str
    /root/waveforms/
        DAS__{net}__{sta}__{tag}__{start}__{end}
            data   # patch data array
            data.attrs
            _coords_{coord_name}  # each coordinate array is saved here
        DAS__{net}__{sta}__{tag}__{start}__{end}.attrs
            _attrs_{attr_nme}  # each patch attribute
            _dims  # a str of 'dim1, dim2, dim3'
    /root/waveforms/.index - Index table of waveform contents. The columns
    in the table are:
    {table_columns}
    """

    version = "2"

    def write(self, patch, path, **kwargs):
        """Read a Patch/Spool from disk."""
        with open_hdf5_file(path, mode="a") as h5:
            _write_meta(h5, self.version)
            # get an iterable of patches and save them
            patches = [patch] if isinstance(patch, dc.Patch) else patch
            waveforms = h5.create_group(h5.root, "waveforms")
            for patch in patches:
                _save_patch(patch, waveforms, h5)
