"""
Shadow testing harness — the core verification strategy for rocketcsv.

Every test runs the same operation on both stdlib `csv` and `rocketcsv`,
then asserts identical behavior.
"""

import csv
import io

import pytest
import rocketcsv


# ---------------------------------------------------------------------------
# Shadow read
# ---------------------------------------------------------------------------


def shadow_read(input_text, **kwargs):
    """Run both readers on same input, return both results."""
    stdlib_rows = list(csv.reader(io.StringIO(input_text), **kwargs))
    fast_rows = list(rocketcsv.reader(io.StringIO(input_text), **kwargs))
    return stdlib_rows, fast_rows


def assert_shadow_read(input_text, **kwargs):
    """Assert both readers produce identical output."""
    stdlib_rows, fast_rows = shadow_read(input_text, **kwargs)
    assert stdlib_rows == fast_rows, (
        f"Reader mismatch!\n"
        f"  Input:  {input_text!r}\n"
        f"  Kwargs: {kwargs}\n"
        f"  stdlib: {stdlib_rows}\n"
        f"  rocket: {fast_rows}"
    )


# ---------------------------------------------------------------------------
# Shadow write
# ---------------------------------------------------------------------------


def shadow_write(rows, **kwargs):
    """Run both writers on same rows, return both outputs."""
    stdlib_out = io.StringIO()
    fast_out = io.StringIO()

    stdlib_w = csv.writer(stdlib_out, **kwargs)
    fast_w = rocketcsv.writer(fast_out, **kwargs)

    stdlib_w.writerows(rows)
    fast_w.writerows(rows)

    return stdlib_out.getvalue(), fast_out.getvalue()


def assert_shadow_write(rows, **kwargs):
    """Assert both writers produce identical output."""
    stdlib_text, fast_text = shadow_write(rows, **kwargs)
    assert stdlib_text == fast_text, (
        f"Writer mismatch!\n"
        f"  Rows:   {rows}\n"
        f"  Kwargs: {kwargs}\n"
        f"  stdlib: {stdlib_text!r}\n"
        f"  rocket: {fast_text!r}"
    )


# ---------------------------------------------------------------------------
# Shadow round-trip
# ---------------------------------------------------------------------------


def assert_shadow_roundtrip(rows, **kwargs):
    """Write with both, then read with both, assert all 4 combinations match."""
    stdlib_text, fast_text = shadow_write(rows, **kwargs)

    # reader doesn't take lineterminator
    read_kwargs = {k: v for k, v in kwargs.items() if k not in ("lineterminator",)}

    ss = list(csv.reader(io.StringIO(stdlib_text), **read_kwargs))
    sf = list(rocketcsv.reader(io.StringIO(stdlib_text), **read_kwargs))
    fs = list(csv.reader(io.StringIO(fast_text), **read_kwargs))
    ff = list(rocketcsv.reader(io.StringIO(fast_text), **read_kwargs))

    assert ss == sf == fs == ff, (
        f"Round-trip mismatch!\n"
        f"  stdlib→stdlib: {ss}\n"
        f"  stdlib→rocket: {sf}\n"
        f"  rocket→stdlib: {fs}\n"
        f"  rocket→rocket: {ff}"
    )


# ---------------------------------------------------------------------------
# Shadow error
# ---------------------------------------------------------------------------


def assert_shadow_error(input_text, **kwargs):
    """Assert both raise the same exception type."""
    stdlib_exc = None
    fast_exc = None

    try:
        list(csv.reader(io.StringIO(input_text), **kwargs))
    except Exception as e:
        stdlib_exc = type(e)

    try:
        list(rocketcsv.reader(io.StringIO(input_text), **kwargs))
    except Exception as e:
        fast_exc = type(e)

    assert stdlib_exc == fast_exc, (
        f"Error mismatch!\n"
        f"  Input:  {input_text!r}\n"
        f"  stdlib: {stdlib_exc}\n"
        f"  rocket: {fast_exc}"
    )


# ---------------------------------------------------------------------------
# Shadow DictReader
# ---------------------------------------------------------------------------


def shadow_dictread(input_text, **kwargs):
    """Run both DictReaders on same input, return both results."""
    stdlib_rows = list(csv.DictReader(io.StringIO(input_text), **kwargs))
    fast_rows = list(rocketcsv.DictReader(io.StringIO(input_text), **kwargs))
    return stdlib_rows, fast_rows


def assert_shadow_dictread(input_text, **kwargs):
    """Assert both DictReaders produce identical output."""
    stdlib_rows, fast_rows = shadow_dictread(input_text, **kwargs)
    assert stdlib_rows == fast_rows, (
        f"DictReader mismatch!\n"
        f"  Input:  {input_text!r}\n"
        f"  Kwargs: {kwargs}\n"
        f"  stdlib: {stdlib_rows}\n"
        f"  rocket: {fast_rows}"
    )


# ---------------------------------------------------------------------------
# Shadow DictWriter
# ---------------------------------------------------------------------------


def shadow_dictwrite(rows, fieldnames, **kwargs):
    """Run both DictWriters on same rows, return both outputs."""
    stdlib_out = io.StringIO()
    fast_out = io.StringIO()

    stdlib_w = csv.DictWriter(stdlib_out, fieldnames=fieldnames, **kwargs)
    fast_w = rocketcsv.DictWriter(fast_out, fieldnames=fieldnames, **kwargs)

    stdlib_w.writeheader()
    fast_w.writeheader()

    stdlib_w.writerows(rows)
    fast_w.writerows(rows)

    return stdlib_out.getvalue(), fast_out.getvalue()


def assert_shadow_dictwrite(rows, fieldnames, **kwargs):
    """Assert both DictWriters produce identical output."""
    stdlib_text, fast_text = shadow_dictwrite(rows, fieldnames, **kwargs)
    assert stdlib_text == fast_text, (
        f"DictWriter mismatch!\n"
        f"  Rows:       {rows}\n"
        f"  Fieldnames: {fieldnames}\n"
        f"  Kwargs:     {kwargs}\n"
        f"  stdlib:     {stdlib_text!r}\n"
        f"  rocket:     {fast_text!r}"
    )
