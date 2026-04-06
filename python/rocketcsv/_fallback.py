"""
Pure Python fallback — delegates to stdlib csv for unsupported platforms
where the Rust extension cannot be compiled.
"""

import csv as _csv

reader = _csv.reader
writer = _csv.writer
DictReader = _csv.DictReader
DictWriter = _csv.DictWriter
Error = _csv.Error
Dialect = _csv.Dialect

QUOTE_MINIMAL = _csv.QUOTE_MINIMAL
QUOTE_ALL = _csv.QUOTE_ALL
QUOTE_NONNUMERIC = _csv.QUOTE_NONNUMERIC
QUOTE_NONE = _csv.QUOTE_NONE

register_dialect = _csv.register_dialect
unregister_dialect = _csv.unregister_dialect
get_dialect = _csv.get_dialect
list_dialects = _csv.list_dialects
field_size_limit = _csv.field_size_limit
