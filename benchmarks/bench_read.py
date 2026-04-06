"""
Benchmark: rocketcsv.reader() vs csv.reader()

Generates CSVs of various sizes and profiles, runs both implementations,
and prints a comparison table with speedup ratios.

Usage:
    python benchmarks/bench_read.py
"""

import csv
import io
import random
import string
import time

import rocketcsv

# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def generate_numeric_csv(rows, cols):
    """Pure numeric data — common in scientific/financial workloads."""
    lines = []
    header = ",".join(f"col{i}" for i in range(cols))
    lines.append(header)
    for _ in range(rows):
        line = ",".join(f"{random.uniform(-1e6, 1e6):.6f}" for _ in range(cols))
        lines.append(line)
    return "\n".join(lines) + "\n"


def generate_mixed_csv(rows, cols):
    """Mixed types: strings, numbers, dates, empty fields."""
    lines = []
    header = ",".join(f"col{i}" for i in range(cols))
    lines.append(header)
    for r in range(rows):
        fields = []
        for c in range(cols):
            kind = c % 4
            if kind == 0:
                fields.append(f"{random.randint(0, 999999)}")
            elif kind == 1:
                word = "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 15)))
                fields.append(word)
            elif kind == 2:
                fields.append(f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}")
            else:
                fields.append("" if random.random() < 0.3 else f"{random.uniform(0,100):.2f}")
        lines.append(",".join(fields))
    return "\n".join(lines) + "\n"


def generate_quoted_csv(rows, cols):
    """Heavy quoting — fields contain commas, quotes, newlines."""
    lines = []
    header = ",".join(f"col{i}" for i in range(cols))
    lines.append(header)
    specials = [",", '"', "\n", "hello, world", 'say "hi"', "line\nbreak"]
    for _ in range(rows):
        fields = []
        for _ in range(cols):
            if random.random() < 0.4:
                fields.append(random.choice(specials))
            else:
                fields.append("".join(random.choices(string.ascii_letters, k=8)))
        row_text = []
        for f in fields:
            if any(c in f for c in (',', '"', '\n')):
                row_text.append('"' + f.replace('"', '""') + '"')
            else:
                row_text.append(f)
        lines.append(",".join(row_text))
    return "\n".join(lines) + "\n"


def generate_wide_csv(rows, cols):
    """Wide CSV — many columns, short values."""
    lines = []
    header = ",".join(f"c{i}" for i in range(cols))
    lines.append(header)
    for _ in range(rows):
        line = ",".join(str(random.randint(0, 99)) for _ in range(cols))
        lines.append(line)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def bench_reader(label, data, iterations=3):
    """Benchmark both readers, return (stdlib_time, rocket_time) in seconds."""
    # Warm up
    list(csv.reader(io.StringIO(data)))
    list(rocketcsv.reader(io.StringIO(data)))

    # stdlib
    times_std = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for row in csv.reader(io.StringIO(data)):
            pass
        times_std.append(time.perf_counter() - t0)

    # rocketcsv
    times_fast = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for row in rocketcsv.reader(io.StringIO(data)):
            pass
        times_fast.append(time.perf_counter() - t0)

    std_best = min(times_std)
    fast_best = min(times_fast)
    return std_best, fast_best


def bench_dictreader(label, data, iterations=3):
    """Benchmark both DictReaders."""
    list(csv.DictReader(io.StringIO(data)))
    list(rocketcsv.DictReader(io.StringIO(data)))

    times_std = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for row in csv.DictReader(io.StringIO(data)):
            pass
        times_std.append(time.perf_counter() - t0)

    times_fast = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for row in rocketcsv.DictReader(io.StringIO(data)):
            pass
        times_fast.append(time.perf_counter() - t0)

    return min(times_std), min(times_fast)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    random.seed(42)

    scenarios = [
        ("Numeric 10K x 10",    generate_numeric_csv(10_000, 10)),
        ("Numeric 100K x 10",   generate_numeric_csv(100_000, 10)),
        ("Mixed 10K x 10",      generate_mixed_csv(10_000, 10)),
        ("Mixed 100K x 10",     generate_mixed_csv(100_000, 10)),
        ("Quoted 10K x 10",     generate_quoted_csv(10_000, 10)),
        ("Quoted 100K x 10",    generate_quoted_csv(100_000, 10)),
        ("Wide 10K x 100",      generate_wide_csv(10_000, 100)),
        ("Wide 1K x 500",       generate_wide_csv(1_000, 500)),
    ]

    print("=" * 78)
    print(f"{'Scenario':<25} {'Rows':>8} {'Size':>8} {'stdlib':>10} {'rocket':>10} {'Speedup':>8}")
    print("=" * 78)

    # reader() benchmarks
    print("\n--- csv.reader() ---\n")
    for label, data in scenarios:
        row_count = data.count("\n") - 1
        size_mb = len(data.encode()) / (1024 * 1024)
        std_t, fast_t = bench_reader(label, data)
        speedup = std_t / fast_t if fast_t > 0 else float("inf")
        print(f"{label:<25} {row_count:>8,} {size_mb:>7.1f}M {std_t:>9.3f}s {fast_t:>9.3f}s {speedup:>7.1f}x")

    # DictReader benchmarks
    print("\n--- csv.DictReader() ---\n")
    dict_scenarios = scenarios[:4]  # subset for DictReader
    for label, data in dict_scenarios:
        row_count = data.count("\n") - 1
        size_mb = len(data.encode()) / (1024 * 1024)
        std_t, fast_t = bench_dictreader(label, data)
        speedup = std_t / fast_t if fast_t > 0 else float("inf")
        print(f"{label:<25} {row_count:>8,} {size_mb:>7.1f}M {std_t:>9.3f}s {fast_t:>9.3f}s {speedup:>7.1f}x")

    print("\n" + "=" * 78)
    print("Best of 3 iterations. Lower time = faster. Speedup = stdlib / rocketcsv.")
    print("=" * 78)
