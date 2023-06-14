"""
Tests for coordinate object.
"""
import numpy as np
import pytest
import rich.text

import dascore as dc
from dascore.exceptions import CoordError
from dascore.utils.coords import (
    BaseCoord,
    CoordArray,
    CoordMonotonicArray,
    CoordRange,
    get_coord,
    get_coord_from_attrs,
)
from dascore.utils.misc import register_func
from dascore.utils.time import to_datetime64

COORDS = []


@pytest.fixture(scope="class")
@register_func(COORDS)
def evenly_sampled_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.arange(0, 100, 1)
    return get_coord(values=ar)


@pytest.fixture(scope="class")
@register_func(COORDS)
def evenly_sampled_float_coord_with_units():
    """Create coordinates which are evenly sampled and have units."""
    ar = np.arange(1, 100, 1 / 3)
    return get_coord(values=ar, units="m")


@pytest.fixture(scope="class")
@register_func(COORDS)
def evenly_sampled_date_coord():
    """Create coordinates which are evenly sampled."""
    ar = to_datetime64(np.arange(1, 100_000, 1_000))
    return get_coord(values=ar)


@pytest.fixture(scope="class")
@register_func(COORDS)
def monotonic_float_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.cumsum(np.abs(np.random.rand(100)))
    return get_coord(values=ar)


@pytest.fixture(scope="class")
@register_func(COORDS)
def reverse_monotonic_float_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.cumsum(np.abs(np.random.rand(100)))[::-1]
    return get_coord(values=ar)


@pytest.fixture(scope="class")
@register_func(COORDS)
def monotonic_datetime_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.cumsum(np.abs(np.random.rand(100) * 1_000))
    return get_coord(values=to_datetime64(ar))


@pytest.fixture(scope="class")
@register_func(COORDS)
def random_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.random.rand(100) * 1_000
    return get_coord(values=ar)


@pytest.fixture(scope="class")
@register_func(COORDS)
def random_date_coord():
    """Create coordinates which are evenly sampled."""
    ar = np.random.rand(100) * 1_000
    return get_coord(values=to_datetime64(ar))


@pytest.fixture(scope="class", params=COORDS)
def coord(request) -> BaseCoord:
    """Meta-fixture for returning all coords"""
    return request.getfixturevalue(request.param)


def assert_value_in_one_step(coord, index, value, greater=True):
    """Ensure value at index is within one step of value"""
    # reverse greater for reverse monotonic
    coord_value = coord.values[index]
    if greater:
        assert value <= coord_value
    else:
        assert value >= coord_value
    # next we ensure value is in the correct index. This is a little
    # bit complicated by reverse order coords.
    val1 = coord.values[index + 1]
    val2 = coord.values[index - 1]
    assert (val1 <= value <= val2) or (val2 <= value <= val1)


class TestBasics:
    """A suite of basic tests for coordinates."""

    def test_coord_init(self, coord):
        """simply run to insure all coords initialize."""
        assert isinstance(coord, BaseCoord)

    def test_bad_init(self):
        """Ensure no parameters raises error"""
        with pytest.raises(CoordError):
            get_coord()

    def test_value(self, coord):
        """All coords should return an array with the values attr."""
        ar = coord.values
        assert isinstance(ar, np.ndarray)

    def test_len_one_array(self):
        """Ensure one length array returns coord."""
        ar = np.array([10])
        coord = get_coord(values=ar)
        assert isinstance(coord, BaseCoord)
        assert len(coord) == 1

    def test_empty_array(self):
        """An empty array should also be a valid coordinate."""
        ar = np.array([])
        coord = get_coord(values=ar)
        assert isinstance(coord, BaseCoord)
        assert len(coord) == 0

    def test_coord_input(self, coord):
        """A coordinate should be valid input."""
        assert get_coord(values=coord) == coord

    def test_filter_inclusive(self, coord):
        """Ensure filtering is inclusive on both ends."""
        # These tests are only for coords with len > 7
        if len(coord) < 7:
            return
        values = np.sort(coord.values)
        value_set = set(values)
        assert len(values) > 7
        args = (values[3], values[-3])
        new, _ = coord.filter(args)
        # Check min and max values conform to args
        new_values = new.values
        new_min, new_max = np.min(new_values), np.max(new_values)
        assert (new_min >= args[0]) or np.isclose(new_min, args[0])
        assert (new_max <= args[1]) or np.isclose(new_max, args[1])
        # There can often be a bit of "slop" in float indices. We may
        # need to rethink this but this is good enough for now.
        if not np.issubdtype(new.dtype, np.float_):
            assert {values[3], values[-3]}.issubset(value_set)

    def test_filter_bounds(self, coord):
        """Ensure filtering bounds are honored."""
        # These tests are only for coords with len > 7
        if len(coord) < 7:
            return
        values = np.sort(coord.values)
        val1 = values[2] + (values[3] - values[2]) / 2
        val2 = values[-2] - (values[-2] - values[-3]) / 2
        new, _ = coord.filter((val1, val2))
        new_values = new.values
        new_min, new_max = np.min(new_values), np.max(new_values)
        assert (new_min >= val1) or np.isclose(new_min, val1)
        assert (new_max <= val2) or np.isclose(new_max, val2)
        if not np.issubdtype(new.dtype, np.float_):
            assert set(values).issuperset(set(new.values))

    def test_get_range(self, coord):
        """Basic tests for range of coords."""
        start = coord.min
        end = coord.max
        out = coord.get_query_range(start, end)
        assert out == (start, end)
        assert coord.get_query_range(start, None) == (start, None)
        assert coord.get_query_range(None, end) == (None, end)
        # if units aren't none, ensure they work.
        if not (unit := coord.units):
            return
        start_unit = start * unit
        end_unit = end * unit
        assert coord.get_query_range(start_unit, None) == (start, None)
        assert coord.get_query_range(start_unit, end_unit) == (start, end)
        assert coord.get_query_range(1 / end_unit, 1 / start_unit) == (start, end)
        # test inverse units

    def test_filter_ordered_coords(self, coord):
        """Basic filter tests all coords should pass."""
        if isinstance(coord, CoordArray):
            return
        assert len(coord.values) == len(coord)
        value1 = coord.values[10]
        new, sliced = coord.filter((value1, ...))
        assert_value_in_one_step(coord, sliced.start, value1, greater=True)
        assert new.values is not coord.values, "new data should be made"
        assert sliced.start == 10
        assert len(coord.values) == len(coord)
        # now test exact value
        value2 = coord.values[20]
        new, sliced = coord.filter((value2, ...))
        assert_value_in_one_step(coord, sliced.start, value2, greater=True)
        assert sliced.start == 20
        assert len(coord.values) == len(coord)
        # test end index
        new, sliced = coord.filter((..., value1))
        assert sliced.stop == 11
        new, sliced = coord.filter((..., value2))
        assert sliced.stop == 21
        assert len(coord.values) == len(coord)
        # test range
        new, sliced = coord.filter((value1, value2))
        assert len(new.values) == 11 == len(new)
        assert sliced == slice(10, 21)

    def test_cant_add_extra_fields(self, evenly_sampled_coord):
        """Ensure coordinates are immutable."""
        with pytest.raises(ValueError, match="has no field"):
            evenly_sampled_coord.bob = 1

    def test_immutable(self, evenly_sampled_coord):
        """Fields can't change once created."""
        with pytest.raises(TypeError, match="is immutable"):
            evenly_sampled_coord.start = 10

    def test_values_immutable(self, coord):
        """Values should all be immutable arrays."""
        with pytest.raises(ValueError, match="assignment destination is read-only"):
            coord.data[0] = coord.data[1]

    def test_str(self, coord):
        """All coords should be convertible to str."""
        out = str(coord)
        assert isinstance(out, str)

    def test_rich(self, coord):
        """Each coord should have nice rich printing."""
        out = coord.__rich__()
        assert isinstance(out, rich.text.Text)


class TestCoordRange:
    """Tests for coords from array."""

    def test_init_array(self, evenly_sampled_coord):
        """Ensure the array can be initialized."""
        assert evenly_sampled_coord.step == 1.0
        assert evenly_sampled_coord.units is None

    def test_values(self, evenly_sampled_coord):
        """Ensure we can get an array with values attribute."""
        vals = evenly_sampled_coord.values
        assert len(vals) == len(evenly_sampled_coord)

    def test_set_units(self, evenly_sampled_coord):
        """Ensure units can be set."""
        out = evenly_sampled_coord.set_units("m")
        assert out.units == dc.Unit("m")
        assert out is not evenly_sampled_coord

    def test_convert_units(self, evenly_sampled_coord):
        """Ensure units can be converted/set."""
        # if units are not set convert_units should set them.
        out_m = evenly_sampled_coord.convert_units("m")
        assert out_m.units == dc.Unit("m")
        out_mm = out_m.convert_units("mm")
        assert out_mm.units == dc.Unit("mm")
        assert len(out_mm) == len(out_m)
        assert np.allclose(out_mm.values / 1000, out_m.values)

    def test_dtype(self, evenly_sampled_coord, evenly_sampled_date_coord):
        """Ensure datatypes are sensible."""
        dtype1 = evenly_sampled_coord.dtype
        assert np.issubdtype(dtype1, np.int_)
        dtype2 = evenly_sampled_date_coord.dtype
        assert np.issubdtype(dtype2, np.datetime64)

    def test_select_tuple_ints(self, evenly_sampled_coord):
        """Ensure a tuple works as a limit."""
        assert evenly_sampled_coord.filter((50, None))[1] == slice(50, None)
        assert evenly_sampled_coord.filter((0, None))[1] == slice(None, None)
        assert evenly_sampled_coord.filter((-10, None))[1] == slice(None, None)
        assert evenly_sampled_coord.filter((None, None))[1] == slice(None, None)
        assert evenly_sampled_coord.filter((None, 1_000_000))[1] == slice(None, None)

    def test_identity_slice_ints(self, evenly_sampled_coord):
        """Ensure slice with exact start/end gives same coord."""
        coord = evenly_sampled_coord
        new, sliced = coord.filter((coord.start, coord.stop))
        assert new == coord

    def test_identity_slice_floats(self, evenly_sampled_float_coord_with_units):
        """Ensure slice with exact start/end gives same coord."""
        coord = evenly_sampled_float_coord_with_units
        new, sliced = coord.filter((coord.start, coord.stop))
        assert new == coord

    def test_float_basics(self):
        """Ensure floating point range coords work."""
        ar = np.arange(1, 100, 1 / 3)
        out = get_coord(values=ar, units="m")
        assert len(out) == len(ar)
        assert np.allclose(out.values, ar)

    def test_select_units(self, evenly_sampled_float_coord_with_units):
        """Ensure units can work in select."""
        coord = evenly_sampled_float_coord_with_units
        value_ft = 100
        value_m = value_ft * 0.3048
        new, sliced = coord.filter((value_ft * dc.Unit("ft"), ...))
        # ensure value is surrounded.
        assert new.start + new.step >= value_m
        assert new.start - new.step <= value_m
        # units should also not change
        assert new.units == coord.units

    def test_select_date_string(self, evenly_sampled_date_coord):
        """Ensure string selection works with datetime objects."""
        coord = evenly_sampled_date_coord
        date_str = "1970-01-01T12"
        new, sliced = coord.filter((date_str, ...))
        datetime = to_datetime64(date_str)
        assert new.start + new.step >= datetime
        assert new.start - new.step <= datetime

    def test_sort(self, evenly_sampled_coord):
        """Ensure sort returns equal coord"""
        out, _ = evenly_sampled_coord.sort()
        assert out == evenly_sampled_coord

    def test_update_limits_too_many_params(self, evenly_sampled_coord):
        """Update limits should raise if too many parameters are specified."""
        with pytest.raises(ValueError, match="At most two parameters"):
            evenly_sampled_coord.update_limits(1, 10, 1)

    def test_update_limits_start(self, evenly_sampled_coord):
        """Ensure start can be updated."""
        new_start = evenly_sampled_coord.start + 2 * evenly_sampled_coord.step
        new = evenly_sampled_coord.update_limits(start=new_start)
        assert len(new) == len(evenly_sampled_coord)
        assert new.step == evenly_sampled_coord.step
        assert new.start == new_start

    def test_update_limits_end(self, evenly_sampled_coord):
        """Ensure end can be updated."""
        new_stop = evenly_sampled_coord.start - 2 * evenly_sampled_coord.step
        step = evenly_sampled_coord.step
        new = evenly_sampled_coord.update_limits(stop=new_stop - step)
        assert len(new) == len(evenly_sampled_coord)
        assert new.step == evenly_sampled_coord.step
        assert new.stop == new_stop

    def test_update_limits_step(self, evenly_sampled_coord):
        """Ensure the step can be updated."""
        coord = evenly_sampled_coord
        new_step = coord.step * 2
        new = coord.update_limits(step=new_step)
        assert np.all(new.values == coord.values * 2)

    def test_update_limits_start_stop(self, evenly_sampled_coord):
        """Ensure both start/stop can be updated."""
        coord = evenly_sampled_coord
        start, stop = coord.values[2], coord.values[-2]
        new = coord.update_limits(start=start, stop=stop)
        assert len(new) == len(coord)
        assert new.start == start
        assert new.stop == stop

    def test_update_limits_no_args(self, evenly_sampled_coord):
        """Ensure both start/stop can be updated."""
        coords = evenly_sampled_coord
        assert coords == coords.update_limits()

    def test_test_filter_end_floats(self, evenly_sampled_float_coord_with_units):
        """Ensure we can filter right up to the end of the array."""
        coord = evenly_sampled_float_coord_with_units
        new_coord, out = coord.filter((coord.min, coord.max))
        assert len(new_coord) == len(coord)
        assert np.allclose(new_coord.values, coord.values)


class TestMonotonicCoord:
    """Tests for monotonic array coords."""

    def test_filter_basic(self, monotonic_float_coord):
        """Basic filter tests for monotonic array."""
        coord = monotonic_float_coord
        # test start only
        new, sliced = coord.filter((5, ...))
        assert_value_in_one_step(coord, sliced.start, 5)
        assert new.min >= 5
        # test stop only
        new, sliced = coord.filter((..., 40))
        assert_value_in_one_step(coord, sliced.stop, 40, greater=False)
        assert new.max <= 40

    def test_sort(self, monotonic_float_coord):
        """Ensure sort returns equal coord"""
        out, _ = monotonic_float_coord.sort()
        assert out == monotonic_float_coord

    def test_reverse_monotonic(self):
        """Ensure reverse monotonic values can be handled."""
        ar = np.cumsum(np.abs(np.random.rand(100)))[::-1]
        coord = get_coord(values=ar)
        assert np.allclose(coord.values, ar)
        new, sliced = coord.filter((ar[10], ar[20]))
        assert len(new) == 10 == len(new.values)
        assert np.allclose(new.values, coord.values[10:20])
        # test edges
        eps = 0.000000001
        new, sliced = coord.filter((ar[0] + eps, ar[20] - eps))
        assert sliced.start is None
        # ensure messing with the ends keeps the order
        val1, val2 = ar[10] - eps, ar[20] + eps
        new, sliced = coord.filter((val1, val2))
        assert sliced == slice(11, 19)
        assert new[0] <= val1
        assert new[-1] >= val2

    def test_index_with_string(self, monotonic_datetime_coord):
        """Ensure indexing works with date string."""
        coord = monotonic_datetime_coord
        value1 = coord.values[12] + np.timedelta64(1, "ns")
        new, sliced = coord.filter((value1, ...))
        assert_value_in_one_step(coord, sliced.start, value1, greater=True)
        assert sliced.start == 13
        # now test exact value
        value2 = coord.values[12]
        new, sliced = coord.filter((value2, ...))
        assert_value_in_one_step(coord, sliced.start, value2, greater=True)
        assert sliced.start == 12
        # test end index
        new, sliced = coord.filter((..., value1))
        assert sliced.stop == 12
        new, sliced = coord.filter((..., value2 - np.timedelta64(1, "ns")))
        assert sliced.stop == 11
        # test range
        new, sliced = coord.filter((coord.values[10], coord.values[20]))
        assert len(new) == 10
        assert slice(10, 20) == sliced

    def test_update_limits_too_many_params(self, monotonic_float_coord):
        """Update limits should raise if too many parameters are specified."""
        coords = monotonic_float_coord
        start, stop = coords.min + 1, coords.max - 1
        with pytest.raises(ValueError, match="At most one parameter"):
            coords.update_limits(start, stop)

    def test_update_limits_step(self, monotonic_float_coord):
        """Ensure step can be updated."""
        coord = monotonic_float_coord
        new = coord.update_limits(step=1.5)
        assert np.isclose(new.step, 1.5)
        assert new.min == coord.min

    def test_update_limits_end(self, monotonic_float_coord):
        """Ensure end can be updated."""
        coord = monotonic_float_coord
        new_stop = coord.max - 10
        new = coord.update_limits(stop=new_stop)
        assert len(new) == len(coord)
        assert new.max == new_stop

    def test_update_limits_start(self, monotonic_float_coord):
        """Ensure the start can be updated."""
        coord = monotonic_float_coord
        new_start = coord.min - 100
        new = coord.update_limits(start=new_start)
        assert len(new) == len(coord)
        assert np.isclose(new.min, new_start)

    def test_update_limits_no_args(self, monotonic_float_coord):
        """Ensure both start/stop can be updated."""
        coords = monotonic_float_coord
        assert coords == coords.update_limits()

    def test_getitem_slice(self, monotonic_float_coord):
        """Ensure get_item_slice returns another coord."""
        new = monotonic_float_coord[slice(1, -1)]
        assert isinstance(new, monotonic_float_coord.__class__)
        assert (len(new) + 2) == len(monotonic_float_coord)


class TestNonOrderedArrayCoords:
    """Tests for non-ordered array coords."""

    def test_filter(self, random_coord):
        """Ensure filtering returns an ndarray"""
        min_v, max_v = np.min(random_coord.values), np.max(random_coord.values)
        dist = max_v - min_v
        val1, val2 = min_v + 0.2 * dist, max_v - 0.2 * dist
        new, bool_array = random_coord.filter((val1, val2))
        assert np.all(new.values >= val1)
        assert np.all(new.values <= val2)
        assert bool_array.sum() == len(new)

    def test_sort(self, random_coord):
        """Ensure the coord can be ordered."""
        new, ordering = random_coord.sort()
        assert isinstance(new, CoordMonotonicArray)

    def test_snap(self, random_coord):
        """Ensure coords can be snapped to even sampling intervals."""
        out = random_coord.snap()
        assert isinstance(out, CoordRange)

    def test_snap_date(self, random_date_coord):
        """Ensure coords can be snapped to even sampling intervals."""
        out = random_date_coord.snap()
        assert np.issubdtype(out.dtype, np.datetime64)
        assert isinstance(out, CoordRange)


class TestCoordFromAttrs:
    """Tests for creating coordinates from attrs."""

    def test_missing_info_raises(self):
        """Ensure missing values raise CoordError."""
        attrs = dict(time_min=0, time_max=10)
        with pytest.raises(CoordError, match="Could not get coordinate"):
            get_coord_from_attrs(attrs, name="time")

    def test_int_coords(self):
        """Happy path for getting coords."""
        attrs = dict(time_min=0, time_max=10, d_time=1)
        coord = get_coord_from_attrs(attrs, name="time")
        assert isinstance(coord, BaseCoord)
        assert isinstance(coord, CoordRange)
        assert coord.start == 0
        assert coord.stop == 11
        assert coord.step == 1
        assert coord.values[0] == 0
        assert coord.values[-1] == 10

    def test_init_attr_with_units(self):
        """Ensure units are also set."""
        attrs = dict(time_min=0, time_max=10, d_time=1, time_units="s")
        coord = get_coord_from_attrs(attrs, name="time")
        assert coord.units == dc.Unit("s")


class TestTextOutput:
    """Tests for converting coordinate to nice textual outputs."""