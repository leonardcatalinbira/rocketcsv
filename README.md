# rocketcsv

**Rust-powered drop-in replacement for Python's `csv` module.**

Change one import line. Everything else stays the same. Your CSV code runs faster.

```python
# Before
import csv

# After
import rocketcsv as csv
```

That's it. Same `csv.reader()`, `csv.writer()`, `csv.DictReader`, `csv.DictWriter`. Same parameters. Same behavior. Faster.

> **Status: v0.1.0-alpha.1** — functional drop-in with per-column string interning, raw ffi object creation, and a Rust file-path fast path. Performance mode with lazy Rust-backed rows is in development.

## Benchmarks

Tested on files from 8 MB to 456 MB. Full methodology and all scenarios: **[BENCHMARKS.md](BENCHMARKS.md)**

### Drop-in mode (`import rocketcsv as csv`)

| Operation | Data | stdlib | rocketcsv | Speedup |
|-----------|------|--------|-----------|---------|
| reader() | 100K rows, 7.6 MB | 0.068s | 0.058s | **1.2x** |
| reader() | 5M rows, 456 MB | 24.35s | 8.76s | **2.8x** |
| DictReader() | 100K rows, 11.4 MB | 0.255s | 0.175s | **1.5x** |
| writer() | 100K mixed rows | 0.208s | 0.093s | **2.2x** |

### File path mode (`rocketcsv.reader_from_path()`)

Reads and parses entirely in Rust, bypassing Python IO:

| Data | stdlib `open()+reader()` | `reader_from_path()` | Speedup |
|------|--------------------------|----------------------|---------|
| 100K rows, 8 MB | 0.446s | 0.166s | **2.7x** |
| 100K quoted, 11 MB | 0.840s | 0.252s | **3.3x** |
| 1M narrow, 16 MB | 1.273s | 0.263s | **4.8x** |
| 5M rows, 456 MB | 7.89s | 3.09s | **2.6x** |

Reproduce yourself:

```bash
maturin develop --release
python benchmarks/bench_full.py
```

## Installation

```bash
pip install rocketcsv
```

Requires Python 3.9+. Pre-built wheels for Linux, macOS, and Windows.

## API

### Drop-in replacement (100% compatible with stdlib csv)

```python
import rocketcsv as csv

# These all work identically to stdlib
reader = csv.reader(open("data.csv"))
writer = csv.writer(open("out.csv", "w"))
dreader = csv.DictReader(open("data.csv"))
dwriter = csv.DictWriter(open("out.csv", "w"), fieldnames=["a", "b"])
```

### File path fast path (rocketcsv-only, faster)

```python
import rocketcsv

# Reads and parses entirely in Rust — no Python IO overhead
for row in rocketcsv.reader_from_path("data.csv"):
    process(row)  # row is a regular list[str]
```

### Full API surface

| Feature | Status |
|---------|--------|
| `reader()` | Done |
| `writer()` | Done |
| `DictReader` | Done |
| `DictWriter` | Done |
| `reader_from_path()` | Done (rocketcsv-only) |
| Dialect support | Done |
| All format parameters | Done |
| `QUOTE_*` constants | Done |
| `field_size_limit()` | Done |
| `Sniffer` | Planned |

All format parameters work identically to stdlib:
`delimiter`, `quotechar`, `escapechar`, `doublequote`, `skipinitialspace`, `lineterminator`, `quoting`, `strict`

## How It Works

The CSV parsing and formatting happens in Rust via the [csv crate](https://crates.io/crates/csv) by BurntSushi. Python bindings via [PyO3](https://pyo3.rs), packaged with [maturin](https://maturin.rs).

Key optimizations:
- **Per-column string interning** — adaptive HashMap caches repeated values (country codes, status fields), auto-disables on high-cardinality columns
- **Raw ffi object creation** — `PyUnicode_FromStringAndSize` + `PyList_SET_ITEM` skip bounds checks and intermediate Rust String allocations
- **File path fast path** — `reader_from_path()` reads entirely in Rust via `std::fs::read`, zero Python IO
- **Batched writer** — `writerows()` formats all rows in Rust, single `.write()` call to Python

## Testing

Every function is shadow-tested: the same operation runs on both `csv` (stdlib) and `rocketcsv`, and the outputs are asserted identical.

- **64 shadow tests** — reader, writer, DictReader, DictWriter
- **121 corpus files** — real-world CSVs from pandas, csvkit, agate, BurntSushi/rust-csv
- **96.6% corpus pass rate** — 4 known edge cases (BOM handling, blank line parity)
- Edge cases: multiline fields, Unicode, empty inputs, ragged rows, all format parameter combinations
- Round-trip verification (write then read through both implementations)

```bash
pytest tests/ -v                    # Shadow tests
python tests/corpus_runner.py       # Corpus validation
```

## Known Limitations (alpha)

- **UTF-8 BOM**: Rust csv crate auto-strips BOM, stdlib preserves it. 3 corpus files affected.
- **Blank lines between records**: Handled differently from stdlib. 1 corpus file affected.
- **Small files (<10K rows)**: PyO3 initialization overhead may make rocketcsv slower than stdlib. Gains appear at 50K+ rows.
- **Wide tables (500+ columns)**: Writer is slower due to per-row builder overhead. Being optimized.

## Why Not Polars / PyArrow?

Those are great tools — for DataFrames. But they change the API entirely. If you have existing code using `csv.reader()` or `csv.DictReader()`, switching to Polars means rewriting your code.

rocketcsv is for the millions of codebases that already use `import csv`. One line change, zero refactoring.

## License

rocketcsv is dual-licensed:

- **Open source**: [LGPLv3](LICENSE-LGPL) — free for use in any project, open or proprietary. You can `import rocketcsv` in commercial software without any obligation to open-source your application.

- **Commercial**: For companies that need to modify rocketcsv internals and keep changes private, or want warranty/support/indemnification. Contact for pricing.

## Contributing

Contributions welcome. Please ensure all shadow tests pass before submitting a PR.

```bash
pip install maturin pytest
maturin develop
pytest tests/ -v
```
