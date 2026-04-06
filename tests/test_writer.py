"""Shadow tests for rocketcsv.writer() — must match csv.writer() exactly."""

from conftest import assert_shadow_write, assert_shadow_roundtrip


class TestWriterBasic:
    def test_simple_row(self):
        assert_shadow_write([["a", "b", "c"]])

    def test_multiple_rows(self):
        assert_shadow_write([["a", "b", "c"], ["1", "2", "3"]])

    def test_empty_row(self):
        assert_shadow_write([[]])

    def test_empty_fields(self):
        assert_shadow_write([["", "", ""]])

    def test_single_field(self):
        assert_shadow_write([["hello"]])


class TestWriterQuoting:
    def test_field_with_delimiter(self):
        assert_shadow_write([["a", "b,c", "d"]])

    def test_field_with_newline(self):
        assert_shadow_write([["a", "b\nc", "d"]])

    def test_field_with_quote(self):
        assert_shadow_write([["a", 'b"c', "d"]])

    def test_field_with_crlf(self):
        assert_shadow_write([["a", "b\r\nc", "d"]])

    def test_quote_all(self):
        assert_shadow_write([["a", "b", "c"]], quoting=1)  # QUOTE_ALL

    def test_quote_none_with_escape(self):
        assert_shadow_write(
            [["a", "b", "c"]], quoting=3, escapechar="\\"  # QUOTE_NONE
        )


class TestWriterFormatParams:
    def test_tab_delimiter(self):
        assert_shadow_write([["a", "b", "c"]], delimiter="\t")

    def test_semicolon_delimiter(self):
        assert_shadow_write([["a", "b", "c"]], delimiter=";")

    def test_lf_terminator(self):
        assert_shadow_write([["a", "b", "c"]], lineterminator="\n")

    def test_single_quote_char(self):
        assert_shadow_write([["a", "b,c", "d"]], quotechar="'")


class TestWriterRoundTrip:
    def test_basic_roundtrip(self):
        assert_shadow_roundtrip([["a", "b", "c"], ["1", "2", "3"]])

    def test_roundtrip_with_special_chars(self):
        assert_shadow_roundtrip([["hello, world", 'say "hi"', "line\nbreak"]])

    def test_roundtrip_empty_fields(self):
        assert_shadow_roundtrip([["", "a", ""], ["b", "", "c"]])

    def test_roundtrip_unicode(self):
        assert_shadow_roundtrip([["caf\u00e9", "\U0001f600", "\u6771\u4eac"]])
