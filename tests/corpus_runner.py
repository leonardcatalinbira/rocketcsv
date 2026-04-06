#!/usr/bin/env python3
"""
Run shadow tests on every CSV file in the corpus directory.
Reports: PASS / FAIL / SKIP (with reason) for each file.

Usage:
    python tests/corpus_runner.py
"""

import csv
import io
import os
import sys
import time

import rocketcsv

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus")

# Encodings to try, in order
ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")

# Files known to be intentionally malformed (skip shadow comparison)
KNOWN_SKIPS = set()


def shadow_read(text, **kwargs):
    """Run both readers on same input, return (stdlib_rows, fast_rows)."""
    stdlib_rows = list(csv.reader(io.StringIO(text), **kwargs))
    fast_rows = list(rocketcsv.reader(io.StringIO(text), **kwargs))
    return stdlib_rows, fast_rows


def test_file(path):
    """Test a single CSV file. Returns ('pass', 'fail', or 'skip'), message."""
    basename = os.path.basename(path)

    if basename in KNOWN_SKIPS:
        return "skip", f"Known skip: {basename}"

    # Try to read with multiple encodings
    text = None
    used_encoding = None
    for enc in ENCODINGS:
        try:
            with open(path, encoding=enc, newline="") as f:
                text = f.read()
            used_encoding = enc
            break
        except (UnicodeDecodeError, ValueError):
            continue

    if text is None:
        return "skip", "Could not decode with any supported encoding"

    # Skip very large files (>50MB) to keep runtime reasonable
    if len(text) > 50 * 1024 * 1024:
        return "skip", f"Too large ({len(text) / (1024*1024):.0f} MB)"

    # Shadow test: run both readers, compare output
    try:
        stdlib_rows, fast_rows = shadow_read(text)

        if stdlib_rows == fast_rows:
            return "pass", f"{len(stdlib_rows)} rows, {used_encoding}"
        else:
            # Find first difference
            for i, (s, f) in enumerate(zip(stdlib_rows, fast_rows)):
                if s != f:
                    return "fail", (
                        f"Row {i} mismatch\n"
                        f"  stdlib: {s!r}\n"
                        f"  rocket: {f!r}"
                    )
            if len(stdlib_rows) != len(fast_rows):
                return "fail", (
                    f"Row count: stdlib={len(stdlib_rows)}, rocket={len(fast_rows)}"
                )
            return "fail", "Unknown mismatch"

    except Exception as e:
        # If both raise the same error, that's a pass
        try:
            list(csv.reader(io.StringIO(text)))
            # stdlib succeeded but rocketcsv failed
            return "fail", f"rocketcsv error (stdlib OK): {type(e).__name__}: {e}"
        except type(e):
            # Both raised the same type — that's parity
            return "pass", f"Both raised {type(e).__name__}"
        except Exception:
            return "fail", f"Different error types: {type(e).__name__}: {e}"


def main():
    if not os.path.isdir(CORPUS_DIR):
        print(f"Corpus directory not found: {CORPUS_DIR}")
        print("Run: bash scripts/fetch_corpus.sh")
        sys.exit(1)

    results = {"pass": 0, "fail": 0, "skip": 0}
    failures = []
    total_files = 0

    t0 = time.perf_counter()

    for root, dirs, files in os.walk(CORPUS_DIR):
        # Skip .git dirs inside cloned repos
        dirs[:] = [d for d in dirs if d != ".git"]

        for fname in sorted(files):
            if not fname.endswith(".csv"):
                continue

            total_files += 1
            path = os.path.join(root, fname)
            relpath = os.path.relpath(path, CORPUS_DIR)

            status, message = test_file(path)
            results[status] += 1

            if status == "fail":
                failures.append((relpath, message))
                print(f"  FAIL  {relpath}")
                for line in message.split("\n"):
                    print(f"        {line}")
            elif status == "skip":
                print(f"  SKIP  {relpath} — {message}")
            else:
                print(f"  PASS  {relpath} — {message}")

    elapsed = time.perf_counter() - t0

    # Summary
    print("\n" + "=" * 70)
    print(f"Corpus test results: {total_files} files in {elapsed:.1f}s")
    print(f"  PASS: {results['pass']}")
    print(f"  FAIL: {results['fail']}")
    print(f"  SKIP: {results['skip']}")

    tested = results["pass"] + results["fail"]
    if tested > 0:
        pass_rate = results["pass"] / tested * 100
        print(f"  Pass rate: {pass_rate:.1f}% (target: >= 99.5%)")
    print("=" * 70)

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for relpath, msg in failures:
            print(f"\n  {relpath}:")
            for line in msg.split("\n"):
                print(f"    {line}")

    sys.exit(1 if results["fail"] > 0 else 0)


if __name__ == "__main__":
    main()
