#!/usr/bin/env python3
"""
Generate synthetic benchmark CSV files for rocketcsv performance testing.

Usage:
    python scripts/generate_synthetic.py

Outputs to corpus/benchmarks/
"""

import csv
import io
import os
import random
import string

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus", "benchmarks")


def ensure_dir():
    os.makedirs(CORPUS_DIR, exist_ok=True)


def write_csv(filename, header, rows):
    path = os.path.join(CORPUS_DIR, filename)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    size = os.path.getsize(path)
    print(f"  {filename}: {len(rows):,} rows, {size / (1024*1024):.1f} MB")


def rand_str(min_len=3, max_len=15):
    return "".join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))


def rand_word_sentence(words=5):
    return " ".join(rand_str(3, 8) for _ in range(words))


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def gen_simple(rows, cols):
    """Simple fields, no quoting needed."""
    header = [f"col{i}" for i in range(cols)]
    data = []
    for _ in range(rows):
        row = [str(random.randint(0, 999999)) if c % 2 == 0 else rand_str() for c in range(cols)]
        data.append(row)
    return header, data


def gen_quoted(rows, cols):
    """Every field is quoted (contains comma or quote)."""
    header = [f"col{i}" for i in range(cols)]
    specials = [",", '"', "\n", "hello, world", 'say "hi"', "a\nb"]
    data = []
    for _ in range(rows):
        row = [random.choice(specials) + rand_str(2, 5) for _ in range(cols)]
        data.append(row)
    return header, data


def gen_mixed(rows, cols):
    """Mix of quoted and unquoted fields."""
    header = [f"col{i}" for i in range(cols)]
    data = []
    for _ in range(rows):
        row = []
        for c in range(cols):
            if random.random() < 0.3:
                row.append(f"text, with comma {rand_str(3, 6)}")
            elif random.random() < 0.1:
                row.append(f'quoted "word" here')
            else:
                row.append(str(random.uniform(-1000, 1000)))
        data.append(row)
    return header, data


def gen_wide(rows, cols):
    """Wide table — many columns, short values."""
    header = [f"c{i}" for i in range(cols)]
    data = [[str(random.randint(0, 99)) for _ in range(cols)] for _ in range(rows)]
    return header, data


def gen_narrow(rows):
    """Narrow but very tall — 2 columns, tests iteration overhead."""
    header = ["key", "value"]
    data = [[str(i), rand_str(5, 10)] for i in range(rows)]
    return header, data


def gen_longfield(rows, cols, field_size=1024):
    """Each field is 1KB+ of text."""
    header = [f"field{i}" for i in range(cols)]
    data = []
    for _ in range(rows):
        row = [rand_word_sentence(field_size // 6) for _ in range(cols)]
        data.append(row)
    return header, data


def gen_unicode(rows, cols):
    """CJK, emoji, combining chars in every field."""
    cjk_chars = "".join(chr(c) for c in range(0x4E00, 0x4E50))
    emoji = "\U0001f600\U0001f680\U0001f389\U0001f525\U0001f4a1\U0001f30d\U0001f40d\U0001f60e"
    combining = "e\u0301 n\u0303 a\u0308"

    header = [f"col{i}" for i in range(cols)]
    data = []
    for _ in range(rows):
        row = []
        for _ in range(cols):
            kind = random.randint(0, 3)
            if kind == 0:
                row.append("".join(random.choices(cjk_chars, k=random.randint(3, 10))))
            elif kind == 1:
                row.append("".join(random.choices(emoji, k=random.randint(2, 5))))
            elif kind == 2:
                row.append(combining + rand_str(3, 6))
            else:
                row.append(rand_str(5, 15))
        data.append(row)
    return header, data


def gen_dictreader(rows, cols):
    """With meaningful header names, for DictReader benchmarks."""
    names = ["id", "name", "email", "age", "city", "country", "score", "active", "created", "notes"]
    header = names[:cols]
    data = []
    for i in range(rows):
        row = [
            str(i),
            rand_str(5, 12),
            f"{rand_str(5, 8)}@example.com",
            str(random.randint(18, 80)),
            rand_str(4, 10).title(),
            rand_str(4, 8).title(),
            f"{random.uniform(0, 100):.2f}",
            random.choice(["true", "false"]),
            f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            rand_word_sentence(3) if random.random() < 0.2 else "",
        ][:cols]
        data.append(row)
    return header, data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    random.seed(42)
    ensure_dir()

    print("Generating synthetic benchmark CSVs...\n")

    h, d = gen_simple(100_000, 10)
    write_csv("bench_simple_100k.csv", h, d)

    h, d = gen_simple(1_000_000, 10)
    write_csv("bench_simple_1m.csv", h, d)

    h, d = gen_quoted(100_000, 10)
    write_csv("bench_quoted_100k.csv", h, d)

    h, d = gen_mixed(100_000, 10)
    write_csv("bench_mixed_100k.csv", h, d)

    h, d = gen_wide(10_000, 200)
    write_csv("bench_wide_10k.csv", h, d)

    h, d = gen_narrow(1_000_000)
    write_csv("bench_narrow_1m.csv", h, d)

    h, d = gen_longfield(10_000, 5, field_size=1024)
    write_csv("bench_longfield_10k.csv", h, d)

    h, d = gen_unicode(50_000, 10)
    write_csv("bench_unicode_50k.csv", h, d)

    h, d = gen_dictreader(100_000, 10)
    write_csv("bench_dictreader_100k.csv", h, d)

    print("\nDone.")
