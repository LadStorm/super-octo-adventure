#!/usr/bin/env python3
"""Un-scramble an AI-generated file by replacing tokens with originals.

Accepts .csv, .txt, or .md and a mapping key JSON written by scramble.py.
Replaces every known token anywhere in the content (not just the columns
originally tokenised) and writes the result to ./output/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path("output")
SUPPORTED_EXT = {".csv", ".txt", ".md"}
TOKEN_PATTERN = re.compile(r"[A-Z0-9]+_\d+")


def load_key(path: Path) -> dict[str, str]:
    if not path.is_file():
        sys.exit(f"Error: key file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"Error: key file is not valid JSON: {e}")
    if not isinstance(data, dict) or "mappings" not in data or not isinstance(data["mappings"], dict):
        sys.exit("Error: key file is malformed (missing 'mappings' object).")
    flat: dict[str, str] = {}
    for col, col_map in data["mappings"].items():
        if not isinstance(col_map, dict):
            sys.exit(f"Error: mapping for column {col!r} is malformed.")
        for token, original in col_map.items():
            if not isinstance(token, str) or not isinstance(original, str):
                sys.exit(f"Error: non-string entry in column {col!r}.")
            flat[token] = original
    if not flat:
        sys.exit("Error: key file contains no token mappings.")
    return flat


def replace_tokens(text: str, token_map: dict[str, str]) -> tuple[str, int]:
    count = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        tok = match.group(0)
        if tok in token_map:
            count += 1
            return token_map[tok]
        return tok

    return TOKEN_PATTERN.sub(_sub, text), count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Un-scramble an AI-returned file using a mapping key."
    )
    parser.add_argument("file_from_ai", help="Path to the AI's output file (.csv, .txt or .md)")
    parser.add_argument("key_file", help="Path to the *_key.json produced by scramble.py")
    args = parser.parse_args()

    src = Path(args.file_from_ai)
    if not src.is_file():
        sys.exit(f"Error: {src} not found.")
    ext = src.suffix.lower()
    if ext not in SUPPORTED_EXT:
        sys.exit(f"Error: unsupported extension '{ext}'. Use .csv, .txt, or .md.")

    token_map = load_key(Path(args.key_file))

    try:
        content = src.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        sys.exit(f"Error: could not read {src} as UTF-8 text: {e}")

    restored, n = replace_tokens(content, token_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{src.stem}_unscrambled{ext}"
    out_path.write_text(restored, encoding="utf-8")

    print(f"Tokens replaced: {n}")
    print(f"Unscrambled file written to: {out_path}")


if __name__ == "__main__":
    main()
