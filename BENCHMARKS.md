# rocketcsv Benchmarks

All benchmarks compare `rocketcsv` against Python's stdlib `csv` module on identical data with identical parameters. Times are single-run on large files, best-of-5 on small files.

## How to reproduce

```bash
pip install maturin
maturin develop --release
python benchmarks/bench_full.py
```

## Environment

- **Python**: 3.11.2 / 3.12.13
- **Platform**: Linux x86_64
- **rocketcsv**: 0.1.0-alpha.1
- **Date**: 2026-04-06

---

## Large file benchmarks (175 MB — 877 MB)

Mixed data: integers, strings, floats, status codes (5 values), dates. 10 columns.

### reader_from_path() — file path, drop-in compatible

Reads and parses entirely in Rust. Returns `list[str]` per row.

| File | Rows | stdlib `open()+reader()` | `reader_from_path()` | Speedup |
|------|------|--------------------------|----------------------|---------|
| 175 MB | 2,000,000 | 4.66s | 3.32s | **1.4x** |
| 395 MB | 4,500,000 | 6.41s | 2.65s | **2.4x** |
| 877 MB | 10,000,000 | 12.13s | 7.20s | **1.7x** |

### fast_reader_from_path() — performance mode, lazy rows

Field data stays in Rust. PyString created only when you access `row[i]`. Cross-row string interning for repeated values.

**Single column access** (filtering, lookup):

| File | Rows | stdlib | fast_reader | Speedup |
|------|------|--------|-------------|---------|
| 175 MB | 2,000,000 | 8.25s | 4.11s | **2.0x** |
| 395 MB | 4,500,000 | 4.90s | 2.72s | **1.8x** |
| 877 MB | 10,000,000 | 10.77s | 5.01s | **2.2x** |

**Filter pattern** (`if row[3] == "active"`):

| File | Rows | stdlib | fast_reader | Speedup |
|------|------|--------|-------------|---------|
| 175 MB | 2,000,000 | 8.25s | 4.11s | **2.0x** |
| 395 MB | 4,500,000 | 4.82s | 2.15s | **2.2x** |
| 877 MB | 10,000,000 | 10.63s | 7.63s | **1.4x** |

**3-column access** (selective read):

| File | Rows | stdlib | fast_reader | Speedup |
|------|------|--------|-------------|---------|
| 395 MB | 4,500,000 | 4.59s | 3.25s | **1.4x** |
| 877 MB | 10,000,000 | 9.88s | 8.14s | **1.2x** |

---

## Small/medium file benchmarks (best of 5)

### reader() via StringIO — drop-in compatible

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Simple 100K x 10 | 100,001 | 7.6 MB | 0.068s | 0.058s | **1.2x** |
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.127s | 0.096s | **1.3x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.144s | 0.115s | **1.2x** |

Note: For files over ~50 MB, use `reader_from_path()` instead of `reader(StringIO(...))`. The StringIO path copies the entire content Python→Rust, which dominates at large scale.

### writer() — batched writerows

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.208s | 0.093s | **2.2x** |
| Narrow 1M x 2 | 1,000,001 | 15.2 MB | 0.234s | 0.158s | **1.5x** |

### DictReader() via StringIO

| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |
|----------|------|------|--------|-----------|---------|
| Quoted 100K x 10 | 433,080 | 11.4 MB | 0.255s | 0.175s | **1.5x** |
| Mixed 100K x 10 | 100,001 | 18.4 MB | 0.227s | 0.170s | **1.3x** |

---

## Corpus shadow test results

119 real-world CSV files from pandas, csvkit, agate, BurntSushi/rust-csv, parsecsv, CharlesNepote:

| Result | Count |
|--------|-------|
| PASS   | 119   |
| FAIL   | 0     |
| **Pass rate** | **100%** |

---

## What makes it fast

1. **Rust file I/O** — `reader_from_path()` reads via `std::fs::read()`, zero Python I/O overhead
2. **Per-column string interning** — `HashMap<Box<[u8]>, *mut PyObject>` caches repeated values per column. Auto-disables on high-cardinality columns. Status codes, country names, categories get reused instead of re-allocated
3. **Lazy RocketRow** — `fast_reader()` keeps field data in Rust, creates PyString only on `__getitem__`. Fields you never access cost zero
4. **Raw ffi** — `PyUnicode_FromStringAndSize` from byte slices (no Rust String intermediate) + `PyList_SET_ITEM` (no bounds checks)
5. **Batched writer** — `writerows()` formats all rows in one Rust buffer, single `.write()` to Python

## Known performance limitations

- **StringIO at large scale** — `reader(StringIO(text))` copies the full content Python→Rust. For files >50 MB, use `reader_from_path()` instead
- **DictReader with file objects** — Same StringIO copy issue. For large files, prefer `reader_from_path()` + manual dict construction
- **Writer** — Faster on mixed/quoted data, roughly equal on simple data. Wide tables (500+ cols) may be slower
- **Small files (<10K rows)** — PyO3 init overhead may exceed the Rust speed gain. Crossover at ~50K rows

## Performance roadmap

| Optimization | Expected impact | Status |
|---|---|---|
| Rust file I/O (`reader_from_path`) | 1.4-2.4x on large files | Done |
| Per-column string interning | 2x+ on repetitive data | Done |
| Lazy RocketRow (`fast_reader`) | 1.4-2.2x on selective access | Done |
| Raw ffi PyList + PyUnicode | ~15% fewer allocations | Done |
| Batched writer | 1.5-2.2x on writerows | Done |
| GIL release on bulk path | 2-3x additional | Planned |
| Streaming file reader (avoid bulk copy) | Fix large-file DictReader | Planned |
| Rust-side DictReader with cached keys | 3-5x DictReader | Planned |
