"""
A 2D trace object.
"""
from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd
from rich.text import Text

import dascore.proc
from dascore.compat import DataArray, array
from dascore.constants import PatchType
from dascore.core.schema import PatchAttrs
from dascore.io import PatchIO
from dascore.transform import TransformPatchNameSpace
from dascore.utils.coordmanager import CoordManager, get_coord_manager
from dascore.utils.coords import assign_coords
from dascore.utils.display import array_to_text, get_dascore_text
from dascore.utils.misc import optional_import
from dascore.utils.models import ArrayLike
from dascore.viz import VizPatchNameSpace


class Patch:
    """
    A Class for managing data and metadata.

    Parameters
    ----------
    data
        The data representing fiber optic measurements.
    coords
        The coordinates, or dimensional labels for the data. These can be
        passed in three forms:
        {coord_name: coord}
        {coord_name: ((dimensions,), coord)}
        {coord_name: (dimensions, coord)}
    dims
        A sequence of dimension strings. The first entry corresponds to the
        first axis of data, the second to the second dimension, and so on.
    attrs
        Optional attributes (non-coordinate metadata) passed as a dict or
        [PatchAttrs](`dascore.core.schema.PatchAttrs')

    Notes
    -----
    - If coordinates and dims are not provided, they will be extracted from
    attrs, if possible.

    - If coords and attrs are provided, attrs will have priority. This means
    if there is a conflict between information contained in both, the coords
    will be recalculated. However, any missing data in attrs will be filled in
    if available in coords.
    """

    data: ArrayLike
    coords: CoordManager
    dims: tuple[str, ...]
    attrs: Union[PatchAttrs, Mapping]

    def __init__(
        self,
        data: ArrayLike | DataArray | None = None,
        coords: Mapping[str, ArrayLike] | None = None,
        dims: Sequence[str] | None = None,
        attrs: Optional[Union[Mapping, PatchAttrs]] = None,
    ):
        if isinstance(data, (DataArray, self.__class__)):
            # dar = data if isinstance(data, DataArray) else data._data_array
            return
        # Try to generate coords from ranges in attrs
        if coords is None and attrs is not None:
            coords = PatchAttrs.coords_from_dims(attrs)
            dims = dims if dims is not None else attrs.dims
        # Ensure required info is here
        non_attrs = [x is None for x in [data, coords, dims]]
        if any(non_attrs) and not all(non_attrs):
            msg = "data, coords, and dims must be defined to init Patch."
            raise ValueError(msg)
        self._coords = get_coord_manager(coords, dims, attrs)
        self._attrs = PatchAttrs.from_dict(attrs, self.coords)
        self._data = array(self.coords.validate_data(data))

    def __eq__(self, other):
        """
        Compare one Trace2D to another.

        Parameters
        ----------
        other

        Returns
        -------

        """
        return self.equals(other)

    def __rich__(self):

        dascore_text = get_dascore_text()
        patch_text = Text("Patch", style="bold")
        header = Text.assemble(dascore_text, " ", patch_text)

        coords = self.coords.__rich__()

        data = array_to_text(self.data)

        attrs = Text(str(self.attrs))

        out = Text("\n").join([header, coords, data, attrs])
        return out

        pass

    def __str__(self):
        out = self.__rich__()
        return str(out)

    __repr__ = __str__

    def equals(self, other: PatchType, only_required_attrs=True) -> bool:
        """
        Determine if the current trace equals the other trace.

        Parameters
        ----------
        other
            A Trace2D object
        only_required_attrs
            If True, only compare required attributes. This helps avoid issues
            with comparing histories or custom attrs of patches, for example.
        """

        if only_required_attrs:
            attrs_to_compare = set(PatchAttrs.get_defaults()) - {"history"}
            attrs1 = {x: self.attrs.get(x, None) for x in attrs_to_compare}
            attrs2 = {x: other.attrs.get(x, None) for x in attrs_to_compare}
        else:
            attrs1, attrs2 = dict(self.attrs), dict(other.attrs)
        if set(attrs1) != set(attrs2):  # attrs don't have same keys; not equal
            return False
        if attrs1 != attrs2:
            # see if some values are NaNs, these should be counted equal
            not_equal = {
                x
                for x in attrs1
                if attrs1[x] != attrs2[x]
                and not (pd.isnull(attrs1[x]) and pd.isnull(attrs2[x]))
            }
            if not_equal:
                return False
        # check coords, names and values
        if not self.coords == other.coords:
            return False
        # handle transposed case; patches that are identical but transposed
        # should still be equal.
        if self.dims != other.dims and set(self.dims) == set(other.dims):
            other = other.transpose(*self.dims)
        return np.equal(self.data, other.data).all()

    def new(
        self: PatchType,
        data: None | ArrayLike = None,
        coords: None | dict[str | Sequence[str], ArrayLike] = None,
        dims: None | Sequence[str] = None,
        attrs: None | Mapping = None,
    ) -> PatchType:
        """
        Return a copy of the Patch with updated data, coords, dims, or attrs.

        Parameters
        ----------
        data
            An array-like containing data, an xarray DataArray object, or a Patch.
        coords
            The coordinates, or dimensional labels for the data. These can be
            passed in three forms:
            {coord_name: data}
            {coord_name: ((dimensions,), data)}
            {coord_name: (dimensions, data)}
        dims
            A sequence of dimension strings. The first entry cooresponds to the
            first axis of data, the second to the second dimension, and so on.
        attrs
            Optional attributes (non-coordinate metadata) passed as a dict.
        """
        data = data if data is not None else self.data
        attrs = attrs if attrs is not None else self.attrs
        coords = coords if coords is not None else self.coords
        if dims:
            coords = get_coord_manager(coords, dims, attrs)
            dim_map = {old: new for old, new in zip(self.dims, dims)}
            coords = coords.rename_dims(**dim_map)
        return self.__class__(data=data, coords=coords, attrs=attrs, dims=coords.dims)

    def update_attrs(self: PatchType, **attrs) -> PatchType:
        """
        Update attrs and return a new Patch.

        Parameters
        ----------
        **attrs
            attrs to add/update.
        """
        new_attrs = dict(self.attrs)
        new_attrs.update(attrs)
        new_coords = self.coords.update_from_attrs(attrs)
        out = dict(coords=new_coords, attrs=new_attrs, dims=self.dims)
        return self.__class__(self.data, **out)

    @property
    def coord_dims(self):
        """Return a dict of coordinate dimensions {coord_name: (**dims)}"""
        return self.coords.dim_map

    @property
    def dims(self) -> tuple[str, ...]:
        """Return the dimensions contained in patch."""
        return self.coords.dims

    @property
    def attrs(self) -> PatchAttrs:
        """Return the dimensions contained in patch."""
        return self._attrs

    @property
    def coords(self) -> CoordManager:
        """Return the dimensions contained in patch."""
        return self._coords

    @property
    def data(self) -> ArrayLike:
        """Return the dimensions contained in patch."""
        return self._data

    @property
    def shape(self) -> tuple[int, ...]:
        """Return the shape of the data array."""
        return self.coords.shape

    def to_xarray(self):
        """
        Return a data array with patch contents.
        """
        xr = optional_import("xarray")
        attrs = dict(self.attrs)
        dims = self.dims
        coords = self.coords._to_xarray_input()
        return xr.DataArray(self.data, attrs=attrs, dims=dims, coords=coords)

    squeeze = dascore.proc.squeeze
    rename = dascore.proc.rename
    transpose = dascore.proc.transpose

    # --- processing funcs

    select = dascore.proc.select
    decimate = dascore.proc.decimate
    detrend = dascore.proc.detrend
    pass_filter = dascore.proc.pass_filter
    sobel_filter = dascore.proc.sobel_filter
    median_filter = dascore.proc.median_filter
    aggregate = dascore.proc.aggregate
    abs = dascore.proc.abs
    resample = dascore.proc.resample
    iresample = dascore.proc.iresample
    interpolate = dascore.proc.interpolate
    normalize = dascore.proc.normalize
    standardize = dascore.proc.standardize
    taper = dascore.proc.taper

    # --- Method Namespaces
    # Note: these can't be cached_property (from functools) or references
    # to self stick around and keep large arrays in memory.

    @property
    def viz(self) -> VizPatchNameSpace:
        """The visualization namespace."""
        return VizPatchNameSpace(self)

    @property
    def tran(self) -> TransformPatchNameSpace:
        """The transformation namespace."""
        return TransformPatchNameSpace(self)

    @property
    def io(self) -> PatchIO:
        """Return a patch IO object for saving patches to various formats."""
        return PatchIO(self)

    def pipe(self, func: Callable[["Patch", ...], "Patch"], *args, **kwargs) -> "Patch":
        """
        Pipe the patch to a function.

        This is primarily useful for maintaining a chain of patch calls for
        a function.

        Parameters
        ----------
        func
            The function to pipe the patch. It must take a patch instance as
            the first argument followed by any number of positional or keyword
            arguments, then return a patch.
        *args
            Positional arguments that get passed to func.
        **kwargs
            Keyword arguments passed to func.
        """
        return func(self, *args, **kwargs)

    # Bind assign_coords as method
    assign_coords = assign_coords
