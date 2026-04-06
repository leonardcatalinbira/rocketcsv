#!/bin/bash
# Fetch test corpus for rocketcsv shadow testing.
# See .claude-docs/ROCKETCSV_TEST_CORPUS.md for full details.
#
# Usage: bash scripts/fetch_corpus.sh

set -e
CORPUS_DIR="corpus"

mkdir -p "$CORPUS_DIR/spec-compliance/parsecsv"
mkdir -p "$CORPUS_DIR/spec-compliance/cpython"
mkdir -p "$CORPUS_DIR/spec-compliance/rfc4180-bis"
mkdir -p "$CORPUS_DIR/spec-compliance/encoding-variants"
mkdir -p "$CORPUS_DIR/parser-fixtures/pandas"
mkdir -p "$CORPUS_DIR/parser-fixtures/csvkit"
mkdir -p "$CORPUS_DIR/parser-fixtures/agate"
mkdir -p "$CORPUS_DIR/parser-fixtures/csvlint"
mkdir -p "$CORPUS_DIR/parser-fixtures/fastcsv-java"
mkdir -p "$CORPUS_DIR/parser-fixtures/rust-csv"
mkdir -p "$CORPUS_DIR/real-world/government"
mkdir -p "$CORPUS_DIR/real-world/financial"
mkdir -p "$CORPUS_DIR/real-world/text-heavy"
mkdir -p "$CORPUS_DIR/real-world/multilingual"
mkdir -p "$CORPUS_DIR/benchmarks"
mkdir -p "$CORPUS_DIR/excel-exports"

echo "=== Category 1: Spec compliance ==="

if [ ! -d "$CORPUS_DIR/spec-compliance/parsecsv/.git" ]; then
    echo "Fetching parsecsv/csv-spec..."
    git clone --depth 1 https://github.com/parsecsv/csv-spec "$CORPUS_DIR/spec-compliance/parsecsv"
fi

if [ ! -d "$CORPUS_DIR/spec-compliance/encoding-variants/.git" ]; then
    echo "Fetching CharlesNepote/CSV-test-files..."
    git clone --depth 1 https://github.com/CharlesNepote/CSV-test-files "$CORPUS_DIR/spec-compliance/encoding-variants"
fi

if [ ! -f "$CORPUS_DIR/spec-compliance/cpython/test_csv.py" ]; then
    echo "Fetching CPython test_csv.py..."
    curl -sfo "$CORPUS_DIR/spec-compliance/cpython/test_csv.py" \
        https://raw.githubusercontent.com/python/cpython/main/Lib/test/test_csv.py
fi

if [ ! -d "$CORPUS_DIR/spec-compliance/rfc4180-bis/.git" ]; then
    echo "Fetching rfc4180-bis..."
    git clone --depth 1 https://github.com/osiegmar/rfc4180-bis "$CORPUS_DIR/spec-compliance/rfc4180-bis"
fi

echo ""
echo "=== Category 2: Parser fixtures ==="

# pandas
if [ "$(ls -A $CORPUS_DIR/parser-fixtures/pandas/*.csv 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "Fetching pandas test fixtures (sparse checkout)..."
    TMP=$(mktemp -d)
    git clone --depth 1 --filter=blob:none --sparse https://github.com/pandas-dev/pandas.git "$TMP/pandas" 2>/dev/null
    cd "$TMP/pandas" && git sparse-checkout set pandas/tests/io/data/csv 2>/dev/null && cd -
    cp -r "$TMP/pandas/pandas/tests/io/data/csv"/* "$CORPUS_DIR/parser-fixtures/pandas/" 2>/dev/null || true
    rm -rf "$TMP"
fi

# csvkit
if [ "$(ls -A $CORPUS_DIR/parser-fixtures/csvkit/*.csv 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "Fetching csvkit test fixtures..."
    TMP=$(mktemp -d)
    git clone --depth 1 https://github.com/wireservice/csvkit "$TMP/csvkit" 2>/dev/null
    find "$TMP/csvkit" -name "*.csv" -exec cp {} "$CORPUS_DIR/parser-fixtures/csvkit/" \;
    rm -rf "$TMP"
fi

# agate
if [ "$(ls -A $CORPUS_DIR/parser-fixtures/agate/*.csv 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "Fetching agate test fixtures..."
    TMP=$(mktemp -d)
    git clone --depth 1 https://github.com/wireservice/agate "$TMP/agate" 2>/dev/null
    find "$TMP/agate" -name "*.csv" -exec cp {} "$CORPUS_DIR/parser-fixtures/agate/" \;
    rm -rf "$TMP"
fi

# rust-csv (BurntSushi)
if [ "$(ls -A $CORPUS_DIR/parser-fixtures/rust-csv/*.csv 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "Fetching BurntSushi/rust-csv test fixtures..."
    TMP=$(mktemp -d)
    git clone --depth 1 https://github.com/BurntSushi/rust-csv "$TMP/rust-csv" 2>/dev/null
    find "$TMP/rust-csv" -name "*.csv" -exec cp {} "$CORPUS_DIR/parser-fixtures/rust-csv/" \;
    rm -rf "$TMP"
fi

echo ""
echo "=== Category 3: Real-world ==="
echo "Most real-world datasets require manual download (Kaggle auth, large size)."
echo "See .claude-docs/ROCKETCSV_TEST_CORPUS.md for URLs."

echo ""
echo "=== Category 4: Synthetic benchmarks ==="
echo "Generating..."
python3 scripts/generate_synthetic.py

echo ""
echo "=== Category 5: Excel exports ==="
echo "Excel/Numbers/Sheets exports require manual creation."
echo "See .claude-docs/ROCKETCSV_TEST_CORPUS.md for instructions."

echo ""
echo "=== Done ==="
echo "Run: python tests/corpus_runner.py"
