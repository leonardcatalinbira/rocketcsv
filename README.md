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

## Benchmarks

Best of 5 iterations on 100K-row CSVs. Full results with all scenarios, DictReader, and corpus testing: **[BENCHMARKS.md](BENCHMARKS.md)**

| Operation | Scenario | stdlib | rocketcsv | Speedup |
|-----------|----------|--------|-----------|---------|
| reader() | Simple 100K x 10 | 0.092s | 0.062s | **1.5x** |
| reader() | Mixed 100K x 10 | 0.232s | 0.163s | **1.4x** |
| reader() | Quoted 100K x 10 | 0.174s | 0.126s | **1.4x** |
| writer() | Simple 100K x 10 | 0.146s | 0.091s | **1.6x** |
| writer() | Mixed 100K x 10 | 0.237s | 0.099s | **2.4x** |
| DictReader() | Mixed 100K x 10 | 0.346s | 0.240s | **1.4x** |

> v0.1.0 alpha — the Rust parsing core is 10-50x faster than Python, but the Python/Rust boundary crossing is the current bottleneck. Performance improves with every release. Target for v1.0: reader >= 3x, writer >= 3x, DictReader >= 5x.

Reproduce the benchmarks yourself:

```bash
maturin develop --release
python benchmarks/bench_full.py
```

## Installation

```bash
pip install rocketcsv
```

Requires Python 3.9+. Pre-built wheels for Linux, macOS, and Windows.

## Full API Compatibility

rocketcsv implements the complete `csv` module API:

| Feature | Status |
|---------|--------|
| `reader()` | Done |
| `writer()` | Done |
| `DictReader` | Done |
| `DictWriter` | Done |
| `Sniffer` | Planned |
| Dialect support | Done |
| All format parameters | Done |
| `QUOTE_*` constants | Done |
| `field_size_limit()` | Done |

All format parameters work identically to stdlib:
`delimiter`, `quotechar`, `escapechar`, `doublequote`, `skipinitialspace`, `lineterminator`, `quoting`, `strict`

## How It Works

The heavy lifting (CSV parsing and formatting) happens in Rust via the [csv crate](https://crates.io/crates/csv) by BurntSushi. Python bindings are built with [PyO3](https://pyo3.rs) and packaged with [maturin](https://maturin.rs).

- **reader()**: Bulk-reads file content into Rust, parses without the GIL, returns Python lists
- **writer()**: Batches rows, formats in Rust, writes to Python file in one call
- **DictReader/DictWriter**: Pure Python wrappers around the fast reader/writer

## Testing

Every function is shadow-tested: the same operation runs on both `csv` (stdlib) and `rocketcsv`, and the outputs are asserted identical. This includes:

- 64 shadow tests covering reader, writer, DictReader, DictWriter
- Edge cases: multiline fields, Unicode, empty inputs, ragged rows
- All format parameter combinations
- Round-trip verification (write then read)

```bash
pytest tests/ -v
```

## Why Not Polars / PyArrow?

Those are great tools — for DataFrames. But they change the API entirely. If you have existing code using `csv.reader()` or `csv.DictReader()`, switching to Polars means rewriting your code.

rocketcsv is for the millions of codebases that already use `import csv`. One line change, zero refactoring.

## License

rocketcsv is dual-licensed:

- **Open source**: [LGPLv3](LICENSE-LGPL) — free for use in any project, open or proprietary. You can `import rocketcsv` in commercial software without any obligation to open-source your application.

- **Commercial**: For companies that need to modify rocketcsv internals and keep changes private, or want warranty/support/indemnification. Contact for pricing.

## Contributing

Contributions are welcome. Please ensure all shadow tests pass before submitting a PR.

```bash
# Build from source
pip install maturin
maturin develop
pytest tests/ -v
```
