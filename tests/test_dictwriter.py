"""Shadow tests for rocketcsv.DictWriter — must match csv.DictWriter exactly."""

from conftest import assert_shadow_dictwrite


class TestDictWriterBasic:
    def test_simple(self):
        rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        assert_shadow_dictwrite(rows, fieldnames=["name", "age"])

    def test_single_row(self):
        rows = [{"a": "1", "b": "2", "c": "3"}]
        assert_shadow_dictwrite(rows, fieldnames=["a", "b", "c"])

    def test_empty_rows(self):
        assert_shadow_dictwrite([], fieldnames=["a", "b", "c"])


class TestDictWriterRestval:
    def test_missing_key(self):
        rows = [{"a": "1", "b": "2"}]
        assert_shadow_dictwrite(rows, fieldnames=["a", "b", "c"], restval="N/A")


class TestDictWriterExtrasaction:
    def test_ignore_extras(self):
        rows = [{"a": "1", "b": "2", "extra": "x"}]
        assert_shadow_dictwrite(
            rows, fieldnames=["a", "b"], extrasaction="ignore"
        )
