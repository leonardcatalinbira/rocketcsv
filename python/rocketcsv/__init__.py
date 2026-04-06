"""
rocketcsv — Rust-backed drop-in replacement for Python's csv module.

Usage:
    import rocketcsv as csv
"""

import re
from io import StringIO
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
    # If delimiter was explicitly set to None, that's an error
    if "delimiter" in kwargs and kwargs["delimiter"] is None:
        raise TypeError('"delimiter" must be a 1-character string')
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
    delim = kwargs.get("delimiter", ",")
    d = type("dialect", (Dialect,), {"delimiter": delim})()
    d.delimiter = delim
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
    __slots__ = ("_inner", "dialect", "_file", "_mode")

    # _mode values:
    #   0 = normal (delegate to Rust)
    #   1 = QUOTE_NONE with no escapechar (raise on special chars)
    #   2 = QUOTE_NONE with escapechar (manual escape, no quoting)
    #   3 = doublequote=False with escapechar (manual escape-in-quotes)

    # _mode 4 = multi-char lineterminator (manual formatting needed)

    def __init__(self, inner, dialect_obj, file_obj):
        self._inner = inner
        self.dialect = dialect_obj
        self._file = file_obj
        d = dialect_obj
        lt = d.lineterminator
        multichar_lt = lt != "\r\n" and len(lt) > 1
        if d.quoting == QUOTE_NONE and d.escapechar is not None:
            self._mode = 2
        elif d.quoting == QUOTE_NONE and d.escapechar is None:
            self._mode = 1
        elif not d.doublequote and d.escapechar is not None:
            self._mode = 3
        elif multichar_lt:
            self._mode = 4
        else:
            self._mode = 0

    def _manual_writerow(self, row):
        d = self.dialect
        fields = []
        for field in row:
            s = str(field) if field is not None else ""
            if self._mode == 2:
                # QUOTE_NONE + escapechar: escape special chars, never quote
                s = s.replace(d.escapechar, d.escapechar + d.escapechar)
                s = s.replace(d.delimiter, d.escapechar + d.delimiter)
                if d.quotechar:
                    s = s.replace(d.quotechar, d.escapechar + d.quotechar)
                s = s.replace('\r', d.escapechar + '\r')
                s = s.replace('\n', d.escapechar + '\n')
                fields.append(s)
            else:
                # doublequote=False + escapechar: escape quotechar,
                # wrap in quotes only if field contains delimiter or newlines
                need_wrap = (
                    d.delimiter in s
                    or '\r' in s
                    or '\n' in s
                )
                # Always escape quotechar with escapechar (before wrapping)
                if d.quotechar and d.quotechar in s:
                    s = s.replace(d.quotechar, d.escapechar + d.quotechar)
                if need_wrap and d.quotechar:
                    s = d.quotechar + s + d.quotechar
                fields.append(s)
        line = d.delimiter.join(fields) + d.lineterminator
        return self._file.write(line)

    def _manual_writerow_quoteall(self, row):
        """Mode 4: manual formatting for multi-char lineterminator with standard quoting."""
        d = self.dialect
        fields = []
        for field in row:
            s = str(field) if field is not None else ""
            # Apply standard quoting rules
            need_quote = (
                d.quoting == QUOTE_ALL
                or d.delimiter in s
                or '\r' in s
                or '\n' in s
                or (d.quotechar and d.quotechar in s)
            )
            if need_quote and d.quotechar:
                if d.doublequote:
                    s = s.replace(d.quotechar, d.quotechar + d.quotechar)
                s = d.quotechar + s + d.quotechar
            fields.append(s)
        line = d.delimiter.join(fields) + d.lineterminator
        return self._file.write(line)

    def writerow(self, row):
        if self._mode == 1:
            # QUOTE_NONE, no escapechar — check for chars that need escaping
            delim = self.dialect.delimiter
            quotechar = self.dialect.quotechar
            for field in row:
                s = str(field) if not isinstance(field, str) else field
                if delim in s or (quotechar and quotechar in s) or any(
                    c in s for c in ("\r", "\n")
                ):
                    raise Error(
                        "need to escape, but no escapechar set"
                    )
            return self._inner.writerow(row)
        elif self._mode in (2, 3):
            return self._manual_writerow(row)
        elif self._mode == 4:
            return self._manual_writerow_quoteall(row)
        else:
            return self._inner.writerow(row)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def reader(csvfile, dialect=None, **fmtparams):
    """Drop-in replacement for csv.reader(). Supports dialect parameter."""
    # Validate csvfile is iterable
    if not hasattr(csvfile, '__iter__') and not hasattr(csvfile, 'read'):
        raise Error("argument 1 must be an iterator")
    kwargs = _resolve_dialect(dialect, fmtparams)
    _validate_params(kwargs)
    dialect_obj = _make_dialect_obj(kwargs)

    # Fall back to stdlib for edge cases the Rust csv crate doesn't handle:
    # - escapechar in reader (Rust crate handles it differently)
    # - strict mode (not implemented in Rust)
    # - multi-char lineterminator (not applicable to reader but filter out)
    has_escape = kwargs.get("escapechar") is not None
    has_strict = kwargs.get("strict", False)
    has_nonnumeric = kwargs.get("quoting") == QUOTE_NONNUMERIC
    if has_escape or has_strict or has_nonnumeric:
        import csv as _csv_stdlib
        stdlib_kwargs = dict(kwargs)
        stdlib_kwargs.pop("lineterminator", None)
        r = _csv_stdlib.reader(csvfile, **stdlib_kwargs)
        # Wrap to add our dialect attribute
        return _StdlibReaderWrapper(r, dialect_obj)

    # Remove params that Rust reader doesn't accept
    kwargs.pop("lineterminator", None)
    kwargs.pop("strict", None)
    r = _reader_rust(csvfile, **kwargs)
    return _ReaderWrapper(r, dialect_obj)


class _StdlibReaderWrapper:
    """Wraps stdlib csv.reader for edge cases, exposes rocketcsv dialect."""
    __slots__ = ("_inner", "dialect")

    def __init__(self, inner, dialect_obj):
        self._inner = inner
        self.dialect = dialect_obj

    def __iter__(self):
        return self

    def __next__(self):
        import csv as _csv_stdlib
        try:
            return next(self._inner)
        except _csv_stdlib.Error as e:
            raise Error(str(e)) from None

    @property
    def line_num(self):
        return self._inner.line_num


def writer(csvfile, dialect=None, **fmtparams):
    """Drop-in replacement for csv.writer(). Supports dialect parameter."""
    if not hasattr(csvfile, 'write'):
        raise TypeError(
            "argument 1 must have a \"write\" method"
        )
    kwargs = _resolve_dialect(dialect, fmtparams)
    _validate_params(kwargs)
    dialect_obj = _make_dialect_obj(kwargs)
    # Remove params that only apply to reader
    kwargs.pop("strict", None)
    kwargs.pop("skipinitialspace", None)
    w = _writer_rust(csvfile, **kwargs)
    return _WriterWrapper(w, dialect_obj, csvfile)

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

    def __init__(self):
        # Base Dialect class cannot be instantiated directly
        if type(self) is Dialect:
            raise Error("CSV dialect class not subclassed correctly")
        # Subclass must explicitly define delimiter (not just inherit it)
        if "delimiter" not in type(self).__dict__:
            raise Error("Dialect has no 'delimiter' attribute")
        d = type(self).__dict__["delimiter"]
        if not isinstance(d, str):
            raise Error(
                "delimiter must be a string, not %s" % type(d).__name__
            )


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
    '''
    "Sniffs" the format of a CSV file (i.e. delimiter, quotechar)
    Returns a Dialect object.
    '''
    def __init__(self):
        # in case there is more than one possible delimiter
        self.preferred = [',', '\t', ';', ' ', ':']

    def sniff(self, sample, delimiters=None):
        """
        Returns a dialect (or None) corresponding to the sample
        """

        quotechar, doublequote, delimiter, skipinitialspace = \
                   self._guess_quote_and_delimiter(sample, delimiters)
        if not delimiter:
            delimiter, skipinitialspace = self._guess_delimiter(sample,
                                                                delimiters)

        if not delimiter:
            raise Error("Could not determine delimiter")

        class dialect(Dialect):
            _name = "sniffed"
            lineterminator = '\r\n'
            quoting = QUOTE_MINIMAL
            # escapechar = ''

        dialect.doublequote = doublequote
        dialect.delimiter = delimiter
        # _csv.reader won't accept a quotechar of ''
        dialect.quotechar = quotechar or '"'
        dialect.skipinitialspace = skipinitialspace

        return dialect

    def _guess_quote_and_delimiter(self, data, delimiters):
        """
        Looks for text enclosed between two identical quotes
        (the probable quotechar) which are preceded and followed
        by the same character (the probable delimiter).
        For example:
                         ,'some text',
        The quote with the most wins, same with the delimiter.
        If there is no quotechar the delimiter can't be determined
        this way.
        """

        matches = []
        for restr in (r'(?P<delim>[^\w\n"\'])(?P<space> ?)(?P<quote>["\']).*?(?P=quote)(?P=delim)', # ,".*?",
                      r'(?:^|\n)(?P<quote>["\']).*?(?P=quote)(?P<delim>[^\w\n"\'])(?P<space> ?)',   #  ".*?",
                      r'(?P<delim>[^\w\n"\'])(?P<space> ?)(?P<quote>["\']).*?(?P=quote)(?:$|\n)',   # ,".*?"
                      r'(?:^|\n)(?P<quote>["\']).*?(?P=quote)(?:$|\n)'):                            #  ".*?" (no delim, no space)
            regexp = re.compile(restr, re.DOTALL | re.MULTILINE)
            matches = regexp.findall(data)
            if matches:
                break

        if not matches:
            # (quotechar, doublequote, delimiter, skipinitialspace)
            return ('', False, None, 0)
        quotes = {}
        delims = {}
        spaces = 0
        groupindex = regexp.groupindex
        for m in matches:
            n = groupindex['quote'] - 1
            key = m[n]
            if key:
                quotes[key] = quotes.get(key, 0) + 1
            try:
                n = groupindex['delim'] - 1
                key = m[n]
            except KeyError:
                continue
            if key and (delimiters is None or key in delimiters):
                delims[key] = delims.get(key, 0) + 1
            try:
                n = groupindex['space'] - 1
            except KeyError:
                continue
            if m[n]:
                spaces += 1

        quotechar = max(quotes, key=quotes.get)

        if delims:
            delim = max(delims, key=delims.get)
            skipinitialspace = delims[delim] == spaces
            if delim == '\n': # most likely a file with a single column
                delim = ''
        else:
            # there is *no* delimiter, it's a single column of quoted data
            delim = ''
            skipinitialspace = 0

        # if we see an extra quote between delimiters, we've got a
        # double quoted format
        dq_regexp = re.compile(
                               r"((%(delim)s)|^)\W*%(quote)s[^%(delim)s\n]*%(quote)s[^%(delim)s\n]*%(quote)s\W*((%(delim)s)|$)" % \
                               {'delim':re.escape(delim), 'quote':quotechar}, re.MULTILINE)

        if dq_regexp.search(data):
            doublequote = True
        else:
            doublequote = False

        return (quotechar, doublequote, delim, skipinitialspace)

    def _guess_delimiter(self, data, delimiters):
        """
        The delimiter /should/ occur the same number of times on
        each row. However, due to malformed data, it may not. We don't want
        an all or nothing approach, so we allow for small variations in this
        number.
          1) build a table of the frequency of each character on every line.
          2) build a table of frequencies of this frequency (meta-frequency?),
             e.g.  'x occurred 5 times in 10 rows, 6 times in 1000 rows,
             7 times in 2 rows'
          3) use the mode of the meta-frequency to determine the /expected/
             frequency for that character
          4) find out how often the character actually meets that goal
          5) the character that best meets its goal is the delimiter
        For performance reasons, the data is evaluated in chunks, so it can
        try and evaluate the smallest portion of the data possible, evaluating
        additional chunks as necessary.
        """

        data = list(filter(None, data.split('\n')))

        ascii = [chr(c) for c in range(127)] # 7-bit ASCII

        # build frequency tables
        chunkLength = min(10, len(data))
        iteration = 0
        charFrequency = {}
        modes = {}
        delims = {}
        start, end = 0, chunkLength
        while start < len(data):
            iteration += 1
            for line in data[start:end]:
                for char in ascii:
                    metaFrequency = charFrequency.get(char, {})
                    # must count even if frequency is 0
                    freq = line.count(char)
                    # value is the mode
                    metaFrequency[freq] = metaFrequency.get(freq, 0) + 1
                    charFrequency[char] = metaFrequency

            for char in charFrequency.keys():
                items = list(charFrequency[char].items())
                if len(items) == 1 and items[0][0] == 0:
                    continue
                # get the mode of the frequencies
                if len(items) > 1:
                    modes[char] = max(items, key=lambda x: x[1])
                    # adjust the mode - subtract the sum of all
                    # other frequencies
                    items.remove(modes[char])
                    modes[char] = (modes[char][0], modes[char][1]
                                   - sum(item[1] for item in items))
                else:
                    modes[char] = items[0]

            # build a list of possible delimiters
            modeList = modes.items()
            total = float(min(chunkLength * iteration, len(data)))
            # (rows of consistent data) / (number of rows) = 100%
            consistency = 1.0
            # minimum consistency threshold
            threshold = 0.9
            while len(delims) == 0 and consistency >= threshold:
                for k, v in modeList:
                    if v[0] > 0 and v[1] > 0:
                        if ((v[1]/total) >= consistency and
                            (delimiters is None or k in delimiters)):
                            delims[k] = v
                consistency -= 0.01

            if len(delims) == 1:
                delim = list(delims.keys())[0]
                skipinitialspace = (data[0].count(delim) ==
                                    data[0].count("%c " % delim))
                return (delim, skipinitialspace)

            # analyze another chunkLength lines
            start = end
            end += chunkLength

        if not delims:
            return ('', 0)

        # if there's more than one, fall back to a 'preferred' list
        if len(delims) > 1:
            for d in self.preferred:
                if d in delims.keys():
                    skipinitialspace = (data[0].count(d) ==
                                        data[0].count("%c " % d))
                    return (d, skipinitialspace)

        # nothing else indicates a preference, pick the character that
        # dominates(?)
        items = [(v,k) for (k,v) in delims.items()]
        items.sort()
        delim = items[-1][1]

        skipinitialspace = (data[0].count(delim) ==
                            data[0].count("%c " % delim))
        return (delim, skipinitialspace)

    def has_header(self, sample):
        # Creates a dictionary of types of data in each column. If any
        # column is of a single type (say, integers), *except* for the first
        # row, then the first row is presumed to be labels. If the type
        # can't be determined, it is assumed to be a string in which case
        # the length of the string is the determining factor: if all of the
        # rows except for the first are the same length, it's a header.
        # Finally, a 'vote' is taken at the end for each column, adding or
        # subtracting from the likelihood of the first row being a header.

        rdr = reader(StringIO(sample), self.sniff(sample))

        header = next(rdr) # assume first row is header

        columns = len(header)
        columnTypes = {}
        for i in range(columns): columnTypes[i] = None

        checked = 0
        for row in rdr:
            # arbitrary number of rows to check, to keep it sane
            if checked > 20:
                break
            checked += 1

            if len(row) != columns:
                continue # skip rows that have irregular number of columns

            for col in list(columnTypes.keys()):
                thisType = complex
                try:
                    thisType(row[col])
                except (ValueError, OverflowError):
                    # fallback to length of string
                    thisType = len(row[col])

                if thisType != columnTypes[col]:
                    if columnTypes[col] is None: # add new column type
                        columnTypes[col] = thisType
                    else:
                        # type is inconsistent, remove column from
                        # consideration
                        del columnTypes[col]

        # finally, compare results against first row and "vote"
        # on whether it's a header
        hasHeader = 0
        for col, colType in columnTypes.items():
            if type(colType) == type(0): # it's a length
                if len(header[col]) != colType:
                    hasHeader += 1
                else:
                    hasHeader -= 1
            else: # attempt typecast
                try:
                    colType(header[col])
                except (ValueError, TypeError):
                    hasHeader += 1
                else:
                    hasHeader -= 1

        return hasHeader > 0


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
        self.reader = reader(f, dialect=dialect, *args, **kwds)
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
        if extrasaction not in ("raise", "ignore"):
            raise ValueError("extrasaction (%s) must be 'raise' or 'ignore'" % extrasaction)
        self.fieldnames = fieldnames
        self.restval = restval
        self.extrasaction = extrasaction
        self.writer = writer(f, dialect=dialect, *args, **kwds)

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
