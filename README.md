# rocketcsv

**The only Rust-backed drop-in replacement for Python's `csv` module.**

```python
# Before
import csv

# After — everything else stays the same
import rocketcsv as csv
```

Same `reader()`, `writer()`, `DictReader`, `DictWriter`. Same parameters. Same behavior. [376 compatibility tests](BENCHMARKS.md#corpus-shadow-test-results) prove it.

## Benchmarks

Three levels of speed, depending on how much code you want to change. Tested up to 877 MB. Full details: **[BENCHMARKS.md](BENCHMARKS.md)**

### Level 1 — Change one import line (zero other code changes)

```python
import rocketcsv as csv          # swap this one line

with open("data.csv") as f:     # your existing code, untouched
    for row in csv.reader(f):
        process(row)
```

| Scenario | Rows | stdlib | rocketcsv | Speedup |
|----------|------|--------|-----------|---------|
| reader(), simple data | 100K | 0.068s | 0.058s | **1.2x** |
| reader(), quoted fields | 100K | 0.127s | 0.096s | **1.3x** |
| reader(), mixed types | 100K | 0.144s | 0.115s | **1.2x** |
| DictReader(), quoted | 100K | 0.255s | 0.175s | **1.5x** |
| writer(), mixed data | 100K | 0.208s | 0.093s | **2.2x** |

### Level 2 — Pass a file path instead of a file object

rocketcsv extends `reader()` to accept a string path. When it sees a path, it reads the file entirely in Rust — no Python file handling overhead. This is **not** how stdlib `csv.reader()` works (stdlib requires a file object), but it's one small code change:

```python
import rocketcsv as csv

# Before (stdlib-compatible):
# with open("data.csv") as f:
#     for row in csv.reader(f):

# After (rocketcsv extension — pass path directly):
for row in csv.reader("data.csv"):
    process(row)
```

| File | Rows | stdlib `open()+reader()` | rocketcsv `reader(path)` | Speedup |
|------|------|--------------------------|--------------------------|---------|
| 175 MB | 2,000,000 | 4.66s | 3.32s | **1.4x** |
| 395 MB | 4,500,000 | 6.41s | 2.65s | **2.4x** |
| 877 MB | 10,000,000 | 12.13s | 7.20s | **1.7x** |

### Level 3 — Performance mode (lazy Rust-backed rows)

`fast_reader_from_path()` returns `RocketRow` objects instead of `list[str]`. Field data stays in Rust — a PyString is only created when you access `row[i]`. Columns you never touch cost zero.

```python
import rocketcsv

for row in rocketcsv.fast_reader_from_path("data.csv"):
    if row[3] == "active":   # only this column is materialized
        print(row[0])         # and this one — the other 8 are free
```

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
# From GitHub (requires Rust toolchain)
pip install git+https://github.com/leonardcatalinbira/rocketcsv.git
```

PyPI release coming soon. Python 3.11+. Linux, macOS, Windows.

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
