# rocketcsv

**The only Rust-backed drop-in replacement for Python's `csv` module.**

```python
# Before
import csv

# After — everything else stays the same
import rocketcsv as csv
```

Same `reader()`, `writer()`, `DictReader`, `DictWriter`. Same parameters. Same behavior. [376 compatibility tests](BENCHMARKS.md#corpus-shadow-test-results) prove it.

**Pass a file path instead of a file object — rocketcsv reads it entirely in Rust:**

```python
import rocketcsv as csv

# Pass a path string → auto-detects, reads in Rust (1.7-2.4x faster)
for row in csv.reader("data.csv"):
    process(row)

# Still works the classic way too (1.2-1.3x faster)
with open("data.csv") as f:
    for row in csv.reader(f):
        process(row)
```

One import change for an instant speedup. Pass a file path for the full Rust fast path. Same function, same API.

## Benchmarks

Tested on real-scale files up to 877 MB. Full methodology: **[BENCHMARKS.md](BENCHMARKS.md)**

### Drop-in mode (`import rocketcsv as csv`)

Zero code changes. Swap the import, get faster reads and writes.

| Scenario | Rows | stdlib | rocketcsv | Speedup |
|----------|------|--------|-----------|---------|
| reader() 100K rows, simple | 100K | 0.068s | 0.058s | **1.2x** |
| reader() 100K rows, quoted | 100K | 0.127s | 0.096s | **1.3x** |
| reader() 100K rows, mixed | 100K | 0.144s | 0.115s | **1.2x** |
| DictReader() 100K, quoted | 100K | 0.255s | 0.175s | **1.5x** |
| writer() 100K, mixed data | 100K | 0.208s | 0.093s | **2.2x** |

### File path mode (`reader_from_path`)

One line of code change. Reads and parses entirely in Rust.

| File | Rows | stdlib `open()+reader()` | `reader_from_path()` | Speedup |
|------|------|--------------------------|----------------------|---------|
| 175 MB | 2,000,000 | 4.66s | 3.32s | **1.4x** |
| 395 MB | 4,500,000 | 6.41s | 2.65s | **2.4x** |
| 877 MB | 10,000,000 | 12.13s | 7.20s | **1.7x** |

### Performance mode (`fast_reader_from_path`)

Lazy Rust-backed rows. Only touch the columns you need, skip everything else.

| File | Pattern | stdlib | fast_reader | Speedup |
|------|---------|--------|-------------|---------|
| 395 MB | Filter 1 column | 4.82s | 2.15s | **2.2x** |
| 877 MB | Access 1 of 10 cols | 10.77s | 5.01s | **2.2x** |
| 877 MB | Filter `row[3] == "active"` | 10.63s | 7.63s | **1.4x** |

### Writing — drop-in, same `csv.writer()` API

`writerows()` batches all formatting in Rust, then writes to your file in a single call.

```python
import rocketcsv as csv

with open("out.csv", "w", newline="") as f:
    w = csv.writer(f)            # same API, nothing new to learn
    w.writerows(rows)            # 2.2x faster on mixed data
```

| Scenario | Rows | stdlib | rocketcsv | Speedup |
|----------|------|--------|-----------|---------|
| Mixed types (strings, numbers, dates) | 100K | 0.208s | 0.093s | **2.2x** |
| Quoted fields (commas, newlines in data) | 100K | 0.127s | 0.096s | **1.3x** |
| Narrow table (2 cols, high row count) | 1M | 0.234s | 0.158s | **1.5x** |

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

Python 3.11+. Pre-built wheels for Linux, macOS, Windows.

## Three ways to read

```python
import rocketcsv as csv

# 1. Drop-in — swap one import, change nothing else (1.2-1.3x)
with open("data.csv") as f:
    for row in csv.reader(f):
        process(row)

# 2. Pass a path — auto-detects, reads in Rust (1.7-2.4x)
for row in csv.reader("data.csv"):
    process(row)

# 3. Performance mode — lazy rows, zero-cost unused columns (2.2x)
for row in rocketcsv.fast_reader_from_path("data.csv"):
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
