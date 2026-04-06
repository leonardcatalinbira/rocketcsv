"""Tests for rocketcsv.fast_reader() — performance mode with lazy RocketRow."""

import csv
import io
import os
import tempfile

import rocketcsv


class TestFastReaderCorrectness:
    """Verify fast_reader output matches stdlib csv.reader."""

    def _assert_match(self, text, **kwargs):
        stdlib_rows = list(csv.reader(io.StringIO(text), **kwargs))
        fast_rows = [list(row) for row in rocketcsv.fast_reader(io.StringIO(text), **kwargs)]
        assert stdlib_rows == fast_rows, (
            f"Mismatch!\n  stdlib: {stdlib_rows}\n  fast:   {fast_rows}"
        )

    def test_simple(self):
        self._assert_match("a,b,c\n1,2,3\n")

    def test_empty(self):
        self._assert_match("")

    def test_quoted(self):
        self._assert_match('a,"b,c",d\n')

    def test_quoted_newline(self):
        self._assert_match('a,"b\nc",d\n')

    def test_doubled_quotes(self):
        self._assert_match('a,"b""c",d\n')

    def test_unicode(self):
        self._assert_match("caf\u00e9,\U0001f600,\u6771\u4eac\n")

    def test_multiple_rows(self):
        self._assert_match("a,b,c\n1,2,3\n4,5,6\n7,8,9\n")

    def test_empty_fields(self):
        self._assert_match(",,\n")

    def test_no_trailing_newline(self):
        self._assert_match("a,b,c")

    def test_tab_delimiter(self):
        self._assert_match("a\tb\tc\n", delimiter="\t")

    def test_ragged_rows(self):
        self._assert_match("a,b\n1,2,3\n")

    def test_fewer_fields(self):
        self._assert_match("a,b,c\n1,2\n")


class TestRocketRow:
    """Test RocketRow sequence protocol."""

    def _make_row(self, text="a,b,c\n"):
        rows = list(rocketcsv.fast_reader(io.StringIO(text)))
        return rows[0] if rows else None

    def test_len(self):
        row = self._make_row()
        assert len(row) == 3

    def test_getitem(self):
        row = self._make_row()
        assert row[0] == "a"
        assert row[1] == "b"
        assert row[2] == "c"

    def test_negative_index(self):
        row = self._make_row()
        assert row[-1] == "c"
        assert row[-3] == "a"

    def test_index_error(self):
        row = self._make_row()
        try:
            row[5]
            assert False, "Should raise IndexError"
        except IndexError:
            pass

    def test_contains(self):
        row = self._make_row()
        assert "a" in row
        assert "z" not in row

    def test_eq_list(self):
        row = self._make_row()
        assert row == ["a", "b", "c"]
        assert not (row == ["a", "b"])
        assert not (row == ["x", "y", "z"])

    def test_repr(self):
        row = self._make_row()
        r = repr(row)
        assert r == "['a', 'b', 'c']"

    def test_iter(self):
        row = self._make_row()
        assert list(row) == ["a", "b", "c"]

    def test_list_conversion(self):
        row = self._make_row()
        as_list = list(row)
        assert isinstance(as_list, list)
        assert as_list == ["a", "b", "c"]


class TestFastReaderFromPath:
    """Test fast_reader_from_path."""

    def test_basic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("x,y\n1,2\n3,4\n")
            path = f.name
        try:
            rows = [list(row) for row in rocketcsv.fast_reader_from_path(path)]
            assert rows == [["x", "y"], ["1", "2"], ["3", "4"]]
        finally:
            os.unlink(path)

    def test_matches_stdlib(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write('a,"b,c",d\n"e""f",g,h\n')
            path = f.name
        try:
            stdlib_rows = []
            with open(path, newline="") as fh:
                stdlib_rows = list(csv.reader(fh))
            fast_rows = [list(row) for row in rocketcsv.fast_reader_from_path(path)]
            assert stdlib_rows == fast_rows
        finally:
            os.unlink(path)
