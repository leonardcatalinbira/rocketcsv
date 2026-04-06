# rocketcsv Benchmarks

All benchmarks compare `rocketcsv` against Python's stdlib `csv` module. Both libraries process identical data with identical parameters.

## How to reproduce

```bash
pip install maturin
maturin develop --release
python benchmarks/bench_full.py
```

Data is generated deterministically (seed=42). Absolute times vary by hardware — speedup ratios are the meaningful metric.

## Environment

- **Python**: 3.11.2
- **Platform**: Linux x86_64
- **rocketcsv**: 0.1.0-alpha.1
- **Iterations**: best of 5 (bench_full.py) or single run (large file tests)
- **Date**: 2026-04-06

## reader() — drop-in mode

Uses `rocketcsv.reader(io.StringIO(data))`, identical API to `csv.reader()`.

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.068s | 0.058s | **1.2x** |
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.127s | 0.096s | **1.3x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.144s | 0.115s | **1.2x** |
| Narrow 100K x 2 | 100,001 | 1.4 MB | 0.016s | 0.013s | **1.2x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.157s | 0.148s | **1.1x** |
| **Simple 5M x 10** | **5,000,001** | **456 MB** | **24.35s** | **8.76s** | **2.8x** |

Speedup increases with file size as string interning amortizes its overhead. At 456 MB the adaptive per-column cache hits its stride — repeated values (numbers in the same range, common strings) get reused instead of re-allocated.

**Note**: On small files (<10K rows), PyO3 initialization overhead may make rocketcsv slower than stdlib. The crossover point is around 50K rows.

## reader_from_path() — file path fast path

Reads and parses entirely in Rust via `std::fs::read()`. No Python IO, no StringIO, no GIL during file read. This is the fastest path available.

| Scenario | Rows | Size | stdlib `open()+reader()` | `reader_from_path()` | Speedup |
|----------|------|------|--------------------------|----------------------|---------|
| Simple 100K x 10 | 100,001 | 8 MB | 0.446s | 0.166s | **2.7x** |
| Quoted 100K x 10 | 100,001 | 11 MB | 0.840s | 0.252s | **3.3x** |
| Narrow 1M x 2 | 1,000,001 | 16 MB | 1.273s | 0.263s | **4.8x** |
| **Simple 5M x 10** | **5,000,001** | **456 MB** | **7.89s** | **3.09s** | **2.6x** |

## writer()

Uses batched `writerows()` — formats all rows in Rust, single `.write()` call to Python.

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.083s | 0.072s | **1.1x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.208s | 0.093s | **2.2x** |
| Narrow 100K x 2 | 100,001 | 1.4 MB | 0.025s | 0.016s | **1.6x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.234s | 0.158s | **1.5x** |

**Known limitation**: Wide tables (100+ columns) are currently slower due to per-row WriterBuilder overhead. Optimization planned.

## DictReader()

Pure Python wrapper around the Rust reader, with `sys.intern()` for header key strings.

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.255s | 0.175s | **1.5x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.227s | 0.170s | **1.3x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.653s | 0.543s | **1.2x** |
| **Simple 5M x 10** | **5,000,001** | **456 MB** | **14.04s** | **11.15s** | **1.3x** |

## Corpus shadow test results

Tested against 121 real-world CSV files from pandas, csvkit, agate, BurntSushi/rust-csv, parsecsv/csv-spec, and CharlesNepote encoding variants:

| Result | Count |
|--------|-------|
| PASS   | 115   |
| FAIL   | 4     |
| SKIP   | 2     |
| **Pass rate** | **96.6%** |

Known failures (documented, being fixed):
- UTF-8 BOM handling (3 files) — Rust csv crate auto-strips BOM, stdlib preserves it
- Blank line between records (1 file) — different empty-row semantics

Target: >= 99.5% before stable release.

## What's making it fast

1. **Per-column adaptive string interning** — `HashMap<Box<[u8]>, *mut PyObject>` caches repeated field values per column. Auto-disables on high-cardinality columns to avoid memory waste. At 5M rows with typical categorical data, this avoids millions of redundant `PyUnicode_FromStringAndSize` calls.
2. **Raw ffi object creation** — `PyUnicode_FromStringAndSize` from csv crate byte slices (no intermediate Rust String allocation) + `PyList_SET_ITEM` (no bounds checks or redundant refcounting).
3. **File path fast path** — `reader_from_path()` uses `std::fs::read()` + `Cursor<Vec<u8>>`, parsing stays entirely in Rust.
4. **Batched writer** — `writerows()` builds all output in a single Rust buffer, one `.write()` call to Python.

## Performance roadmap

| Optimization | Expected impact | Status |
|---|---|---|
| Per-column string interning | 2-5x on repetitive data | Done |
| Raw ffi PyList + PyUnicode | ~15% fewer allocations | Done |
| File path fast path | 2.7-4.8x vs open()+reader() | Done |
| Cached WriterBuilder | Fixed wide-table regression | Done |
| Lazy RocketRow (`fast_reader()`) | 5-50x on selective access | Planned |
| GIL release on bulk path | 2-3x additional on large files | Planned |
| Rust-side DictReader with cached keys | 3-5x DictReader | Planned |
