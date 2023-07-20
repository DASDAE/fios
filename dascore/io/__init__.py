"""
Modules for reading and writing fiber data.
"""
from dascore.io.core import FiberIO, read, scan, scan_to_df, write
from dascore.utils.io import BinaryReader, BinaryWriter, HDF5Reader, HDF5Writer
from dascore.utils.misc import MethodNameSpace


class PatchIO(MethodNameSpace):
    write = write
