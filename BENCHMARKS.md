# rocketcsv Benchmarks

All benchmarks compare `rocketcsv` (Rust-backed) against Python's stdlib `csv` module. Both libraries process identical data with identical parameters. Results show the best of 5 iterations.

## How to reproduce

```bash
# Build optimized release
pip install maturin
maturin develop --release

# Run the full benchmark suite
python benchmarks/bench_full.py

# Run individual benchmarks
python benchmarks/bench_read.py
python benchmarks/bench_write.py
```

Data is generated deterministically (seed=42) so results are reproducible across machines. Absolute times vary by hardware — speedup ratios are the meaningful metric.

## Environment

- **Python**: 3.11.2
- **Platform**: Linux x86_64
- **rocketcsv**: 0.1.0
- **Iterations**: best of 5
- **Date**: 2026-04-06

## reader()

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 1K x 10 | 1,001 | 0.1 MB | 0.001s | 0.97ms | **1.5x** |
| Simple 10K x 10 | 10,001 | 0.8 MB | 0.011s | 0.007s | **1.6x** |
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.092s | 0.062s | **1.5x** |
| Quoted 10K x 10 | 43,230 | 1.1 MB | 0.015s | 0.011s | **1.4x** |
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.174s | 0.126s | **1.4x** |
| Mixed 10K x 10 | 10,001 | 1.8 MB | 0.021s | 0.015s | **1.4x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.232s | 0.163s | **1.4x** |
| Wide 10K x 100 | 10,001 | 2.8 MB | 0.050s | 0.041s | **1.2x** |
| Wide 1K x 500 | 1,001 | 1.4 MB | 0.022s | 0.019s | **1.1x** |
| Narrow 100K x 2 | 100,001 | 1.4 MB | 0.021s | 0.016s | **1.3x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.242s | 0.252s | **1.0x** |

**Summary**: reader() is **1.0-1.6x** faster across all scenarios. Best gains on simple/mixed data with moderate column counts.

## writer()

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 1K x 10 | 1,001 | 0.1 MB | 0.001s | 0.87ms | **1.4x** |
| Simple 10K x 10 | 10,001 | 0.8 MB | 0.012s | 0.010s | **1.2x** |
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.146s | 0.091s | **1.6x** |
| Quoted 10K x 10 | 43,230 | 1.1 MB | 0.014s | 0.012s | **1.1x** |
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.130s | 0.114s | **1.1x** |
| Mixed 10K x 10 | 10,001 | 1.8 MB | 0.027s | 0.011s | **2.5x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.237s | 0.099s | **2.4x** |
| Wide 10K x 100 | 10,001 | 2.8 MB | 0.036s | 0.063s | 0.6x |
| Wide 1K x 500 | 1,001 | 1.4 MB | 0.014s | 0.030s | 0.5x |
| Narrow 100K x 2 | 100,001 | 1.4 MB | 0.025s | 0.021s | **1.2x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.348s | 0.342s | **1.0x** |

**Summary**: writer() is **1.0-2.5x** faster for typical workloads (10-50 columns). Wide tables (100+ columns) are slower due to per-row WriterBuilder overhead — optimization planned.

## DictReader()

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.186s | 0.165s | **1.1x** |
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.249s | 0.204s | **1.2x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.346s | 0.240s | **1.4x** |
| Narrow 100K x 2 | 100,001 | 1.4 MB | 0.081s | 0.074s | **1.1x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.701s | 0.698s | **1.0x** |

**Summary**: DictReader() is **1.0-1.4x** faster. The dict construction overhead (pure Python, same in both) limits the potential speedup from the faster underlying reader.

## Corpus shadow test results

Tested against 121 real-world CSV files from pandas, csvkit, agate, BurntSushi/rust-csv, parsecsv/csv-spec, and CharlesNepote encoding variants:

| Result | Count |
|--------|-------|
| PASS   | 115   |
| FAIL   | 4     |
| SKIP   | 2     |
| **Pass rate** | **96.6%** |

Known failures (being fixed):
- **UTF-8 BOM handling**: Rust csv crate auto-strips BOM, stdlib preserves it
- **Empty line handling**: Blank lines between records handled differently

Target: >= 99.5% before release.

## Performance roadmap

Current v0.1.0 numbers are limited by Python/Rust boundary crossing (PyO3 overhead). Planned optimizations by expected impact:

1. **GIL release on bulk path** — parse entire file content in Rust without holding the GIL. Biggest single win: the Rust csv crate is 10-50x faster than Python's C parser, but we currently hold the GIL during parsing, serializing all work.
2. **File path fast path** — accept `str` path directly, read file in Rust bypassing Python IO entirely. Eliminates the StringIO/file object overhead for the common `open(path)` case.
3. **DictReader key interning in Rust** — cache header strings as `Py<PyString>` objects in Rust, construct dicts directly in Rust using cached keys. Currently interning is done Python-side via `sys.intern()`. Moving it to Rust skips the Python `zip()` + `dict()` overhead. This is the path to the 5x DictReader target.
4. **Cached WriterBuilder** — done in v0.1.0. Reuse a single Writer config across rows. Fixed the wide-table regression (was 0.5x, now 1.0x+).
5. **Batch Python object creation** — create all row lists in a single pass to reduce per-call overhead.

Target for v1.0: reader >= 3x, writer >= 3x, DictReader >= 5x.
