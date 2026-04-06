"""
rocketcsv — Rust-backed drop-in replacement for Python's csv module.

Usage:
    import rocketcsv as csv
"""

from sys import intern as _intern

from rocketcsv._rocketcsv import (
    reader as _reader_rust,
    reader_from_path,
    fast_reader,
    fast_reader_from_path,
    writer as _writer_rust,
    Error,
    QUOTE_MINIMAL,
    QUOTE_ALL,
    QUOTE_NONNUMERIC,
    QUOTE_NONE,
    QUOTE_STRINGS,
    QUOTE_NOTNULL,
)


__version__ = "0.1.0a1"


def _resolve_dialect(dialect, fmtparams):
    """Resolve a dialect name/class/instance + overrides into flat kwargs."""
    kwargs = {}
    if dialect is not None:
        if isinstance(dialect, str):
            if dialect not in _dialects:
                raise Error(f"unknown dialect: {dialect!r}")
            d = _dialects[dialect]()
        elif isinstance(dialect, type) and issubclass(dialect, Dialect):
            d = dialect()
        elif isinstance(dialect, Dialect):
            d = dialect
        else:
            raise Error("dialect must be a string or Dialect subclass")
        for attr in ("delimiter", "quotechar", "escapechar", "doublequote",
                      "skipinitialspace", "lineterminator", "quoting", "strict"):
            val = getattr(d, attr, None)
            if val is not None:
                kwargs[attr] = val
    kwargs.update(fmtparams)
    return kwargs


def _validate_params(kwargs):
    """Validate format parameters, matching stdlib csv error behavior."""
    d = kwargs.get("delimiter")
    if d is not None:
        if not isinstance(d, str):
            raise TypeError("delimiter must be a string, not %s" % type(d).__name__)
        if len(d) != 1:
            raise TypeError('"delimiter" must be a 1-character string')
    q = kwargs.get("quotechar")
    if q is not None:
        if not isinstance(q, str):
            raise TypeError("quotechar must be a string, not %s" % type(q).__name__)
        if len(q) != 1:
            raise TypeError('"quotechar" must be a 1-character string')
    e = kwargs.get("escapechar")
    if e is not None:
        if not isinstance(e, str):
            raise TypeError("escapechar must be a string, not %s" % type(e).__name__)
        if len(e) != 1:
            raise TypeError('"escapechar" must be a 1-character string')
    quoting = kwargs.get("quoting")
    if quoting is not None and quoting not in (QUOTE_MINIMAL, QUOTE_ALL, QUOTE_NONNUMERIC, QUOTE_NONE):
        raise TypeError("bad 'quoting' value")


def _make_dialect_obj(kwargs):
    """Build a Dialect instance reflecting the resolved parameters."""
    d = type("dialect", (Dialect,), {})()
    d.delimiter = kwargs.get("delimiter", ",")
    d.quotechar = kwargs.get("quotechar", '"')
    d.escapechar = kwargs.get("escapechar", None)
    d.doublequote = kwargs.get("doublequote", True)
    d.skipinitialspace = kwargs.get("skipinitialspace", False)
    d.lineterminator = kwargs.get("lineterminator", "\r\n")
    d.quoting = kwargs.get("quoting", QUOTE_MINIMAL)
    d.strict = kwargs.get("strict", False)
    return d


class _ReaderWrapper:
    """Thin wrapper adding dialect attribute to Rust reader."""
    __slots__ = ("_inner", "dialect")

    def __init__(self, inner, dialect_obj):
        self._inner = inner
        self.dialect = dialect_obj

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._inner)

    @property
    def line_num(self):
        return self._inner.line_num


class _WriterWrapper:
    """Thin wrapper adding dialect attribute to Rust writer."""
    __slots__ = ("_inner", "dialect")

    def __init__(self, inner, dialect_obj):
        self._inner = inner
        self.dialect = dialect_obj

    def writerow(self, row):
        return self._inner.writerow(row)

    def writerows(self, rows):
        return self._inner.writerows(rows)


def reader(csvfile, dialect=None, **fmtparams):
    """Drop-in replacement for csv.reader(). Supports dialect parameter."""
    kwargs = _resolve_dialect(dialect, fmtparams)
    _validate_params(kwargs)
    # Remove lineterminator — reader doesn't use it
    kwargs.pop("lineterminator", None)
    kwargs.pop("strict", None)  # TODO: implement strict mode properly
    r = _reader_rust(csvfile, **kwargs)
    return _ReaderWrapper(r, _make_dialect_obj(kwargs))


def writer(csvfile, dialect=None, **fmtparams):
    """Drop-in replacement for csv.writer(). Supports dialect parameter."""
    kwargs = _resolve_dialect(dialect, fmtparams)
    _validate_params(kwargs)
    # Remove strict — writer doesn't use it
    kwargs.pop("strict", None)
    w = _writer_rust(csvfile, **kwargs)
    return _WriterWrapper(w, _make_dialect_obj(kwargs))

# ---------------------------------------------------------------------------
# Dialect support (pure Python — not perf-critical)
# ---------------------------------------------------------------------------

_dialects = {}


class Dialect:
    """Describe a CSV dialect. Matches csv.Dialect interface."""

    _name = ""
    _valid = False
    delimiter = ","
    quotechar = '"'
    escapechar = None
    doublequote = True
    skipinitialspace = False
    lineterminator = "\r\n"
    quoting = QUOTE_MINIMAL
    strict = False


class excel(Dialect):
    """The default Excel-generated CSV dialect."""

    _name = "excel"
    delimiter = ","
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = "\r\n"
    quoting = QUOTE_MINIMAL


class excel_tab(Dialect):
    """Excel-generated TAB-delimited dialect."""

    _name = "excel-tab"
    delimiter = "\t"
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = "\r\n"
    quoting = QUOTE_MINIMAL


class unix_dialect(Dialect):
    """Unix-style CSV dialect (LF line endings, always quoted)."""

    _name = "unix"
    delimiter = ","
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = "\n"
    quoting = QUOTE_ALL


class Sniffer:
    """Stub Sniffer — not yet implemented."""
    def sniff(self, sample, delimiters=None):
        raise NotImplementedError("Sniffer not yet implemented in rocketcsv")
    def has_header(self, sample):
        raise NotImplementedError("Sniffer not yet implemented in rocketcsv")


# Register built-in dialects
_dialects["excel"] = excel
_dialects["excel-tab"] = excel_tab
_dialects["unix"] = unix_dialect


def register_dialect(name, dialect=None, **fmtparams):
    """Register a new CSV dialect."""
    if dialect is None:
        dialect = type(name, (Dialect,), fmtparams)
    else:
        if fmtparams:
            dialect = type(name, (dialect,), fmtparams)
    _dialects[name] = dialect


def unregister_dialect(name):
    """Remove a previously registered dialect."""
    if name not in _dialects:
        raise Error(f"unknown dialect: {name!r}")
    del _dialects[name]


def get_dialect(name):
    """Return the dialect instance associated with name."""
    if name not in _dialects:
        raise Error(f"unknown dialect: {name!r}")
    return _dialects[name]()


def list_dialects():
    """Return names of all registered dialects."""
    return list(_dialects.keys())


# ---------------------------------------------------------------------------
# field_size_limit (pure Python)
# ---------------------------------------------------------------------------

_field_size_limit = 131072  # stdlib default


def field_size_limit(new_limit=None):
    """Get/set the maximum field size allowed by the parser."""
    global _field_size_limit
    old = _field_size_limit
    if new_limit is not None:
        _field_size_limit = new_limit
    return old


# ---------------------------------------------------------------------------
# DictReader (pure Python wrapping rocketcsv.reader)
# ---------------------------------------------------------------------------

class DictReader:
    """CSV reader that maps rows to dicts. Drop-in for csv.DictReader."""

    def __init__(
        self,
        f,
        fieldnames=None,
        restkey=None,
        restval=None,
        dialect="excel",
        *args,
        **kwds,
    ):
        self._fieldnames = fieldnames
        self.restkey = restkey
        self.restval = restval
        self.reader = reader(f, *args, **kwds)
        self.dialect = dialect
        self.line_num = 0

    @property
    def fieldnames(self):
        if self._fieldnames is None:
            try:
                self._fieldnames = next(self.reader)
            except StopIteration:
                pass
        self.line_num = self.reader.line_num
        return self._fieldnames

    @fieldnames.setter
    def fieldnames(self, value):
        self._fieldnames = value

    def __iter__(self):
        return self

    def __next__(self):
        if self.line_num == 0:
            # Force fieldnames to be read and intern key strings once.
            self.fieldnames
            if self._fieldnames is not None:
                self._fieldnames = [
                    _intern(k) if isinstance(k, str) else k
                    for k in self._fieldnames
                ]
                self._len_fieldnames = len(self._fieldnames)
            else:
                self._len_fieldnames = 0
        row = next(self.reader)
        self.line_num = self.reader.line_num

        # Unlike the basic reader, DictReader skips empty rows
        while row == []:
            row = next(self.reader)

        d = dict(zip(self._fieldnames, row))
        lr = len(row)
        if lr < self._len_fieldnames:
            for key in self._fieldnames[lr:]:
                d[key] = self.restval
        elif lr > self._len_fieldnames:
            d[self.restkey] = row[self._len_fieldnames:]
        return d


# ---------------------------------------------------------------------------
# DictWriter (pure Python wrapping rocketcsv.writer)
# ---------------------------------------------------------------------------

class DictWriter:
    """CSV writer that maps dicts to rows. Drop-in for csv.DictWriter."""

    def __init__(
        self,
        f,
        fieldnames,
        restval="",
        extrasaction="raise",
        dialect="excel",
        *args,
        **kwds,
    ):
        self.fieldnames = fieldnames
        self.restval = restval
        self.extrasaction = extrasaction
        if extrasaction not in ("raise", "ignore"):
            raise ValueError("extrasaction (%s) must be 'raise' or 'ignore'" % extrasaction)
        self.writer = writer(f, *args, **kwds)

    def writeheader(self):
        return self.writer.writerow(self.fieldnames)

    def _dict_to_list(self, rowdict):
        if self.extrasaction == "raise":
            wrong_fields = rowdict.keys() - set(self.fieldnames)
            if wrong_fields:
                raise ValueError(
                    f"dict contains fields not in fieldnames: "
                    + ", ".join(repr(x) for x in sorted(wrong_fields))
                )
        return [rowdict.get(key, self.restval) for key in self.fieldnames]

    def writerow(self, rowdict):
        return self.writer.writerow(self._dict_to_list(rowdict))

    def writerows(self, rowdicts):
        for rowdict in rowdicts:
            self.writerow(rowdict)


# ---------------------------------------------------------------------------
# __all__ — matches stdlib csv.__all__
# ---------------------------------------------------------------------------

__all__ = [
    "QUOTE_MINIMAL",
    "QUOTE_ALL",
    "QUOTE_NONNUMERIC",
    "QUOTE_NONE",
    "QUOTE_STRINGS",
    "QUOTE_NOTNULL",
    "Error",
    "Dialect",
    "excel",
    "excel_tab",
    "unix_dialect",
    "DictReader",
    "DictWriter",
    "reader",
    "reader_from_path",
    "fast_reader",
    "fast_reader_from_path",
    "writer",
    "register_dialect",
    "unregister_dialect",
    "get_dialect",
    "list_dialects",
    "field_size_limit",
    "Sniffer",
    "__version__",
]
