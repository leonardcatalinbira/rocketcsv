# rocketcsv

**Drop one line of Rust into your Python CSV code. Get up to 2.4x faster reads.**

```python
# Before
import csv

# After — everything else stays the same
import rocketcsv as csv
```

Same `reader()`, `writer()`, `DictReader`, `DictWriter`. Same parameters. Same behavior. [376 compatibility tests](BENCHMARKS.md#corpus-shadow-test-results) prove it. Zero API changes, zero refactoring, zero new dependencies to learn.

For files you can point at directly, it gets faster:

```python
# 2.4x faster — reads entirely in Rust, no Python IO
for row in rocketcsv.reader_from_path("data.csv"):
    process(row)

# Even faster — fields stay in Rust, only materialize what you touch
for row in rocketcsv.fast_reader_from_path("data.csv"):
    if row[3] == "active":   # only this column is materialized
        print(row[0])         # and this one — the other 8 are free
```

## Benchmarks

Tested on real-scale files. Full methodology: **[BENCHMARKS.md](BENCHMARKS.md)**

### Reading large files

| File | API | stdlib | rocketcsv | Speedup |
|------|-----|--------|-----------|---------|
| 175 MB (2M rows) | `reader_from_path()` | 4.66s | 3.32s | **1.4x** |
| 395 MB (4.5M rows) | `reader_from_path()` | 6.41s | 2.65s | **2.4x** |
| 877 MB (10M rows) | `reader_from_path()` | 12.13s | 7.20s | **1.7x** |

### Selective access (performance mode)

Only touch the columns you need. Skip everything else.

| File | Pattern | stdlib | fast_reader | Speedup |
|------|---------|--------|-------------|---------|
| 395 MB | Filter 1 column | 4.82s | 2.15s | **2.2x** |
| 877 MB | Access 1 of 10 cols | 10.77s | 5.01s | **2.2x** |
| 877 MB | Filter `row[3] == "active"` | 10.63s | 7.63s | **1.4x** |

### Writing

| Scenario | stdlib | rocketcsv | Speedup |
|----------|--------|-----------|---------|
| 100K rows, mixed data | 0.208s | 0.093s | **2.2x** |
| 100K rows, quoted fields | 0.127s | 0.096s | **1.3x** |

### Compatibility

| Metric | Result |
|--------|--------|
| Compat tests (Python 3.12) | **376/376 pass** |
| Compat tests (Python 3.11) | **368/368 pass** (8 skip: 3.12 features) |
| Real-world corpus (121 files) | **100% pass** |

## Installation

```bash
pip install rocketcsv
```

Python 3.9+. Pre-built wheels for Linux, macOS, Windows.

## Three ways to read

```python
import rocketcsv

# 1. Drop-in — swap one import, change nothing else
import rocketcsv as csv
for row in csv.reader(open("data.csv")):  # returns list[str]
    process(row)

# 2. File path — reads entirely in Rust, skips Python IO
for row in rocketcsv.reader_from_path("data.csv"):  # returns list[str]
    process(row)

# 3. Performance mode — lazy rows, zero-cost unused columns
for row in rocketcsv.fast_reader_from_path("data.csv"):  # returns RocketRow
    if row[2] == "IT":     # only this field is materialized
        name = row[0]       # and this one
        # row[1], row[3]..row[9] — never allocated
```

## Full API

Everything in `import csv` works in `import rocketcsv as csv`:

| Feature | Status |
|---------|--------|
| `reader()` / `writer()` | Drop-in compatible |
| `DictReader` / `DictWriter` | Drop-in compatible |
| `Sniffer` (sniff + has_header) | Drop-in compatible |
| Dialect support | Full (register, get, list, unregister) |
| All format parameters | Full (delimiter, quotechar, escapechar, doublequote, skipinitialspace, lineterminator, quoting, strict) |
| `QUOTE_*` constants | All 6 including 3.12+ (`QUOTE_STRINGS`, `QUOTE_NOTNULL`) |
| `field_size_limit()` | Enforced |
| `reader_from_path()` | rocketcsv-only, 1.4-2.4x faster |
| `fast_reader()` / `fast_reader_from_path()` | rocketcsv-only, lazy Rust-backed rows |

## How it works

CSV parsing happens in Rust via [BurntSushi's csv crate](https://crates.io/crates/csv). Python bindings via [PyO3](https://pyo3.rs). Packaged with [maturin](https://maturin.rs).

- **Per-column string interning** — repeated values (status codes, countries, categories) are cached as Python objects and reused across rows. Auto-disables on high-cardinality columns
- **Raw CPython ffi** — `PyUnicode_FromStringAndSize` + `PyList_SET_ITEM` skip intermediate allocations and bounds checks
- **Rust file I/O** — `reader_from_path()` uses `std::fs::read()`, bypassing Python's file handling entirely
- **Lazy RocketRow** — `fast_reader()` parses in Rust but defers Python object creation to `__getitem__`. Columns you never access cost zero
- **Batched writer** — `writerows()` formats everything in a single Rust buffer, one `.write()` call

## Why not Polars / PyArrow?

Those are great — for DataFrames. But they replace the API entirely. If your code uses `csv.reader()` or `csv.DictReader()`, switching to Polars means rewriting.

rocketcsv is for the millions of existing codebases that use `import csv`. One line change. Zero refactoring.

## License

Dual-licensed:

- **Open source**: [LGPLv3](LICENSE-LGPL) — use freely in any project, open or proprietary. `import rocketcsv` in commercial software with zero obligation to open-source your code.
- **Commercial**: For modifying rocketcsv internals privately, or for warranty/support/indemnification. Contact for pricing.

## Contributing

```bash
pip install maturin pytest
maturin develop
pytest tests/ -v   # 376 tests
```
