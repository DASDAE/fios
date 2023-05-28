"""Pydantic schemas used by DASCore."""
from pathlib import Path
from typing import Literal, Optional, Mapping, Sequence, Union

import numpy as np

from pydantic import BaseModel, Field, validator
from typing_extensions import Self

import dascore as dc
from dascore.constants import (
    VALID_DATA_CATEGORIES,
    VALID_DATA_TYPES,
    basic_summary_attrs,
    max_lens,
)
from dascore.utils.docs import compose_docstring
from dascore.utils.models import DateTime64, TimeDelta64, UnitStr


@compose_docstring(basic_params=basic_summary_attrs)
class PatchAttrs(BaseModel):
    """
    The expected attributes for a Patch.

    Parameter
    ---------
    {basic_params}

    Notes
    -----
    These attributes go into the HDF5 index used by dascore. Therefore,
    when they are changed the index version needs to be incremented so
    previous indices are invalidated.
    """

    data_type: Literal[VALID_DATA_TYPES] = ""
    data_category: Literal[VALID_DATA_CATEGORIES] = ""
    data_units: Optional[UnitStr] = None
    time_min: DateTime64 = np.datetime64("NaT")
    time_max: DateTime64 = np.datetime64("NaT")
    d_time: TimeDelta64 = np.timedelta64("NaT")
    time_units: Optional[UnitStr] = None
    distance_min: float = np.NaN
    distance_max: float = np.NaN
    d_distance: float = np.NaN
    distance_units: Optional[UnitStr] = None
    instrument_id: str = Field("", max_length=max_lens["instrument_id"])
    cable_id: str = Field("", max_length=max_lens["cable_id"])
    dims: str = Field("", max_length=max_lens["dims"])
    tag: str = Field("", max_length=max_lens["tag"])
    station: str = Field("", max_length=max_lens["station"])
    network: str = Field("", max_length=max_lens["network"])
    history: Union[str, Sequence[str]] = Field(default_factory=list)

    # In order to maintain backward compatibility, these dunders make the
    # class also behave like a dict.

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __len__(self):
        return len(self.dict())

    def get(self, item, default=None):
        """dict-like get method."""
        try:
            return self[item]
        except (AttributeError, KeyError):
            return default

    def items(self):
        """Yield (attribute, values) just like dict.items()."""
        for item, value in self.dict().items():
            yield item, value

    @classmethod
    def get_defaults(cls):
        """return a dict of default values"""
        new = cls()
        return new.dict()

    def coords_from_dims(self) -> Mapping[str, np.ndarray]:
        """Return coordinates from dimensions assuming evenly sampled."""
        out = {}
        for dim in self.dim_tuple:
            # TODO replace this with simple coords
            start, stop = self[f"{dim}_min"], self[f"{dim}_max"]
            step = self[f"d_{dim}"]
            ar = np.arange(start, stop + step, step)
            # due to float imprecision the last value can be slightly larger
            # than stop, just trim
            if ar[-1] > stop:
                ar = ar[:-1]
            out[dim] = ar
        return out

    @classmethod
    def new(
        cls,
        args,
        coord_manager: Optional["dc.utils.coordmanager.CoordManager"] = None,
    ) -> Self:
        """
        Get a new instance of the PatchAttrs.

        Optionally, give preference to data contained in a
        [`CoordManager`](`dascore.utils.coordmanager.CoordManager`).

        """
        if isinstance(args, cls):
            return args
        out = dict(args)
        if coord_manager is None:
            return cls(**out)
        for name in coord_manager.dims:
            coord = coord_manager.coord_map[name]
            out[f"{name}_min"], out[f"{name}_max"] = coord.min, coord.max
            out[f"d_{name}"], out[f"{name}_units"] = coord.step, coord.units
        return cls(**out)

    class Config:
        """Configuration for Patch Summary"""

        title = "Patch Summary"
        extra = "allow"
        allow_mutation = False
        json_encoders = {
            np.datetime64: lambda x: str(x),
            np.timedelta64: lambda x: str(x),
        }

    @property
    def dim_tuple(self):
        """Return a tuple of dimensions. The dims attr is a string."""
        return tuple(self.dims.split(","))

    @validator("dims", pre=True)
    def _flatten_dims(cls, value):
        """Some dims are passed as a tuple; we just want str"""
        if not isinstance(value, str):
            value = ",".join(value)
        return value


class PatchFileSummary(PatchAttrs):
    """
    The expected minimum attributes for a Patch/spool file.
    """

    # These attributes are excluded from the HDF index.
    _excluded_index = ("data_units", "time_units", "distance_units", "history")

    file_version: str = ""
    file_format: str = ""
    path: Union[str, Path] = ""

    @classmethod
    def get_index_columns(cls) -> tuple[str, ...]:
        """Return the column names which should be used for indexing."""
        fields = set(cls.__fields__) - set(cls._excluded_index)
        return tuple(sorted(fields))
