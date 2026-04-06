"""
Benchmark: rocketcsv.writer() vs csv.writer()

Usage:
    python benchmarks/bench_write.py
"""

import csv
import io
import random
import string
import time

import rocketcsv


def generate_rows(n_rows, n_cols):
    """Generate random row data as list of lists."""
    rows = []
    for _ in range(n_rows):
        row = []
        for c in range(n_cols):
            kind = c % 3
            if kind == 0:
                row.append(str(random.randint(0, 999999)))
            elif kind == 1:
                row.append("".join(random.choices(string.ascii_lowercase, k=10)))
            else:
                row.append(f"{random.uniform(0, 100):.4f}")
        rows.append(row)
    return rows


def generate_rows_with_specials(n_rows, n_cols):
    """Generate rows that force quoting (commas, quotes, newlines)."""
    specials = ["hello, world", 'say "hi"', "line\nbreak", "normal"]
    rows = []
    for _ in range(n_rows):
        row = [random.choice(specials) for _ in range(n_cols)]
        rows.append(row)
    return rows


def bench_writer(label, rows, iterations=3, **kwargs):
    """Benchmark both writers."""
    # Warm up
    out = io.StringIO()
    csv.writer(out, **kwargs).writerows(rows)
    out = io.StringIO()
    rocketcsv.writer(out, **kwargs).writerows(rows)

    times_std = []
    for _ in range(iterations):
        out = io.StringIO()
        w = csv.writer(out, **kwargs)
        t0 = time.perf_counter()
        w.writerows(rows)
        times_std.append(time.perf_counter() - t0)

    times_fast = []
    for _ in range(iterations):
        out = io.StringIO()
        w = rocketcsv.writer(out, **kwargs)
        t0 = time.perf_counter()
        w.writerows(rows)
        times_fast.append(time.perf_counter() - t0)

    return min(times_std), min(times_fast)


if __name__ == "__main__":
    random.seed(42)

    scenarios = [
        ("Simple 10K x 10",    generate_rows(10_000, 10), {}),
        ("Simple 100K x 10",   generate_rows(100_000, 10), {}),
        ("Quoted 10K x 10",    generate_rows_with_specials(10_000, 10), {}),
        ("Quoted 100K x 10",   generate_rows_with_specials(100_000, 10), {}),
        ("QUOTE_ALL 100K x 10", generate_rows(100_000, 10), {"quoting": 1}),
    ]

    print("=" * 78)
    print(f"{'Scenario':<28} {'Rows':>8} {'stdlib':>10} {'rocket':>10} {'Speedup':>8}")
    print("=" * 78)

    for label, rows, kwargs in scenarios:
        std_t, fast_t = bench_writer(label, rows, **kwargs)
        speedup = std_t / fast_t if fast_t > 0 else float("inf")
        print(f"{label:<28} {len(rows):>8,} {std_t:>9.3f}s {fast_t:>9.3f}s {speedup:>7.1f}x")

    print("\n" + "=" * 78)
    print("Best of 3 iterations. Lower time = faster.")
    print("=" * 78)
