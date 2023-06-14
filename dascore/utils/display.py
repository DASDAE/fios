"""
Utils for displaying dascore objects.
"""
import textwrap
from functools import singledispatch

import numpy as np
import pandas as pd
from rich.style import Style
from rich.text import Text

import dascore as dc
from dascore.constants import DC_BLUE, DC_RED, DC_YELLOW


@singledispatch
def get_nice_string(value):
    """
    Get a string for formatting nice display for various datatypes.
    """
    return str(value)


@get_nice_string.register(float)
@get_nice_string.register(np.float_)
def _nice_float_string(value):
    """Nice print value for floats."""
    return f"{float(value):.7}"


@get_nice_string.register(np.timedelta64)
@get_nice_string.register(pd.Timedelta)
def _nice_timedelta(value):
    """Get a nice timedelta value."""
    sec = dc.to_timedelta64(value) / np.timedelta64(1, "s")
    return f"{sec:.9}s"


@get_nice_string.register(np.datetime64)
@get_nice_string.register(pd.Timestamp)
def _nice_datetime(value):
    """Get a nice timedelta value."""
    empty = str(dc.to_datetime64(0))
    out = str(dc.to_datetime64(value))
    # strip off YEAR-MONTH-DAY if they aren't used.
    if empty.split("T")[0] == out.split("T")[0]:
        out = out.split("T")[1]
    out = out.rstrip("0").rstrip(".")  # strip trailing 0s.
    return out


def get_dascore_text():
    """Get stylized dascore text."""
    das_style = Style(color=DC_BLUE, bold=True)
    c_style = Style(color=DC_RED, bold=True)
    ore_style = Style(color=DC_YELLOW, bold=True)
    das = Text("DAS", style=das_style)
    c = Text("C", style=c_style)
    ore = Text("ore", style=ore_style)
    return Text.assemble(das, c, ore)


def array_to_text(data) -> Text:
    """Convert a coordinate to string."""
    header = Text("➤ ") + Text("Data", style=DC_RED) + Text(f" ({data.dtype})")
    numpy_format = textwrap.indent(str(data), "   ")
    return header + Text("\n") + Text(numpy_format)
