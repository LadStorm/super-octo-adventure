#!/usr/bin/env python3
"""Scramble identifying columns in a student data file.

Reads a .csv or .xlsx from ./input/, prompts for which columns to tokenise,
writes a scrambled .csv to ./output/ and a mapping key JSON to
~/pseudonymise-keys/ (outside the working directory, so AI tools scoped
to the project cannot see it).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

KEY_DIR = Path.home() / "pseudonymise-keys"
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")


def prefix_from_column(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    return cleaned or "COL"


def read_table(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if ext == ".xlsx":
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise ValueError(f"Unsupported extension: {ext} (use .csv or .xlsx)")


def parse_selection(raw: str, n_cols: int) -> list[int]:
    indices: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError(f"'{part}' is not a number")
        i = int(part)
        if not 1 <= i <= n_cols:
            raise ValueError(f"'{i}' is out of range (1..{n_cols})")
        if i - 1 not in indices:
            indices.append(i - 1)
    return indices


def tokenise_column(values: pd.Series, prefix: str) -> tuple[pd.Series, dict[str, str]]:
    """Return (new_series, token->original map). Deterministic within the file:
    same original value always produces the same token."""
    original_to_token: dict[str, str] = {}
    new_values: list[str] = []
    counter = 0
    for v in values:
        if v == "" or v is None:
            new_values.append("")
            continue
        if v not in original_to_token:
            counter += 1
            original_to_token[v] = f"{prefix}_{counter:04d}"
        new_values.append(original_to_token[v])
    token_to_original = {tok: orig for orig, tok in original_to_token.items()}
    return pd.Series(new_values, index=values.index), token_to_original


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scramble identifying columns in a student data file."
    )
    parser.add_argument("filename", help="File name inside ./input/ (.csv or .xlsx)")
    args = parser.parse_args()

    src = INPUT_DIR / args.filename
    if not src.is_file():
        sys.exit(f"Error: {src} not found. Put the file inside ./input/ first.")

    try:
        df = read_table(src)
    except ValueError as e:
        sys.exit(f"Error: {e}")

    cols = list(df.columns)
    if not cols:
        sys.exit("Error: file has no columns.")

    print(f"\nColumns in {src.name}:")
    for i, c in enumerate(cols, 1):
        print(f"  {i}. {c}")
    raw = input("\nEnter columns to tokenise (comma-separated numbers, e.g. 1,2,5): ").strip()
    try:
        indices = parse_selection(raw, len(cols))
    except ValueError as e:
        sys.exit(f"Error: {e}")
    if not indices:
        sys.exit("No columns selected. Nothing to do.")

    mappings: dict[str, dict[str, str]] = {}
    unique_counts: dict[str, int] = {}
    for i in indices:
        col = cols[i]
        prefix = prefix_from_column(col)
        new_series, col_map = tokenise_column(df[col].astype(str), prefix)
        df[col] = new_series
        mappings[col] = col_map
        unique_counts[col] = len(col_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    KEY_DIR.mkdir(parents=True, exist_ok=True)

    stem = src.stem
    out_path = OUTPUT_DIR / f"{stem}_scrambled.csv"
    df.to_csv(out_path, index=False)

    now = datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")
    key_path = KEY_DIR / f"{stem}_{ts}_key.json"
    key_data = {
        "source_file": str(src.resolve()),
        "created": now.isoformat(timespec="seconds"),
        "mappings": mappings,
    }
    key_path.write_text(json.dumps(key_data, indent=2, ensure_ascii=False))

    print(f"\nScrambled file written to: {out_path}")
    print("Columns tokenised:")
    for col, n in unique_counts.items():
        print(f"  - {col}: {n} unique value(s)")
    print(f"Key file written to:     {key_path}")

    print(
        "\n⚠️  REMINDERS BEFORE SHARING:\n"
        " 1. Free-text columns (comments, notes, essays) may still contain identifying details in the body of the text. Review manually.\n"
        " 2. Small cohorts can be re-identified through context (year level + subject + distinctive attributes). Strip non-essential columns before sharing.\n"
        f" 3. Your mapping key is at: {key_path}. Never share this file."
    )


if __name__ == "__main__":
    main()
