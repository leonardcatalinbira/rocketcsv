"""Shadow tests for rocketcsv.reader() — must match csv.reader() exactly."""

from conftest import assert_shadow_read


class TestReaderBasic:
    def test_simple_csv(self):
        assert_shadow_read("a,b,c\n1,2,3\n")

    def test_empty_input(self):
        assert_shadow_read("")

    def test_single_row(self):
        assert_shadow_read("a,b,c\n")

    def test_no_trailing_newline(self):
        assert_shadow_read("a,b,c")

    def test_multiple_rows(self):
        assert_shadow_read("a,b,c\n1,2,3\n4,5,6\n")

    def test_empty_fields(self):
        assert_shadow_read(",,\n")

    def test_single_field(self):
        assert_shadow_read("hello\n")

    def test_only_newline(self):
        assert_shadow_read("\n")


class TestReaderQuoting:
    def test_quoted_field(self):
        assert_shadow_read('a,"b,c",d\n')

    def test_quoted_field_with_newline(self):
        assert_shadow_read('a,"b\nc",d\n')

    def test_quoted_field_with_crlf(self):
        assert_shadow_read('a,"b\r\nc",d\n')

    def test_doubled_quotes(self):
        assert_shadow_read('a,"b""c",d\n')

    def test_empty_quoted_field(self):
        assert_shadow_read('a,"",d\n')

    def test_field_all_quotes(self):
        assert_shadow_read('a,"""",d\n')

    def test_field_starts_with_quote(self):
        assert_shadow_read('a,"""hello",d\n')

    def test_field_ends_with_quote(self):
        assert_shadow_read('a,"hello""",d\n')


class TestReaderWhitespace:
    def test_spaces_around_fields(self):
        assert_shadow_read(" a , b , c \n")

    def test_trailing_comma(self):
        assert_shadow_read("a,b,c,\n")

    def test_leading_comma(self):
        assert_shadow_read(",a,b,c\n")


class TestReaderLineEndings:
    def test_unix_endings(self):
        assert_shadow_read("a,b\nc,d\n")

    def test_windows_endings(self):
        assert_shadow_read("a,b\r\nc,d\r\n")

    def test_no_final_newline(self):
        assert_shadow_read("a,b\nc,d")


class TestReaderUnicode:
    def test_utf8(self):
        assert_shadow_read("caf\u00e9,na\u00efve,r\u00e9sum\u00e9\n")

    def test_cjk(self):
        assert_shadow_read("\u540d\u524d,\u4f4f\u6240\n\u592a\u90ce,\u6771\u4eac\n")

    def test_emoji(self):
        assert_shadow_read("\U0001f600,\U0001f389,\U0001f680\n")


class TestReaderFormatParams:
    def test_tab_delimiter(self):
        assert_shadow_read("a\tb\tc\n", delimiter="\t")

    def test_semicolon_delimiter(self):
        assert_shadow_read("a;b;c\n", delimiter=";")

    def test_pipe_delimiter(self):
        assert_shadow_read("a|b|c\n", delimiter="|")

    def test_single_quote_char(self):
        assert_shadow_read("a,'b,c',d\n", quotechar="'")

    def test_skipinitialspace(self):
        assert_shadow_read("a, b, c\n", skipinitialspace=True)


class TestReaderVariableColumns:
    def test_ragged_rows(self):
        assert_shadow_read("a,b\n1,2,3\n")

    def test_fewer_fields(self):
        assert_shadow_read("a,b,c\n1,2\n")
