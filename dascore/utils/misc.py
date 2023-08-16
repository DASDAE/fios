"""Misc Utilities."""
from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import os
import warnings
from collections.abc import Iterable, Sequence
from collections.abc import Mapping
from types import ModuleType

import numpy as np
import pandas as pd
from scipy.linalg import solve
from scipy.special import factorial

from dascore.exceptions import MissingOptionalDependency


def register_func(list_or_dict: list | dict, key=None):
    """
    Decorator for registering a function name in a list or dict.

    If list_or_dict is a list only append the name of the function. If it is
    as dict append name (as key) and function as the value.

    Parameters
    ----------
    list_or_dict
        A list or dict to which the wrapped function will be added.
    key
        The name to use, if different than the name of the function.
    """

    def wrapper(func):
        name = key or func.__name__
        if hasattr(list_or_dict, "append"):
            list_or_dict.append(name)
        else:
            list_or_dict[name] = func
        return func

    return wrapper


def _pass_through_method(func):
    """Decorator for marking functions as methods on namedspace parent class."""

    @functools.wraps(func)
    def _func(self, *args, **kwargs):
        obj = self._obj
        return func(obj, *args, **kwargs)

    return _func


class _NameSpaceMeta(type):
    """Metaclass for namespace class."""

    def __setattr__(self, key, value):
        if callable(value):
            value = _pass_through_method(value)
        super().__setattr__(key, value)


@contextlib.contextmanager
def suppress_warnings(category=Warning):
    """
    Context manager for suppressing warnings.

    Parameters
    ----------
    category
        The types of warnings to suppress. Must be a subclass of Warning.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=category)
        yield
    return None


class MethodNameSpace(metaclass=_NameSpaceMeta):
    """A namespace for class methods."""

    def __init__(self, obj):
        self._obj = obj

    def __init_subclass__(cls, **kwargs):
        """Wrap all public methods."""
        for key, val in vars(cls).items():
            if callable(val):  # passes to _NameSpaceMeta settattr
                setattr(cls, key, val)


def get_slice_from_monotonic(array, cond: tuple | None) -> slice:
    """
    Return a slice object which meets conditions in cond on array.

    This is useful for determining how a particular dimension should be
    trimmed based on a coordinate (array) and an interval (cond).

    Parameters
    ----------
    array
        Any array with sorted values, but the array can have zeros
        at the end up to the sorted segment. Eg [1,2,3, 0, 0] works.
    cond
        An interval for which the array is to be indexed. End points are
        inclusive.

    Examples
    --------
    >>> import numpy as np
    >>> from dascore.utils.misc import get_slice_from_monotonic
    >>> ar = np.arange(100)
    >>> array_slice = get_slice_from_monotonic(ar, cond=(1, 10))
    """
    # TODO do we still need this or can we just use coordinates?
    if cond is None:
        return slice(None, None)
    assert len(cond) == 2, "you must pass a length 2 tuple to get_slice."
    start, stop = None, None
    if not pd.isnull(cond[0]):
        start = np.searchsorted(array, cond[0], side="left")
        start = start if start != 0 else None
    if not pd.isnull(cond[1]):
        stop = np.searchsorted(array, cond[1], side="right")
        stop = stop if stop != len(array) else None
    # check for and handle zeroed end values
    if array[-1] <= array[0]:
        increasing_segment_end = np.argmin(np.diff(array))
        out = get_slice_from_monotonic(array[:increasing_segment_end], cond)
        stop = np.min([out.stop or len(array), increasing_segment_end])
    return slice(start, stop)


def broadcast_for_index(
    n_dims: int,
    axis: int | Sequence[int],
    value: slice | int | None,
    fill=slice(None),
):
    """
    For a given shape of array, return empty slices except for slice axis.

    Parameters
    ----------
    n_dims
        The number of dimensions in the array that will be indexed.
    axis
        The axis number.
    value
        A slice object.
    fill
        The default values for non-axis entries.
    """
    axes = set(iterate(axis))
    return tuple(fill if x not in axes else value for x in range(n_dims))


def all_close(ar1, ar2):
    """
    Return True if ar1 is allcose to ar2.

    Just uses numpy.allclose unless ar1 is a datetime, in which case
    strict equality is used.
    """
    ar1, ar2 = np.array(ar1), np.array(ar2)
    is_date = np.issubdtype(ar1.dtype, np.datetime64)
    is_timedelta = np.issubdtype(ar1.dtype, np.timedelta64)
    if is_date or is_timedelta:
        return np.all(ar1 == ar2)
    else:
        return np.allclose(ar1, ar2)


def iter_files(
    paths: str | Iterable[str],
    ext: str | None = None,
    mtime: float | None = None,
    skip_hidden: bool = True,
) -> Iterable[str]:
    """
    Use os.scan dir to iter files, optionally only for those with given
    extension (ext) or modified times after mtime.

    Parameters
    ----------
    paths
        The path to the base directory to traverse. Can also use a collection
        of paths.
    ext : str or None
        The extensions to map.
    mtime : int or float
        Time stamp indicating the minimum mtime.
    skip_hidden : bool
        If True skip files or folders (they begin with a '.')

    Yields
    ------
    Paths, as strings, meeting requirements.
    """
    try:  # a single path was passed
        for entry in os.scandir(paths):
            if entry.is_file() and (ext is None or entry.name.endswith(ext)):
                if mtime is None or entry.stat().st_mtime >= mtime:
                    if entry.name[0] != "." or not skip_hidden:
                        yield entry.path
            elif entry.is_dir() and not (skip_hidden and entry.name[0] == "."):
                yield from iter_files(
                    entry.path, ext=ext, mtime=mtime, skip_hidden=skip_hidden
                )
    except TypeError:  # multiple paths were passed
        for path in paths:
            yield from iter_files(path, ext, mtime, skip_hidden)
    except NotADirectoryError:  # a file path was passed, just return it
        yield paths


def iterate(obj):
    """
    Return an iterable from any object.

    If a string, do not iterate characters, return str in tuple.

    *This is how iteration *should* work in python.
    """
    if obj is None:
        return ()
    if isinstance(obj, str):
        return (obj,)
    return obj if isinstance(obj, Iterable) else (obj,)


class CacheDescriptor:
    """A descriptor for storing infor in an instance cache (mapping)."""

    def __init__(self, cache_name, func_name, args=None, kwargs=None):
        self._cache_name = cache_name
        self._func_name = func_name
        self._args = () if args is None else args
        self._kwargs = {} if kwargs is None else kwargs

    def __set_name__(self, owner, name):
        """Method to set the name of the description on the instance."""
        self._name = name

    def __get__(self, instance, owner):
        """Get contents of the cache."""
        cache = getattr(instance, self._cache_name)
        if self._name not in cache:
            func = getattr(instance, self._func_name)
            out = func(*self._args, **self._kwargs)
            cache[self._name] = out
        return cache[self._name]

    def __set__(self, instance, value):
        """Set the cache contents."""
        cache = getattr(instance, self._cache_name)
        cache[self._name] = value


def optional_import(package_name: str) -> ModuleType:
    """
    Import a module and return the module object if installed, else raise error.

    Parameters
    ----------
    package_name
        The name of the package which may or may not be installed. Can
        also be sub-packages/modules (eg dascore.core).

    Raises
    ------
    MissingOptionalDependency if the package is not installed.

    Examples
    --------
    >>> from dascore.utils.misc import optional_import
    >>> from dascore.exceptions import MissingOptionalDependency
    >>> # import a module (this is the same as import dascore as dc)
    >>> dc = optional_import('dascore')
    >>> try:
    ...     optional_import('boblib5')  # doesn't exist so this raises
    ... except MissingOptionalDependency:
    ...     pass
    """
    try:
        mod = importlib.import_module(package_name)
    except ImportError:
        msg = (
            f"{package_name} is not installed but is required for the "
            f"requested functionality"
        )
        raise MissingOptionalDependency(msg)
    return mod


def get_middle_value(array):
    """Get the middle value in the differences array without changing dtype."""
    array = np.sort(np.array(array))
    last_ind = len(array) - 1
    ind = int(np.floor(last_ind / 2))
    return np.sort(array)[ind]


def all_diffs_close_enough(diffs):
    """Check if all the diffs are 'close' handling timedeltas."""
    if not len(diffs):
        return False
    diffs = np.array(diffs)
    is_dt = np.issubdtype(diffs.dtype, np.timedelta64)
    is_td = np.issubdtype(diffs.dtype, np.datetime64)
    if is_td or is_dt:
        diffs = diffs.astype(np.int64).astype(np.float64)
    med = np.median(diffs)
    # Note: The rtol parameter here is a bit arbitrary; it was set
    # based on experience but there is probably a better way to do this.
    return np.allclose(diffs, med, rtol=0.001)


def unbyte(byte_or_str: bytes | str) -> str:
    """Ensure a string is given by str or possibly bytes."""
    if isinstance(byte_or_str, bytes | np.bytes_):
        byte_or_str = byte_or_str.decode("utf8")
    return byte_or_str


def _get_stencil_weights(array, ref_point, order):
    """
    Computes the derivative stencil weights.

    Parameters
    ----------
        array
            An array representing the stencil domain.
        ref_point
            The point in the domain to base the stencil weights on.
        order
            The order of the derivative.

    Returns
    -------
        The vector of stencil weights.
    """
    ell = np.arange(len(array))
    assert order in ell, "Order must be in domain"
    A = (((array - ref_point)[:, np.newaxis] ** ell) / factorial(ell)).T
    weights = solve(A, ell == order)
    return weights.flatten()


def get_stencil_coefs(order, derivative=2):
    """Get centered coefficients for a derivative of specified order and derivative."""
    dx = np.arange(-order, order + 1)
    return _get_stencil_weights(dx, 0, derivative)


def get_parent_code_name(levels: int = 2) -> str:
    """Get the name of the calling function/class levels up in stack."""
    stack = inspect.currentframe()
    for _ in range(levels):
        stack = stack.f_back
    return stack.f_code.co_name


def to_str(val):
    """Convert value to string."""
    # This is primarily used to avoid lambdas which can cause issues
    # in pickling.
    return str(val)


def maybe_get_attrs(obj, attr_map: Mapping):
    """Maybe get attributes from object (if they exist)."""
    out = {}
    for old_name, new_name in attr_map.items():
        if hasattr(obj, old_name):
            value = getattr(obj, old_name)
            out[new_name] = unbyte(value)
    return out


def cached_method(func):
    """
    Cache decorated method.

    Simply uses the id of self for the key rather than hashing it.
    We can't use functools.cache due to pydantic #6787.
    """
    sentinel = object()  # unique object for cache misses.

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_cache"):
            self._cache = {}
        cache = self._cache
        if not (args or kwargs):
            key = id(func)
        else:
            key = (id(func), *args)
            if kwargs:
                for item in kwargs.items():
                    key += item
        out = cache.get(key, sentinel)
        if out is not sentinel:
            return out
        out = func(self, *args, **kwargs)
        cache[key] = out
        return out

    return wrapper
