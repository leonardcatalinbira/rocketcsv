"""
Strict compatibility test suite for a drop-in replacement of Python's csv module.

Run with:
    pytest test_csv_compat.py -v

Replace the import below with your module:
    import your_csv_module as csv_mod

The tests compare your module's behavior against the stdlib csv module
to ensure identical output in all cases.
"""

import csv as csv_stdlib
import io
import pytest
import sys
import tempfile
import os

# ============================================================================
# CHANGE THIS IMPORT to point at your replacement module
# ============================================================================
import rocketcsv as csv_mod  # drop-in replacement under test
# ============================================================================

PY312_PLUS = sys.version_info >= (3, 12)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_and_read(rows, mod=csv_mod, **writer_kw):
    """Write rows with the module's writer, then read them back with its reader."""
    buf = io.StringIO()
    w = mod.writer(buf, **writer_kw)
    for row in rows:
        w.writerow(row)
    buf.seek(0)
    return list(mod.reader(buf, **writer_kw))


def _write_to_string(rows, mod=csv_mod, **writer_kw):
    """Write rows and return the raw CSV string."""
    buf = io.StringIO()
    w = mod.writer(buf, **writer_kw)
    for row in rows:
        w.writerow(row)
    return buf.getvalue()


def _read_from_string(text, mod=csv_mod, **reader_kw):
    """Read a raw CSV string and return list of rows."""
    return list(mod.reader(io.StringIO(text), **reader_kw))


def assert_same_as_stdlib(rows, **kw):
    """Assert that the module produces identical output to stdlib for both
    writing and reading."""
    stdlib_str = _write_to_string(rows, mod=csv_stdlib, **kw)
    mod_str = _write_to_string(rows, mod=csv_mod, **kw)
    assert mod_str == stdlib_str, (
        f"Writer mismatch:\n  stdlib: {stdlib_str!r}\n  module: {mod_str!r}"
    )
    stdlib_rows = _read_from_string(stdlib_str, mod=csv_stdlib, **kw)
    mod_rows = _read_from_string(mod_str, mod=csv_mod, **kw)
    assert mod_rows == stdlib_rows, (
        f"Reader mismatch:\n  stdlib: {stdlib_rows}\n  module: {mod_rows}"
    )


def roundtrip_matches_stdlib(text, **kw):
    """Assert that reading a given text produces identical rows to stdlib."""
    stdlib_rows = _read_from_string(text, mod=csv_stdlib, **kw)
    mod_rows = _read_from_string(text, mod=csv_mod, **kw)
    assert mod_rows == stdlib_rows, (
        f"Read mismatch:\n  stdlib: {stdlib_rows}\n  module: {mod_rows}"
    )


# ===========================================================================
#  1. MODULE-LEVEL CONSTANTS & ATTRIBUTES
# ===========================================================================

class TestModuleAttributes:

    def test_has_reader(self):
        assert callable(csv_mod.reader)

    def test_has_writer(self):
        assert callable(csv_mod.writer)

    def test_has_DictReader(self):
        assert callable(csv_mod.DictReader)

    def test_has_DictWriter(self):
        assert callable(csv_mod.DictWriter)

    def test_has_register_dialect(self):
        assert callable(csv_mod.register_dialect)

    def test_has_unregister_dialect(self):
        assert callable(csv_mod.unregister_dialect)

    def test_has_get_dialect(self):
        assert callable(csv_mod.get_dialect)

    def test_has_list_dialects(self):
        assert callable(csv_mod.list_dialects)

    def test_has_field_size_limit(self):
        assert callable(csv_mod.field_size_limit)

    def test_has_Dialect_class(self):
        assert isinstance(csv_mod.Dialect, type)

    def test_has_Sniffer_class(self):
        assert isinstance(csv_mod.Sniffer, type)

    def test_has_Error(self):
        assert issubclass(csv_mod.Error, Exception)

    def test_has_version(self):
        assert hasattr(csv_mod, "__version__")

    def test_has_QUOTE_ALL(self):
        assert csv_mod.QUOTE_ALL == csv_stdlib.QUOTE_ALL

    def test_has_QUOTE_MINIMAL(self):
        assert csv_mod.QUOTE_MINIMAL == csv_stdlib.QUOTE_MINIMAL

    def test_has_QUOTE_NONNUMERIC(self):
        assert csv_mod.QUOTE_NONNUMERIC == csv_stdlib.QUOTE_NONNUMERIC

    def test_has_QUOTE_NONE(self):
        assert csv_mod.QUOTE_NONE == csv_stdlib.QUOTE_NONE

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_STRINGS added in 3.12")
    def test_has_QUOTE_STRINGS(self):
        assert csv_mod.QUOTE_STRINGS == csv_stdlib.QUOTE_STRINGS

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_NOTNULL added in 3.12")
    def test_has_QUOTE_NOTNULL(self):
        assert csv_mod.QUOTE_NOTNULL == csv_stdlib.QUOTE_NOTNULL

    def test_excel_in_dialects(self):
        assert "excel" in csv_mod.list_dialects()

    def test_excel_tab_in_dialects(self):
        assert "excel-tab" in csv_mod.list_dialects()

    def test_unix_in_dialects(self):
        assert "unix" in csv_mod.list_dialects()


# ===========================================================================
#  2. BASIC READER
# ===========================================================================

class TestReaderBasic:

    def test_simple_row(self):
        roundtrip_matches_stdlib("a,b,c\r\n")

    def test_multiple_rows(self):
        roundtrip_matches_stdlib("a,b\r\nc,d\r\n")

    def test_empty_input(self):
        roundtrip_matches_stdlib("")

    def test_single_field(self):
        roundtrip_matches_stdlib("hello\r\n")

    def test_empty_fields(self):
        roundtrip_matches_stdlib(",,,\r\n")

    def test_trailing_comma(self):
        roundtrip_matches_stdlib("a,b,c,\r\n")

    def test_leading_comma(self):
        roundtrip_matches_stdlib(",a,b\r\n")

    def test_blank_line(self):
        roundtrip_matches_stdlib("a,b\r\n\r\nc,d\r\n")

    def test_lf_line_ending(self):
        roundtrip_matches_stdlib("a,b\nc,d\n")

    def test_cr_line_ending(self):
        """Bare \\r as line ending. Must use newline='' to avoid Python's
        universal-newline translation mangling the \\r before csv sees it."""
        text = "a,b\rc,d\r"
        std = list(csv_stdlib.reader(io.StringIO(text, newline="")))
        mod = list(csv_mod.reader(io.StringIO(text, newline="")))
        assert mod == std

    def test_mixed_line_endings(self):
        roundtrip_matches_stdlib("a,b\r\nc,d\ne,f\r")

    def test_no_trailing_newline(self):
        roundtrip_matches_stdlib("a,b,c")

    def test_whitespace_fields(self):
        roundtrip_matches_stdlib(" a , b , c \r\n")

    def test_numeric_fields(self):
        roundtrip_matches_stdlib("1,2,3\r\n")

    def test_reader_is_iterator(self):
        r = csv_mod.reader(io.StringIO("a,b\r\n"))
        assert hasattr(r, '__iter__')
        assert hasattr(r, '__next__')

    def test_reader_line_num(self):
        r = csv_mod.reader(io.StringIO("a\r\nb\r\n"))
        assert r.line_num == 0
        next(r)
        assert r.line_num == 1
        next(r)
        assert r.line_num == 2

    def test_reader_line_num_multiline_quoted(self):
        """line_num counts physical lines, including those inside quotes."""
        r = csv_mod.reader(io.StringIO('"a\nb",c\r\nd,e\r\n'))
        r_std = csv_stdlib.reader(io.StringIO('"a\nb",c\r\nd,e\r\n'))
        next(r); next(r_std)
        assert r.line_num == r_std.line_num
        next(r); next(r_std)
        assert r.line_num == r_std.line_num

    def test_reader_with_list_input(self):
        """reader() accepts any iterable, not just file objects."""
        rows = list(csv_mod.reader(["a,b", "c,d"]))
        std_rows = list(csv_stdlib.reader(["a,b", "c,d"]))
        assert rows == std_rows

    def test_reader_with_custom_iterable(self):
        """reader() works with arbitrary iterables."""
        class MyIter:
            def __init__(self):
                self._lines = iter(["x,y", "1,2"])
            def __iter__(self):
                return self
            def __next__(self):
                return next(self._lines)
        rows = list(csv_mod.reader(MyIter()))
        assert rows == [["x", "y"], ["1", "2"]]

    def test_reader_has_dialect_attribute(self):
        r = csv_mod.reader(io.StringIO("a,b"))
        assert hasattr(r, "dialect")
        assert r.dialect.delimiter == ","

    def test_reader_dialect_reflects_params(self):
        r = csv_mod.reader(io.StringIO("a\tb"), delimiter="\t")
        assert r.dialect.delimiter == "\t"


# ===========================================================================
#  3. QUOTING DURING READ
# ===========================================================================

class TestReaderQuoting:

    def test_quoted_field(self):
        roundtrip_matches_stdlib('"hello","world"\r\n')

    def test_quoted_with_comma(self):
        roundtrip_matches_stdlib('"a,b",c\r\n')

    def test_quoted_with_newline(self):
        roundtrip_matches_stdlib('"a\nb",c\r\n')

    def test_quoted_with_crlf(self):
        roundtrip_matches_stdlib('"a\r\nb",c\r\n')

    def test_escaped_quote(self):
        roundtrip_matches_stdlib('"a""b",c\r\n')

    def test_double_escaped_quote(self):
        roundtrip_matches_stdlib('"a""""b",c\r\n')

    def test_quoted_empty(self):
        roundtrip_matches_stdlib('"",""\r\n')

    def test_quote_at_start_of_field(self):
        roundtrip_matches_stdlib('"hello",world\r\n')

    def test_quote_at_end_of_field(self):
        roundtrip_matches_stdlib('hello,"world"\r\n')

    def test_all_quoted(self):
        roundtrip_matches_stdlib('"a","b","c"\r\n')

    def test_multiline_quoted_field(self):
        roundtrip_matches_stdlib('"line1\nline2\nline3",b\r\n')

    def test_quoted_field_with_only_quotes(self):
        roundtrip_matches_stdlib('""""\r\n')

    def test_quoted_field_with_whitespace(self):
        roundtrip_matches_stdlib('"  hello  "\r\n')

    def test_adjacent_quoted_fields(self):
        roundtrip_matches_stdlib('"a","b"\r\n')


# ===========================================================================
#  4. BASIC WRITER
# ===========================================================================

class TestWriterBasic:

    def test_simple_row(self):
        assert_same_as_stdlib([["a", "b", "c"]])

    def test_multiple_rows(self):
        assert_same_as_stdlib([["a", "b"], ["c", "d"]])

    def test_empty_row(self):
        assert_same_as_stdlib([[]])

    def test_empty_string_field(self):
        assert_same_as_stdlib([["", "", ""]])

    def test_single_field(self):
        assert_same_as_stdlib([["hello"]])

    def test_numeric_values(self):
        assert_same_as_stdlib([[1, 2, 3]])

    def test_float_values(self):
        assert_same_as_stdlib([[1.1, 2.2, 3.3]])

    def test_mixed_types(self):
        assert_same_as_stdlib([["text", 42, 3.14, True, None]])

    def test_none_field(self):
        """None is written as empty string."""
        assert_same_as_stdlib([[None]])

    def test_bool_fields(self):
        """Booleans are written as 'True' / 'False'."""
        assert_same_as_stdlib([[True, False]])

    def test_writerow_with_tuple(self):
        """writerow accepts tuples, not just lists."""
        buf_mod = io.StringIO()
        csv_mod.writer(buf_mod).writerow(("a", "b", "c"))
        buf_std = io.StringIO()
        csv_stdlib.writer(buf_std).writerow(("a", "b", "c"))
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writerow_with_generator(self):
        """writerow accepts generators."""
        buf_mod = io.StringIO()
        csv_mod.writer(buf_mod).writerow(x for x in ["a", "b"])
        buf_std = io.StringIO()
        csv_stdlib.writer(buf_std).writerow(x for x in ["a", "b"])
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writerow_returns_string(self):
        """writerow should return the string written."""
        buf = io.StringIO()
        w = csv_mod.writer(buf)
        result = w.writerow(["a", "b"])
        expected_buf = io.StringIO()
        w2 = csv_stdlib.writer(expected_buf)
        expected = w2.writerow(["a", "b"])
        assert result == expected

    def test_writerows(self):
        buf_mod = io.StringIO()
        w = csv_mod.writer(buf_mod)
        w.writerows([["a", "b"], ["c", "d"]])
        buf_std = io.StringIO()
        w2 = csv_stdlib.writer(buf_std)
        w2.writerows([["a", "b"], ["c", "d"]])
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writerows_returns_none(self):
        """writerows returns None (unlike writerow)."""
        buf = io.StringIO()
        result = csv_mod.writer(buf).writerows([["a"]])
        assert result is None


# ===========================================================================
#  5. WRITER QUOTING BEHAVIOR
# ===========================================================================

class TestWriterQuoting:

    def test_field_with_comma(self):
        assert_same_as_stdlib([["a,b", "c"]])

    def test_field_with_quote(self):
        assert_same_as_stdlib([['a"b', "c"]])

    def test_field_with_newline(self):
        assert_same_as_stdlib([["a\nb", "c"]])

    def test_field_with_crlf(self):
        assert_same_as_stdlib([["a\r\nb", "c"]])

    def test_field_with_cr(self):
        assert_same_as_stdlib([["a\rb", "c"]])

    def test_field_with_delimiter_and_quote(self):
        assert_same_as_stdlib([['a,"b', "c"]])

    def test_quote_all(self):
        assert_same_as_stdlib([["a", "b", "c"]], quoting=csv_stdlib.QUOTE_ALL)

    def test_quote_all_with_numbers(self):
        assert_same_as_stdlib(
            [["text", 42, 3.14]], quoting=csv_stdlib.QUOTE_ALL
        )

    def test_quote_nonnumeric(self):
        assert_same_as_stdlib(
            [["text", 42, 3.14]], quoting=csv_stdlib.QUOTE_NONNUMERIC
        )

    def test_quote_none_simple(self):
        assert_same_as_stdlib(
            [["a", "b", "c"]],
            quoting=csv_stdlib.QUOTE_NONE,
            escapechar="\\",
        )

    def test_quote_none_with_special_chars(self):
        """With QUOTE_NONE, special chars must be escaped."""
        assert_same_as_stdlib(
            [["a,b", "c"]],
            quoting=csv_stdlib.QUOTE_NONE,
            escapechar="\\",
        )

    def test_quote_minimal_no_special(self):
        assert_same_as_stdlib(
            [["abc", "def"]], quoting=csv_stdlib.QUOTE_MINIMAL
        )

    def test_quote_minimal_with_special(self):
        assert_same_as_stdlib(
            [["a,b", "d\"e"]], quoting=csv_stdlib.QUOTE_MINIMAL
        )

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_STRINGS added in 3.12")
    def test_quote_strings_write(self):
        """QUOTE_STRINGS: quote string fields, leave numbers/None unquoted."""
        assert_same_as_stdlib(
            [["text", 42, 3.14, None, True, ""]],
            quoting=csv_stdlib.QUOTE_STRINGS,
        )

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_NOTNULL added in 3.12")
    def test_quote_notnull_write(self):
        """QUOTE_NOTNULL: quote everything except None, which becomes empty unquoted."""
        assert_same_as_stdlib(
            [["text", 42, None, "", "end"]],
            quoting=csv_stdlib.QUOTE_NOTNULL,
        )

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_STRINGS added in 3.12")
    def test_quote_strings_roundtrip(self):
        rows = [["hello", "world"]]
        result = _write_and_read(rows, mod=csv_mod, quoting=csv_mod.QUOTE_STRINGS)
        assert result == rows

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_NOTNULL added in 3.12")
    def test_quote_notnull_roundtrip(self):
        rows = [["hello", "world"]]
        result = _write_and_read(rows, mod=csv_mod, quoting=csv_mod.QUOTE_NOTNULL)
        assert result == rows


# ===========================================================================
#  6. QUOTE_NONNUMERIC / QUOTE_STRINGS / QUOTE_NOTNULL READER BEHAVIOR
# ===========================================================================

class TestQuotingReadBehavior:

    def test_nonnumeric_casts_unquoted_to_float(self):
        """With QUOTE_NONNUMERIC, unquoted fields become floats."""
        text = '"hello",42,"world",3.14\r\n'
        std = _read_from_string(
            text, mod=csv_stdlib, quoting=csv_stdlib.QUOTE_NONNUMERIC
        )
        mod = _read_from_string(
            text, mod=csv_mod, quoting=csv_mod.QUOTE_NONNUMERIC
        )
        assert mod == std
        assert isinstance(mod[0][0], str)
        assert isinstance(mod[0][1], float)
        assert isinstance(mod[0][2], str)
        assert isinstance(mod[0][3], float)

    def test_nonnumeric_raises_on_unquoted_nonnumeric(self):
        """QUOTE_NONNUMERIC: unquoted non-numeric string raises ValueError."""
        text = "hello,42\r\n"
        with pytest.raises(ValueError):
            _read_from_string(text, mod=csv_mod, quoting=csv_mod.QUOTE_NONNUMERIC)

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_STRINGS added in 3.12")
    def test_quote_strings_read(self):
        """QUOTE_STRINGS read behavior matches stdlib."""
        text = '"hello",42,"",\r\n'
        std = _read_from_string(text, mod=csv_stdlib, quoting=csv_stdlib.QUOTE_STRINGS)
        mod = _read_from_string(text, mod=csv_mod, quoting=csv_mod.QUOTE_STRINGS)
        assert mod == std

    @pytest.mark.skipif(not PY312_PLUS, reason="QUOTE_NOTNULL added in 3.12")
    def test_quote_notnull_read(self):
        """QUOTE_NOTNULL read behavior matches stdlib."""
        text = '"hello",,\"world\"\r\n'
        std = _read_from_string(text, mod=csv_stdlib, quoting=csv_stdlib.QUOTE_NOTNULL)
        mod = _read_from_string(text, mod=csv_mod, quoting=csv_mod.QUOTE_NOTNULL)
        assert mod == std


# ===========================================================================
#  7. DELIMITER / QUOTECHAR / ESCAPECHAR / LINETERMINATOR
# ===========================================================================

class TestDialectParameters:

    def test_tab_delimiter(self):
        assert_same_as_stdlib([["a", "b", "c"]], delimiter="\t")

    def test_pipe_delimiter(self):
        assert_same_as_stdlib([["a", "b", "c"]], delimiter="|")

    def test_semicolon_delimiter(self):
        assert_same_as_stdlib([["a", "b", "c"]], delimiter=";")

    def test_custom_quotechar(self):
        assert_same_as_stdlib([["a,b", "c"]], quotechar="'")

    def test_quotechar_in_field(self):
        assert_same_as_stdlib([["it's", "here"]], quotechar="'")

    def test_quotechar_none_with_quote_none(self):
        """quotechar=None is valid with QUOTE_NONE."""
        assert_same_as_stdlib(
            [["a", "b"]],
            quotechar=None, quoting=csv_stdlib.QUOTE_NONE, escapechar="\\"
        )

    def test_custom_lineterminator(self):
        s = _write_to_string([["a", "b"]], mod=csv_mod, lineterminator="\n")
        s_std = _write_to_string(
            [["a", "b"]], mod=csv_stdlib, lineterminator="\n"
        )
        assert s == s_std

    def test_lineterminator_multichar(self):
        """lineterminator can be multi-character."""
        s = _write_to_string([["a"]], mod=csv_mod, lineterminator="END\n")
        s_std = _write_to_string([["a"]], mod=csv_stdlib, lineterminator="END\n")
        assert s == s_std

    def test_escapechar_with_quote_none(self):
        assert_same_as_stdlib(
            [["a,b", "c"]], quoting=csv_stdlib.QUOTE_NONE, escapechar="\\"
        )

    def test_doublequote_true(self):
        assert_same_as_stdlib([['a"b', "c"]], doublequote=True)

    def test_doublequote_false(self):
        assert_same_as_stdlib(
            [['a"b', "c"]], doublequote=False, escapechar="\\"
        )

    def test_skipinitialspace_true(self):
        text = "a, b, c\r\n"
        std = _read_from_string(text, mod=csv_stdlib, skipinitialspace=True)
        mod = _read_from_string(text, mod=csv_mod, skipinitialspace=True)
        assert mod == std

    def test_skipinitialspace_false(self):
        text = "a, b, c\r\n"
        std = _read_from_string(text, mod=csv_stdlib, skipinitialspace=False)
        mod = _read_from_string(text, mod=csv_mod, skipinitialspace=False)
        assert mod == std

    def test_strict_mode_rejects_bad_input(self):
        """strict=True should raise csv.Error on malformed input."""
        # Content after closing quote: "abc"def
        text = '"abc"def,g\r\n'
        with pytest.raises(csv_mod.Error):
            _read_from_string(text, mod=csv_mod, strict=True)

    def test_strict_default_is_false(self):
        d = csv_mod.get_dialect("excel")
        assert d.strict is False or d.strict == 0

    def test_escapechar_default_is_none(self):
        d = csv_mod.get_dialect("excel")
        assert d.escapechar is None

    def test_dialect_as_positional_arg_reader(self):
        """Dialect name can be passed as positional argument."""
        rows = list(csv_mod.reader(io.StringIO("a\tb"), "excel-tab"))
        assert rows == [["a", "b"]]

    def test_dialect_as_positional_arg_writer(self):
        buf = io.StringIO()
        csv_mod.writer(buf, "excel-tab").writerow(["a", "b"])
        assert buf.getvalue() == "a\tb\r\n"

    def test_dialect_kwarg_with_override(self):
        """Parameters override dialect settings."""
        rows = list(csv_mod.reader(
            io.StringIO("a;b"), dialect="excel", delimiter=";"
        ))
        assert rows == [["a", "b"]]

    def test_dialect_object_passed_directly(self):
        """A dialect instance/class can be passed, not just a name."""
        d = csv_mod.get_dialect("excel-tab")
        buf = io.StringIO()
        csv_mod.writer(buf, dialect=d).writerow(["a", "b"])
        assert buf.getvalue() == "a\tb\r\n"


# ===========================================================================
#  8. DIALECT REGISTRATION
# ===========================================================================

class TestDialects:

    def test_register_and_get(self):
        class MyDialect(csv_mod.Dialect):
            delimiter = "|"
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = "\r\n"
            quoting = csv_mod.QUOTE_MINIMAL

        csv_mod.register_dialect("test_mine", MyDialect)
        d = csv_mod.get_dialect("test_mine")
        assert d.delimiter == "|"
        csv_mod.unregister_dialect("test_mine")

    def test_register_with_kwargs(self):
        csv_mod.register_dialect("test_kw", delimiter=";")
        d = csv_mod.get_dialect("test_kw")
        assert d.delimiter == ";"
        csv_mod.unregister_dialect("test_kw")

    def test_register_overwrites_existing(self):
        """Registering with the same name overwrites the previous dialect."""
        csv_mod.register_dialect("test_overwrite", delimiter=",")
        csv_mod.register_dialect("test_overwrite", delimiter=";")
        d = csv_mod.get_dialect("test_overwrite")
        assert d.delimiter == ";"
        csv_mod.unregister_dialect("test_overwrite")

    def test_unregister_raises_on_unknown(self):
        with pytest.raises(csv_mod.Error):
            csv_mod.unregister_dialect("nonexistent_dialect_xyz")

    def test_get_raises_on_unknown(self):
        with pytest.raises(csv_mod.Error):
            csv_mod.get_dialect("nonexistent_dialect_xyz")

    def test_write_with_dialect_name(self):
        csv_mod.register_dialect("test_pipe", delimiter="|")
        s = _write_to_string([["a", "b"]], mod=csv_mod, dialect="test_pipe")
        assert s == "a|b\r\n"
        csv_mod.unregister_dialect("test_pipe")

    def test_read_with_dialect_name(self):
        csv_mod.register_dialect("test_tab2", delimiter="\t")
        rows = _read_from_string("a\tb\r\n", mod=csv_mod, dialect="test_tab2")
        assert rows == [["a", "b"]]
        csv_mod.unregister_dialect("test_tab2")

    def test_excel_dialect(self):
        d = csv_mod.get_dialect("excel")
        assert d.delimiter == ","
        assert d.quotechar == '"'
        assert d.doublequote is True
        assert d.skipinitialspace is False
        assert d.lineterminator == "\r\n"
        assert d.quoting == csv_mod.QUOTE_MINIMAL

    def test_excel_tab_dialect(self):
        d = csv_mod.get_dialect("excel-tab")
        assert d.delimiter == "\t"

    def test_unix_dialect(self):
        d = csv_mod.get_dialect("unix")
        assert d.lineterminator == "\n"
        assert d.quoting == csv_stdlib.QUOTE_ALL

    def test_builtin_dialects_can_be_unregistered(self):
        """stdlib allows unregistering built-in dialects."""
        csv_mod.unregister_dialect("excel")
        assert "excel" not in csv_mod.list_dialects()
        # Re-register to restore state
        class excel(csv_mod.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = "\r\n"
            quoting = csv_mod.QUOTE_MINIMAL
        csv_mod.register_dialect("excel", excel)


# ===========================================================================
#  9. DIALECT CLASS VALIDATION
# ===========================================================================

class TestDialectValidation:

    def test_abstract_dialect_instantiation(self):
        """Instantiating Dialect base class directly should raise Error."""
        with pytest.raises(csv_mod.Error):
            csv_mod.Dialect()

    def test_dialect_missing_delimiter(self):
        """Dialect subclass without delimiter raises Error."""
        with pytest.raises(csv_mod.Error):
            class Bad(csv_mod.Dialect):
                quotechar = '"'
                doublequote = True
                skipinitialspace = False
                lineterminator = "\r\n"
                quoting = csv_mod.QUOTE_MINIMAL
            Bad()

    def test_dialect_bad_delimiter_type(self):
        """Non-string delimiter raises Error."""
        with pytest.raises((csv_mod.Error, TypeError)):
            class Bad(csv_mod.Dialect):
                delimiter = 123
                quotechar = '"'
                doublequote = True
                skipinitialspace = False
                lineterminator = "\r\n"
                quoting = csv_mod.QUOTE_MINIMAL
            Bad()


# ===========================================================================
# 10. DictReader
# ===========================================================================

class TestDictReader:

    def test_basic(self):
        text = "name,age\r\nAlice,30\r\nBob,25\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text)))
        mod = list(csv_mod.DictReader(io.StringIO(text)))
        assert mod == std

    def test_custom_fieldnames(self):
        text = "Alice,30\r\nBob,25\r\n"
        std = list(
            csv_stdlib.DictReader(io.StringIO(text), fieldnames=["name", "age"])
        )
        mod = list(
            csv_mod.DictReader(io.StringIO(text), fieldnames=["name", "age"])
        )
        assert mod == std

    def test_fieldnames_from_generator(self):
        """Fieldnames passed as iterator/generator are converted to list."""
        text = "1,2\r\n"
        dr = csv_mod.DictReader(io.StringIO(text), fieldnames=iter(["a", "b"]))
        rows = list(dr)
        assert rows == [{"a": "1", "b": "2"}]

    def test_extra_fields(self):
        """Rows with more fields than headers => restkey."""
        text = "a,b\r\n1,2,3,4\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text)))
        mod = list(csv_mod.DictReader(io.StringIO(text)))
        assert mod == std

    def test_missing_fields(self):
        """Rows with fewer fields than headers => restval."""
        text = "a,b,c\r\n1\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text), restval="MISSING"))
        mod = list(csv_mod.DictReader(io.StringIO(text), restval="MISSING"))
        assert mod == std

    def test_custom_restkey_restval(self):
        text = "a,b\r\n1,2,3\r\n4\r\n"
        kw = dict(restkey="_extra", restval="_missing")
        std = list(csv_stdlib.DictReader(io.StringIO(text), **kw))
        mod = list(csv_mod.DictReader(io.StringIO(text), **kw))
        assert mod == std

    def test_fieldnames_property(self):
        text = "x,y,z\r\n1,2,3\r\n"
        dr = csv_mod.DictReader(io.StringIO(text))
        assert dr.fieldnames == ["x", "y", "z"]

    def test_fieldnames_setter(self):
        """fieldnames can be overridden via setter."""
        text = "1,2\r\n3,4\r\n"
        dr = csv_mod.DictReader(io.StringIO(text))
        dr.fieldnames = ["x", "y"]
        rows = list(dr)
        std_dr = csv_stdlib.DictReader(io.StringIO(text))
        std_dr.fieldnames = ["x", "y"]
        std_rows = list(std_dr)
        assert rows == std_rows

    def test_skips_blank_rows(self):
        """DictReader skips rows that are completely empty."""
        text = "a,b\r\n\r\n\r\n1,2\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text)))
        mod = list(csv_mod.DictReader(io.StringIO(text)))
        assert mod == std
        assert len(mod) == 1

    def test_empty_file(self):
        """DictReader on empty file yields nothing."""
        rows = list(csv_mod.DictReader(io.StringIO("")))
        assert rows == []

    def test_empty_file_fieldnames_is_none(self):
        """On empty file, fieldnames is None."""
        dr = csv_mod.DictReader(io.StringIO(""))
        assert dr.fieldnames is None

    def test_line_num(self):
        text = "a,b\r\n1,2\r\n3,4\r\n"
        dr = csv_mod.DictReader(io.StringIO(text))
        next(dr)
        assert dr.line_num == 2
        next(dr)
        assert dr.line_num == 3

    def test_line_num_before_first_read(self):
        dr = csv_mod.DictReader(io.StringIO("a,b\r\n1,2\r\n"))
        assert dr.line_num == 0

    def test_dialect_kwarg(self):
        text = "a\tb\r\n1\t2\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text), dialect="excel-tab"))
        mod = list(csv_mod.DictReader(io.StringIO(text), dialect="excel-tab"))
        assert mod == std

    def test_class_getitem(self):
        """DictReader supports generic alias (PEP 585)."""
        try:
            alias = csv_mod.DictReader[str, str]
            assert alias is not None
        except TypeError:
            pytest.skip("DictReader generic alias not supported")


# ===========================================================================
# 11. DictWriter
# ===========================================================================

class TestDictWriter:

    def test_basic(self):
        buf_std = io.StringIO()
        w = csv_stdlib.DictWriter(buf_std, fieldnames=["name", "age"])
        w.writeheader()
        w.writerow({"name": "Alice", "age": 30})
        buf_mod = io.StringIO()
        w2 = csv_mod.DictWriter(buf_mod, fieldnames=["name", "age"])
        w2.writeheader()
        w2.writerow({"name": "Alice", "age": 30})
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writerows(self):
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        buf_std = io.StringIO()
        csv_stdlib.DictWriter(buf_std, fieldnames=["a", "b"]).writerows(rows)
        buf_mod = io.StringIO()
        csv_mod.DictWriter(buf_mod, fieldnames=["a", "b"]).writerows(rows)
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writerows_returns_none(self):
        buf = io.StringIO()
        result = csv_mod.DictWriter(buf, fieldnames=["a"]).writerows([{"a": 1}])
        assert result is None

    def test_extra_keys_raises(self):
        """By default, extra keys should raise ValueError."""
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["a"])
        with pytest.raises(ValueError):
            w.writerow({"a": 1, "b": 2})

    def test_extrasaction_ignore(self):
        buf_std = io.StringIO()
        w = csv_stdlib.DictWriter(
            buf_std, fieldnames=["a"], extrasaction="ignore"
        )
        w.writerow({"a": 1, "b": 2})
        buf_mod = io.StringIO()
        w2 = csv_mod.DictWriter(
            buf_mod, fieldnames=["a"], extrasaction="ignore"
        )
        w2.writerow({"a": 1, "b": 2})
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_extrasaction_invalid_raises(self):
        """Invalid extrasaction value raises ValueError."""
        with pytest.raises(ValueError):
            csv_mod.DictWriter(io.StringIO(), fieldnames=["a"], extrasaction="bad")

    def test_restval(self):
        buf_std = io.StringIO()
        w = csv_stdlib.DictWriter(
            buf_std, fieldnames=["a", "b", "c"], restval="N/A"
        )
        w.writerow({"a": 1})
        buf_mod = io.StringIO()
        w2 = csv_mod.DictWriter(
            buf_mod, fieldnames=["a", "b", "c"], restval="N/A"
        )
        w2.writerow({"a": 1})
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_writeheader_returns_value(self):
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["a", "b"])
        result = w.writeheader()
        buf2 = io.StringIO()
        w2 = csv_stdlib.DictWriter(buf2, fieldnames=["a", "b"])
        expected = w2.writeheader()
        assert result == expected

    def test_writerow_returns_char_count(self):
        """DictWriter.writerow returns the char count like writer.writerow."""
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["a", "b"])
        result = w.writerow({"a": "1", "b": "2"})
        buf2 = io.StringIO()
        w2 = csv_stdlib.DictWriter(buf2, fieldnames=["a", "b"])
        expected = w2.writerow({"a": "1", "b": "2"})
        assert result == expected

    def test_fieldname_order_preserved(self):
        """Fields are written in fieldnames order, not dict insertion order."""
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["b", "a"])
        w.writerow({"a": "1", "b": "2"})
        assert buf.getvalue() == "2,1\r\n"

    def test_dialect_kwarg(self):
        buf_std = io.StringIO()
        w = csv_stdlib.DictWriter(
            buf_std, fieldnames=["a", "b"], dialect="excel-tab"
        )
        w.writerow({"a": 1, "b": 2})
        buf_mod = io.StringIO()
        w2 = csv_mod.DictWriter(
            buf_mod, fieldnames=["a", "b"], dialect="excel-tab"
        )
        w2.writerow({"a": 1, "b": 2})
        assert buf_mod.getvalue() == buf_std.getvalue()

    def test_class_getitem(self):
        """DictWriter supports generic alias (PEP 585)."""
        try:
            alias = csv_mod.DictWriter[str, str]
            assert alias is not None
        except TypeError:
            pytest.skip("DictWriter generic alias not supported")


# ===========================================================================
# 12. field_size_limit
# ===========================================================================

class TestFieldSizeLimit:

    def test_get_default(self):
        std_limit = csv_stdlib.field_size_limit()
        mod_limit = csv_mod.field_size_limit()
        assert mod_limit == std_limit

    def test_default_value(self):
        """Default is 131072 (128 * 1024)."""
        assert csv_mod.field_size_limit() == 131072

    def test_set_and_get(self):
        old = csv_mod.field_size_limit()
        try:
            prev = csv_mod.field_size_limit(100)
            assert prev == old
            assert csv_mod.field_size_limit() == 100
        finally:
            csv_mod.field_size_limit(old)

    def test_returns_previous_value(self):
        """field_size_limit(new) returns the previous limit."""
        old = csv_mod.field_size_limit()
        try:
            csv_mod.field_size_limit(999)
            ret = csv_mod.field_size_limit(888)
            assert ret == 999
        finally:
            csv_mod.field_size_limit(old)

    def test_field_exceeding_limit_raises(self):
        old = csv_mod.field_size_limit()
        try:
            csv_mod.field_size_limit(5)
            with pytest.raises(csv_mod.Error):
                _read_from_string("abcdefghij\r\n", mod=csv_mod)
        finally:
            csv_mod.field_size_limit(old)


# ===========================================================================
# 13. EDGE CASES & TORTURE TESTS
# ===========================================================================

class TestEdgeCases:

    def test_field_is_just_a_quote(self):
        assert_same_as_stdlib([['\"']])

    def test_field_is_two_quotes(self):
        assert_same_as_stdlib([['""']])

    def test_field_is_three_quotes(self):
        assert_same_as_stdlib([['"""']])

    def test_empty_quoted_field(self):
        roundtrip_matches_stdlib('""\r\n')

    def test_field_with_only_whitespace(self):
        assert_same_as_stdlib([["   "]])

    def test_field_with_tabs(self):
        assert_same_as_stdlib([["a\tb"]])

    def test_field_with_null_byte(self):
        assert_same_as_stdlib([["a\x00b"]])

    def test_large_field(self):
        big = "x" * 50_000
        assert_same_as_stdlib([[big]])

    def test_many_columns(self):
        row = [str(i) for i in range(500)]
        assert_same_as_stdlib([row])

    def test_many_rows(self):
        rows = [[str(i), str(i + 1)] for i in range(1000)]
        assert_same_as_stdlib(rows)

    def test_unicode_basic(self):
        assert_same_as_stdlib([["café", "naïve", "résumé"]])

    def test_unicode_cjk(self):
        assert_same_as_stdlib([["你好", "世界"]])

    def test_unicode_emoji(self):
        assert_same_as_stdlib([["😀", "🎉", "🚀"]])

    def test_unicode_rtl(self):
        assert_same_as_stdlib([["مرحبا", "عالم"]])

    def test_unicode_surrogate_pair(self):
        """4-byte emoji / supplementary plane character."""
        assert_same_as_stdlib([["𝄞", "𝕳𝖊𝖑𝖑𝖔"]])

    def test_bom_handling(self):
        """UTF-8 BOM at start of file."""
        text = "\ufeffa,b\r\n1,2\r\n"
        roundtrip_matches_stdlib(text)

    def test_field_with_all_special_chars(self):
        assert_same_as_stdlib([['hello,"world"\nfoo']])

    def test_consecutive_delimiters(self):
        roundtrip_matches_stdlib(",,,,\r\n")

    def test_only_newlines(self):
        roundtrip_matches_stdlib("\r\n\r\n\r\n")

    def test_quoted_field_ending_with_newline(self):
        roundtrip_matches_stdlib('"hello\n"\r\n')

    def test_quoted_field_with_only_newline(self):
        roundtrip_matches_stdlib('"\n"\r\n')

    def test_quoted_field_with_only_crlf(self):
        roundtrip_matches_stdlib('"\r\n"\r\n')

    def test_mixed_quoted_unquoted(self):
        roundtrip_matches_stdlib('a,"b,c",d\r\n')

    def test_backslash_in_field(self):
        assert_same_as_stdlib([["a\\b", "c"]])

    def test_single_quote_in_field(self):
        assert_same_as_stdlib([["it's", "here"]])

    def test_very_long_quoted_field_with_newlines(self):
        field = "line\n" * 200
        assert_same_as_stdlib([[field, "end"]])

    def test_single_column_file(self):
        roundtrip_matches_stdlib("a\r\nb\r\nc\r\n")

    def test_field_with_only_delimiter(self):
        assert_same_as_stdlib([[","]])

    def test_field_with_only_quotechar(self):
        assert_same_as_stdlib([['"']])

    def test_field_with_only_lineterminator(self):
        assert_same_as_stdlib([["\r\n"]])


# ===========================================================================
# 14. FILE I/O (real file, not StringIO)
# ===========================================================================

class TestFileIO:

    def test_write_and_read_file(self):
        rows = [["name", "value"], ["alpha", "1"], ["beta", "2"]]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            w = csv_mod.writer(f)
            w.writerows(rows)
            path = f.name
        try:
            with open(path, newline="") as f:
                result = list(csv_mod.reader(f))
            assert result == rows
        finally:
            os.unlink(path)

    def test_file_matches_stdlib(self):
        rows = [["a,b", 'c"d', "e\nf"]]
        # Write with stdlib
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            csv_stdlib.writer(f).writerows(rows)
            path_std = f.name
        # Write with module
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            csv_mod.writer(f).writerows(rows)
            path_mod = f.name
        try:
            with open(path_std) as f1, open(path_mod) as f2:
                assert f1.read() == f2.read()
        finally:
            os.unlink(path_std)
            os.unlink(path_mod)


# ===========================================================================
# 15. SNIFFER (csv.Sniffer)
# ===========================================================================

class TestSniffer:

    @pytest.fixture
    def sniffer(self):
        if not hasattr(csv_mod, "Sniffer"):
            pytest.skip("Sniffer not implemented")
        return csv_mod.Sniffer()

    def test_sniff_comma(self, sniffer):
        d = sniffer.sniff("a,b,c\r\n1,2,3\r\n")
        assert d.delimiter == ","

    def test_sniff_tab(self, sniffer):
        d = sniffer.sniff("a\tb\tc\r\n1\t2\t3\r\n")
        assert d.delimiter == "\t"

    def test_sniff_semicolon(self, sniffer):
        d = sniffer.sniff("a;b;c\r\n1;2;3\r\n")
        assert d.delimiter == ";"

    def test_sniff_pipe(self, sniffer):
        d = sniffer.sniff("a|b|c\r\n1|2|3\r\n")
        assert d.delimiter == "|"

    def test_sniff_returns_dialect_subclass(self, sniffer):
        """sniff() returns a class (not instance) that is a Dialect subclass."""
        result = sniffer.sniff("a,b\r\n1,2\r\n")
        assert isinstance(result, type)
        assert issubclass(result, csv_mod.Dialect)

    def test_sniff_with_delimiters_param(self, sniffer):
        """delimiters param restricts which characters are considered."""
        d = sniffer.sniff("a;b;c\r\n1;2;3\r\n", delimiters=";|")
        assert d.delimiter == ";"

    def test_sniff_raises_on_empty(self, sniffer):
        """Raises Error when input is empty and delimiter cannot be determined."""
        with pytest.raises(csv_mod.Error):
            sniffer.sniff("")

    def test_sniff_delimiters_no_match_raises(self, sniffer):
        """Raises Error when no delimiter in delimiters param matches."""
        with pytest.raises(csv_mod.Error):
            sniffer.sniff("a,b\r\n1,2\r\n", delimiters="|;")

    def test_sniff_doublequote_detection(self, sniffer):
        d = sniffer.sniff('"a""b",c\r\n"d""e",f\r\n')
        assert d.doublequote is True

    def test_sniff_skipinitialspace_detection(self, sniffer):
        d = sniffer.sniff('"a", "b", "c"\r\n"1", "2", "3"\r\n')
        assert d.skipinitialspace is True

    def test_has_header_true(self, sniffer):
        sample = "name,age,city\r\nAlice,30,NYC\r\nBob,25,LA\r\n"
        assert sniffer.has_header(sample) is True

    def test_has_header_false(self, sniffer):
        sample = "1,2,3\r\n4,5,6\r\n7,8,9\r\n"
        assert sniffer.has_header(sample) is False

    def test_sniff_result_usable_by_reader(self, sniffer):
        """The dialect returned by sniff() can be used directly by reader()."""
        sample = "a;b;c\r\n1;2;3\r\n"
        dialect = sniffer.sniff(sample)
        rows = list(csv_mod.reader(io.StringIO(sample), dialect))
        assert rows == [["a", "b", "c"], ["1", "2", "3"]]


# ===========================================================================
# 16. ERROR HANDLING
# ===========================================================================

class TestErrors:

    def test_writer_on_non_writable(self):
        """Writer must accept any object with write()."""
        with pytest.raises((TypeError, AttributeError, csv_mod.Error)):
            csv_mod.writer(42)

    def test_reader_on_non_iterable(self):
        with pytest.raises((TypeError, csv_mod.Error)):
            list(csv_mod.reader(42))

    def test_bad_quoting_value(self):
        with pytest.raises((TypeError, ValueError, csv_mod.Error)):
            _write_to_string([["a"]], mod=csv_mod, quoting=999)

    def test_delimiter_must_be_single_char(self):
        with pytest.raises((TypeError, csv_mod.Error)):
            _write_to_string([["a"]], mod=csv_mod, delimiter=",,")

    def test_quotechar_must_be_single_char(self):
        with pytest.raises((TypeError, csv_mod.Error)):
            _write_to_string([["a"]], mod=csv_mod, quotechar="''")

    def test_quote_none_without_escapechar_on_special(self):
        """QUOTE_NONE with a field that needs quoting but no escapechar."""
        with pytest.raises(csv_mod.Error):
            _write_to_string(
                [["a,b"]], mod=csv_mod, quoting=csv_mod.QUOTE_NONE
            )

    def test_delimiter_none_raises(self):
        with pytest.raises((TypeError, csv_mod.Error)):
            _write_to_string([["a"]], mod=csv_mod, delimiter=None)

    def test_writerow_with_non_iterable(self):
        """writerow with a non-iterable argument raises."""
        buf = io.StringIO()
        w = csv_mod.writer(buf)
        with pytest.raises((TypeError, csv_mod.Error)):
            w.writerow(42)


# ===========================================================================
# 17. ITERATOR PROTOCOL DETAILS
# ===========================================================================

class TestIteratorProtocol:

    def test_reader_stops_iteration(self):
        r = csv_mod.reader(io.StringIO("a\r\n"))
        next(r)
        with pytest.raises(StopIteration):
            next(r)

    def test_reader_works_in_for_loop(self):
        rows = []
        for row in csv_mod.reader(io.StringIO("a,b\r\nc,d\r\n")):
            rows.append(row)
        assert rows == [["a", "b"], ["c", "d"]]

    def test_dictreader_works_in_for_loop(self):
        text = "x,y\r\n1,2\r\n"
        rows = list(csv_mod.DictReader(io.StringIO(text)))
        assert len(rows) == 1
        assert rows[0]["x"] == "1"

    def test_dictreader_stops_iteration(self):
        dr = csv_mod.DictReader(io.StringIO("a\r\n1\r\n"))
        next(dr)
        with pytest.raises(StopIteration):
            next(dr)

    def test_dictreader_is_iterator(self):
        dr = csv_mod.DictReader(io.StringIO("a\r\n1\r\n"))
        assert iter(dr) is dr


# ===========================================================================
# 18. WRITER dialect ATTRIBUTE
# ===========================================================================

class TestWriterDialectAttr:

    def test_writer_has_dialect(self):
        buf = io.StringIO()
        w = csv_mod.writer(buf)
        assert hasattr(w, "dialect")

    def test_writer_dialect_reflects_params(self):
        buf = io.StringIO()
        w = csv_mod.writer(buf, delimiter="|")
        assert w.dialect.delimiter == "|"

    def test_writer_dialect_reflects_quoting(self):
        buf = io.StringIO()
        w = csv_mod.writer(buf, quoting=csv_mod.QUOTE_ALL)
        assert w.dialect.quoting == csv_mod.QUOTE_ALL


# ===========================================================================
# 19. ROUNDTRIP INTEGRITY
# ===========================================================================

class TestRoundtrip:
    """Verify that write → read produces the original data."""

    @pytest.mark.parametrize(
        "rows",
        [
            [["simple", "row"]],
            [["with,comma", "ok"]],
            [['with"quote', "ok"]],
            [["with\nnewline", "ok"]],
            [["with\r\ncrlf", "ok"]],
            [["", ""]],
            [["a", "b"], ["c", "d"], ["e", "f"]],
            [[str(i) for i in range(100)]],
            [["café", "naïve"]],
            [["emoji: 🎉", "done"]],
            [['all,special"\nchars\r\n', "end"]],
            [[None]],  # None → "" → ""
        ],
        ids=[
            "simple",
            "comma",
            "quote",
            "newline",
            "crlf",
            "empty_fields",
            "multi_row",
            "wide_row",
            "unicode",
            "emoji",
            "all_specials",
            "none_field",
        ],
    )
    def test_roundtrip(self, rows):
        result = _write_and_read(rows, mod=csv_mod)
        # None becomes "" on write, which reads back as ""
        expected = [
            [("" if v is None else v) for v in row] for row in rows
        ]
        assert result == expected

    @pytest.mark.parametrize(
        "rows",
        [
            [["simple", "row"]],
            [["with,comma", "ok"]],
            [['with"quote', "ok"]],
            [["with\nnewline", "ok"]],
        ],
        ids=["simple", "comma", "quote", "newline"],
    )
    def test_roundtrip_quote_all(self, rows):
        result = _write_and_read(
            rows, mod=csv_mod, quoting=csv_mod.QUOTE_ALL
        )
        assert result == rows

    def test_roundtrip_unix_dialect(self):
        rows = [["a", "b"], ["c", "d"]]
        buf = io.StringIO()
        w = csv_mod.writer(buf, dialect="unix")
        w.writerows(rows)
        buf.seek(0)
        result = list(csv_mod.reader(buf, dialect="unix"))
        assert result == rows


# ===========================================================================
# 20. INTEROP: write with stdlib, read with module (and vice versa)
# ===========================================================================

class TestInterop:
    """The replacement module must read what stdlib writes,
    and stdlib must read what the module writes."""

    @pytest.mark.parametrize(
        "rows",
        [
            [["a", "b", "c"]],
            [["hello,world", 'say"what', "new\nline"]],
            [["", "", ""]],
            [["café", "日本語"]],
            [[None, 42, True, 3.14]],
        ],
        ids=["simple", "special_chars", "empty", "unicode", "mixed_types"],
    )
    def test_stdlib_writes_module_reads(self, rows):
        csv_str = _write_to_string(rows, mod=csv_stdlib)
        mod_rows = _read_from_string(csv_str, mod=csv_mod)
        std_rows = _read_from_string(csv_str, mod=csv_stdlib)
        assert mod_rows == std_rows

    @pytest.mark.parametrize(
        "rows",
        [
            [["a", "b", "c"]],
            [["hello,world", 'say"what', "new\nline"]],
            [["", "", ""]],
            [["café", "日本語"]],
            [[None, 42, True, 3.14]],
        ],
        ids=["simple", "special_chars", "empty", "unicode", "mixed_types"],
    )
    def test_module_writes_stdlib_reads(self, rows):
        csv_str = _write_to_string(rows, mod=csv_mod)
        std_rows = _read_from_string(csv_str, mod=csv_stdlib)
        mod_rows = _read_from_string(csv_str, mod=csv_mod)
        assert mod_rows == std_rows


# ===========================================================================
# 21. REGRESSION: known tricky patterns
# ===========================================================================

class TestRegressions:

    def test_crlf_inside_quoted_followed_by_crlf_row_end(self):
        """A quoted field containing \\r\\n followed by a \\r\\n row terminator."""
        text = '"a\r\nb"\r\nc\r\n'
        roundtrip_matches_stdlib(text)

    def test_quote_at_very_end_of_input(self):
        roundtrip_matches_stdlib('"hello"')

    def test_row_with_single_empty_quoted_field(self):
        roundtrip_matches_stdlib('""')

    def test_multiple_adjacent_quoted_empty_fields(self):
        roundtrip_matches_stdlib('"","",""\r\n')

    def test_field_ending_with_escaped_quote(self):
        roundtrip_matches_stdlib('"test"""\r\n')

    def test_field_starting_with_escaped_quote(self):
        roundtrip_matches_stdlib('"""test"\r\n')

    def test_only_quotes_in_quoted_field(self):
        roundtrip_matches_stdlib('""""""\r\n')  # three escaped quotes

    def test_newline_at_end_of_quoted_field(self):
        roundtrip_matches_stdlib('"abc\n"\r\n')

    def test_windows_path(self):
        assert_same_as_stdlib([["C:\\Users\\test\\file.txt"]])

    def test_url_field(self):
        assert_same_as_stdlib([["https://example.com?a=1&b=2"]])

    def test_json_in_field(self):
        assert_same_as_stdlib([['{"key": "value", "n": 42}']])

    def test_html_in_field(self):
        assert_same_as_stdlib([["<b>bold</b>"]])

    def test_sql_in_field(self):
        assert_same_as_stdlib([["SELECT * FROM t WHERE x='hello'"]])

    def test_csv_injection_formula(self):
        """Fields starting with =, +, -, @ (potential CSV injection)."""
        assert_same_as_stdlib([["=1+1", "+cmd", "-flag", "@SUM(A1)"]])

    def test_field_with_formfeed(self):
        assert_same_as_stdlib([["a\x0cb"]])

    def test_field_with_vertical_tab(self):
        assert_same_as_stdlib([["a\x0bb"]])

    def test_field_with_bell(self):
        assert_same_as_stdlib([["a\x07b"]])

    def test_field_with_backspace(self):
        assert_same_as_stdlib([["a\x08b"]])

    def test_extremely_nested_quotes(self):
        """Field value is a single double-quote repeated many times."""
        val = '"' * 50
        assert_same_as_stdlib([[val]])

    def test_quoted_field_followed_by_empty_field(self):
        roundtrip_matches_stdlib('"hello",\r\n')

    def test_empty_field_followed_by_quoted_field(self):
        roundtrip_matches_stdlib(',"hello"\r\n')

    def test_only_whitespace_rows(self):
        roundtrip_matches_stdlib(" \r\n  \r\n")

    def test_tab_as_whitespace_in_field(self):
        roundtrip_matches_stdlib('\t,\t\r\n')


# ===========================================================================
# 22. ESCAPECHAR EDGE CASES
# ===========================================================================

class TestEscapeCharEdgeCases:

    def test_escape_delimiter_with_quote_none(self):
        assert_same_as_stdlib(
            [["a,b"]], quoting=csv_mod.QUOTE_NONE, escapechar="\\"
        )

    def test_escape_escapechar_with_quote_none(self):
        """The escapechar itself should be escaped."""
        assert_same_as_stdlib(
            [["a\\b"]], quoting=csv_mod.QUOTE_NONE, escapechar="\\"
        )

    def test_escape_newline_with_quote_none(self):
        assert_same_as_stdlib(
            [["a\nb"]], quoting=csv_mod.QUOTE_NONE, escapechar="\\"
        )

    def test_escape_quotechar_doublequote_false(self):
        assert_same_as_stdlib(
            [['a"b']], doublequote=False, escapechar="\\"
        )

    def test_read_escaped_delimiter(self):
        """Reader should interpret escaped delimiters."""
        text = "a\\,b,c\r\n"
        std = _read_from_string(
            text, mod=csv_stdlib, escapechar="\\",
            quoting=csv_stdlib.QUOTE_NONE
        )
        mod = _read_from_string(
            text, mod=csv_mod, escapechar="\\",
            quoting=csv_mod.QUOTE_NONE
        )
        assert mod == std

    def test_read_escaped_quote_doublequote_false(self):
        text = '"a\\"b"\r\n'
        std = _read_from_string(
            text, mod=csv_stdlib, escapechar="\\", doublequote=False
        )
        mod = _read_from_string(
            text, mod=csv_mod, escapechar="\\", doublequote=False
        )
        assert mod == std


# ===========================================================================
# 23. UNIX DIALECT SPECIFIC
# ===========================================================================

class TestUnixDialect:

    def test_unix_uses_lf(self):
        s = _write_to_string([["a", "b"]], mod=csv_mod, dialect="unix")
        assert s.endswith("\n")
        assert "\r\n" not in s

    def test_unix_quotes_all(self):
        s = _write_to_string([["a", "b"]], mod=csv_mod, dialect="unix")
        assert s == '"a","b"\n'

    def test_unix_roundtrip(self):
        rows = [["a", "b"], ["c", "d"]]
        result = _write_and_read(rows, mod=csv_mod, dialect="unix")
        assert result == rows


# ===========================================================================
# 24. MULTIPLE WRITERS / READERS ON SAME BUFFER
# ===========================================================================

class TestMultipleWritersReaders:

    def test_two_writers_same_buffer(self):
        """Two writers writing to the same buffer sequentially."""
        buf = io.StringIO()
        w1 = csv_mod.writer(buf)
        w1.writerow(["a", "b"])
        w2 = csv_mod.writer(buf, delimiter=";")
        w2.writerow(["c", "d"])
        content = buf.getvalue()
        assert "a,b" in content
        assert "c;d" in content

    def test_write_then_read_same_buffer(self):
        buf = io.StringIO()
        csv_mod.writer(buf).writerow(["hello", "world"])
        buf.seek(0)
        rows = list(csv_mod.reader(buf))
        assert rows == [["hello", "world"]]


# ===========================================================================
# 25. DICT READER/WRITER WITH SPECIAL FIELDNAMES
# ===========================================================================

class TestDictSpecialFieldnames:

    def test_fieldname_with_comma(self):
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["a,b", "c"])
        w.writeheader()
        w.writerow({"a,b": "1", "c": "2"})
        buf.seek(0)
        rows = list(csv_mod.DictReader(buf))
        assert rows[0]["a,b"] == "1"

    def test_fieldname_with_quote(self):
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=['a"b', "c"])
        w.writeheader()
        w.writerow({'a"b': "1", "c": "2"})
        buf.seek(0)
        rows = list(csv_mod.DictReader(buf))
        assert rows[0]['a"b'] == "1"

    def test_empty_fieldname(self):
        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["", "b"])
        w.writeheader()
        w.writerow({"": "1", "b": "2"})
        buf.seek(0)
        rows = list(csv_mod.DictReader(buf))
        assert rows[0][""] == "1"

    def test_duplicate_fieldnames_dictreader(self):
        """DictReader with duplicate headers: last value wins."""
        text = "a,a\r\n1,2\r\n"
        std = list(csv_stdlib.DictReader(io.StringIO(text)))
        mod = list(csv_mod.DictReader(io.StringIO(text)))
        assert mod == std


# ===========================================================================
# 26. LARGE / STRESS TESTS
# ===========================================================================

class TestStress:

    def test_1mb_field(self):
        """Single field ~1MB in size."""
        big = "x" * (1024 * 1024)
        s_mod = _write_to_string([[big]], mod=csv_mod)
        s_std = _write_to_string([[big]], mod=csv_stdlib)
        assert s_mod == s_std

    def test_1000_columns_roundtrip(self):
        row = [f"col{i}" for i in range(1000)]
        assert _write_and_read([row], mod=csv_mod) == [row]

    def test_deeply_nested_quotes_roundtrip(self):
        """A field containing many escaped double-quotes."""
        val = 'x"' * 100 + "x"
        result = _write_and_read([[val]], mod=csv_mod)
        assert result == [[val]]

    def test_many_short_rows(self):
        rows = [[str(i)] for i in range(10_000)]
        s_mod = _write_to_string(rows, mod=csv_mod)
        s_std = _write_to_string(rows, mod=csv_stdlib)
        assert s_mod == s_std
