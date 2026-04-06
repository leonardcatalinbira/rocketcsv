#!/usr/bin/env python3
"""
Full benchmark suite for rocketcsv. Outputs structured results for BENCHMARKS.md.

Usage:
    python benchmarks/bench_full.py
"""

import csv
import io
import os
import platform
import random
import string
import sys
import time

import rocketcsv

random.seed(42)
ITERS = 5


def gen_simple(rows, cols):
    lines = [",".join(f"col{i}" for i in range(cols))]
    for _ in range(rows):
        parts = []
        for c in range(cols):
            if c % 2 == 0:
                parts.append(str(random.randint(0, 999999)))
            else:
                parts.append("".join(random.choices(string.ascii_lowercase, k=8)))
        lines.append(",".join(parts))
    return "\n".join(lines) + "\n"


def gen_quoted(rows, cols):
    specials = [",", '"', "\n", "hello, world", 'say "hi"', "a\nb"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"col{i}" for i in range(cols)])
    for _ in range(rows):
        w.writerow([random.choice(specials) + "".join(random.choices(string.ascii_lowercase, k=4)) for _ in range(cols)])
    return out.getvalue()


def gen_mixed(rows, cols):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"col{i}" for i in range(cols)])
    for _ in range(rows):
        row = []
        for c in range(cols):
            r = random.random()
            if r < 0.3:
                row.append("text, with comma")
            elif r < 0.4:
                row.append('quoted "word" here')
            else:
                row.append(str(random.uniform(-1000, 1000)))
        w.writerow(row)
    return out.getvalue()


def gen_wide(rows, cols):
    lines = [",".join(f"c{i}" for i in range(cols))]
    for _ in range(rows):
        lines.append(",".join(str(random.randint(0, 99)) for _ in range(cols)))
    return "\n".join(lines) + "\n"


def gen_narrow(rows):
    lines = ["key,value"]
    for i in range(rows):
        val = "".join(random.choices(string.ascii_lowercase, k=8))
        lines.append(f"{i},{val}")
    return "\n".join(lines) + "\n"


def bench_read(data):
    times_std = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        for row in csv.reader(io.StringIO(data)):
            pass
        times_std.append(time.perf_counter() - t0)

    times_fast = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        for row in rocketcsv.reader(io.StringIO(data)):
            pass
        times_fast.append(time.perf_counter() - t0)

    return min(times_std), min(times_fast)


def bench_write(data):
    rows = list(csv.reader(io.StringIO(data)))
    times_std = []
    for _ in range(ITERS):
        out = io.StringIO()
        w = csv.writer(out)
        t0 = time.perf_counter()
        w.writerows(rows)
        times_std.append(time.perf_counter() - t0)

    times_fast = []
    for _ in range(ITERS):
        out = io.StringIO()
        w = rocketcsv.writer(out)
        t0 = time.perf_counter()
        w.writerows(rows)
        times_fast.append(time.perf_counter() - t0)

    return min(times_std), min(times_fast)


def bench_dictread(data):
    times_std = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        for row in csv.DictReader(io.StringIO(data)):
            pass
        times_std.append(time.perf_counter() - t0)

    times_fast = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        for row in rocketcsv.DictReader(io.StringIO(data)):
            pass
        times_fast.append(time.perf_counter() - t0)

    return min(times_std), min(times_fast)


def fmt_time(t):
    if t < 0.001:
        return f"{t*1000:.2f}ms"
    return f"{t:.3f}s"


def main():
    scenarios = [
        ("Simple 1K x 10", gen_simple(1_000, 10)),
        ("Simple 10K x 10", gen_simple(10_000, 10)),
        ("Simple 100K x 10", gen_simple(100_000, 10)),
        ("Quoted 10K x 10", gen_quoted(10_000, 10)),
        ("Quoted 100K x 10", gen_quoted(100_000, 10)),
        ("Mixed 10K x 10", gen_mixed(10_000, 10)),
        ("Mixed 100K x 10", gen_mixed(100_000, 10)),
        ("Wide 10K x 100", gen_wide(10_000, 100)),
        ("Wide 1K x 500", gen_wide(1_000, 500)),
        ("Narrow 100K x 2", gen_narrow(100_000)),
        ("Narrow 1M x 2", gen_narrow(1_000_000)),
    ]

    # Print environment info
    print("## Environment\n")
    print(f"- **Python**: {platform.python_version()}")
    print(f"- **Platform**: {platform.system()} {platform.machine()}")
    print(f"- **rocketcsv**: {rocketcsv.__version__ if hasattr(rocketcsv, '__version__') else '0.1.0'}")
    print(f"- **Iterations**: best of {ITERS}")
    print(f"- **Date**: {time.strftime('%Y-%m-%d')}")
    print()

    # Reader benchmarks
    print("## reader()\n")
    print("| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |")
    print("|----------|------|------|--------|-----------|---------|")
    for name, data in scenarios:
        rows = data.count("\n")
        size_mb = len(data.encode()) / (1024 * 1024)
        std_t, fast_t = bench_read(data)
        speedup = std_t / fast_t if fast_t > 0 else 0
        print(f"| {name} | {rows:,} | {size_mb:.1f} MB | {fmt_time(std_t)} | {fmt_time(fast_t)} | **{speedup:.1f}x** |")
    print()

    # Writer benchmarks
    print("## writer()\n")
    print("| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |")
    print("|----------|------|------|--------|-----------|---------|")
    for name, data in scenarios:
        rows = data.count("\n")
        size_mb = len(data.encode()) / (1024 * 1024)
        std_t, fast_t = bench_write(data)
        speedup = std_t / fast_t if fast_t > 0 else 0
        print(f"| {name} | {rows:,} | {size_mb:.1f} MB | {fmt_time(std_t)} | {fmt_time(fast_t)} | **{speedup:.1f}x** |")
    print()

    # DictReader benchmarks
    print("## DictReader()\n")
    print("| Scenario | Rows | Size | stdlib | rocketcsv | Speedup |")
    print("|----------|------|------|--------|-----------|---------|")
    dict_scenarios = [(n, d) for n, d in scenarios if "100K" in n or "1M" in n]
    for name, data in dict_scenarios:
        rows = data.count("\n")
        size_mb = len(data.encode()) / (1024 * 1024)
        std_t, fast_t = bench_dictread(data)
        speedup = std_t / fast_t if fast_t > 0 else 0
        print(f"| {name} | {rows:,} | {size_mb:.1f} MB | {fmt_time(std_t)} | {fmt_time(fast_t)} | **{speedup:.1f}x** |")
    print()


if __name__ == "__main__":
    main()
