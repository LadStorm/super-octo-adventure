# Student data pseudonymiser

A small command-line tool for safely handing class data to AI tools.

- **`scramble.py`** — replaces identifying columns with stable tokens
  (e.g. `NAME_0001`, `EMAIL_0001`). Writes a scrambled CSV you can share and a
  mapping key you must keep private.
- **`unscramble.py`** — takes whatever the AI returns (CSV, TXT, or Markdown)
  and swaps every token back to its original value using the saved key.

## Folder layout

```
<working directory>/
├── input/        ← put original files here
├── output/       ← scrambled files + AI results land here (safe to share *out*)
├── scramble.py
└── unscramble.py

~/pseudonymise-keys/
└── <filename>_<timestamp>_key.json   ← mapping files live OUTSIDE the project
```

Keys live in `~/pseudonymise-keys/` on purpose: any AI tool scoped to the
project folder cannot see them.

## One-off setup

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.10 or newer is required.

## Usage

### 1. Scramble a file before sharing

Put the original in `./input/`, then:

```bash
python scramble.py class9A.csv
```

You'll see a numbered list of columns. Pick the identifying ones
(comma-separated):

```
Columns in class9A.csv:
  1. Name
  2. Email
  3. Year
  4. English Mark
  5. Pastoral Note

Enter columns to tokenise (comma-separated numbers, e.g. 1,2,5): 1,2,5
```

Outputs:

- `./output/class9A_scrambled.csv` — safe to paste into / upload to the AI tool.
- `~/pseudonymise-keys/class9A_<timestamp>_key.json` — **do not share**.

### 2. Un-scramble the AI's reply

Drop the AI's file into the project (`./output/` is a handy place) and run:

```bash
python unscramble.py output/ai_feedback.md ~/pseudonymise-keys/class9A_20260422-151200_key.json
```

The tool scans the whole file (not just columns) and swaps every token back.
Result goes to `./output/ai_feedback_unscrambled.md`.

## Worked example

Say `input/class9A.csv` is:

| Name         | Email                     | Year | English Mark | Pastoral Note                  |
|--------------|---------------------------|------|--------------|--------------------------------|
| Ava Johnson  | ava.johnson@school.test   | 9    | 72           | Confident speaker; often late. |
| Ben Okafor   | ben.okafor@school.test    | 9    | 58           | Needs essay scaffolding.       |
| ...          | ...                       | ...  | ...          | ...                            |

Scramble columns 1, 2, 5 (Name, Email, Pastoral Note):

```bash
python scramble.py class9A.csv
# enter: 1,2,5
```

`output/class9A_scrambled.csv` now reads:

| Name      | Email      | Year | English Mark | Pastoral Note    |
|-----------|------------|------|--------------|------------------|
| NAME_0001 | EMAIL_0001 | 9    | 72           | PASTORALNOTE_0001 |
| NAME_0002 | EMAIL_0002 | 9    | 58           | PASTORALNOTE_0002 |

Share that with the AI, ask for per-student feedback, and save the reply to
`output/ai_feedback.md`. The reply might look like:

> **NAME_0001** — Excellent tone in oral work; prioritise paragraph structure...
> **NAME_0002** — Strong ideas; build a template for essay openings...

Unscramble it:

```bash
python unscramble.py output/ai_feedback.md ~/pseudonymise-keys/class9A_20260422-151200_key.json
```

`output/ai_feedback_unscrambled.md` has real names back in place.

## Reminders before sharing

1. **Free-text columns (comments, notes, essays) may still contain identifying
   details in the body of the text.** Tokens only replace whole-cell values;
   names dropped inside a paragraph will slip through. Review manually.
2. **Small cohorts can be re-identified through context** (year level + subject
   + distinctive attributes). Strip non-essential columns before sharing.
3. **Your mapping key is the whole secret.** Anyone with the key can reverse
   the pseudonymisation. Never share it, never commit it, and keep backups
   private.

## Git safety

`.gitignore` excludes `input/`, `output/`, `*.csv`, `*.xlsx`, and any
`*_key.json`, so you can `git init` a working directory without risk of
committing student data. Keys live outside the repo anyway.
