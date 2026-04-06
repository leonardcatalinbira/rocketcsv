"""Shadow tests for rocketcsv.DictReader — must match csv.DictReader exactly."""

from conftest import assert_shadow_dictread


class TestDictReaderBasic:
    def test_simple(self):
        assert_shadow_dictread("name,age\nAlice,30\nBob,25\n")

    def test_single_row(self):
        assert_shadow_dictread("a,b,c\n1,2,3\n")

    def test_empty_body(self):
        assert_shadow_dictread("a,b,c\n")


class TestDictReaderFieldnames:
    def test_custom_fieldnames(self):
        assert_shadow_dictread("1,2,3\n4,5,6\n", fieldnames=["a", "b", "c"])

    def test_extra_fields(self):
        assert_shadow_dictread("a,b\n1,2,3,4\n")

    def test_missing_fields(self):
        assert_shadow_dictread("a,b,c\n1,2\n")

    def test_restkey(self):
        assert_shadow_dictread("a,b\n1,2,3,4\n", restkey="_extra")

    def test_restval(self):
        assert_shadow_dictread("a,b,c\n1,2\n", restval="MISSING")
