"""
STEP 1 OF 2  -  Extract and clean every SOLace question.

What this does:
  - Looks at every .js file inside the folder you point it at.
  - Finds the question array in each file (the "...Questions = [ ... ]" block).
  - Parses it with json5, which understands JavaScript object syntax
    (single quotes, bare keys like `text:` instead of `"text":`).
  - Strips the HTML/MathML markup out of each question's `text` so what's
    left is clean, readable words for the model to work with.
  - Writes everything to questions.csv (open it in Numbers/Excel to inspect)
    and questions.json.

Run it with:   uv run python 1_extract_questions.py
One-time setup: uv add json5      (json5 is the only extra library this needs)
"""

import re
import csv
import json
import html
from pathlib import Path

import json5  # parses JavaScript-style object literals; install with `uv add json5`

# ----------------------------------------------------------------------
# SETTINGS  -  edit these two lines if your paths differ
# ----------------------------------------------------------------------
JS_FOLDER = Path("./js_files")   # put your ~40 .js files in this folder
OUTPUT_DIR = Path(".")           # where questions.csv / questions.json land
# ----------------------------------------------------------------------


def find_question_array(source_text):
    """Return the raw text of the question array literal, or None if absent.

    Anchors on any variable name ending in 'Questions = [' (so it works no
    matter what the array is called), then walks forward matching square
    brackets. It tracks whether we're inside a quoted string so that any
    '[' or ']' sitting inside question text is ignored.
    """
    anchor = re.search(r"[A-Za-z_]*[Qq]uestions\s*=\s*\[", source_text)
    if not anchor:
        return None

    start = source_text.index("[", anchor.start())
    depth = 0
    in_string = False
    quote_char = ""
    i = start

    while i < len(source_text):
        c = source_text[i]
        if in_string:
            if c == "\\":          # backslash escapes the next char; skip both
                i += 2
                continue
            if c == quote_char:    # closing quote of the same type
                in_string = False
        else:
            if c in "'\"":
                in_string = True
                quote_char = c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:     # matched the opening bracket -> done
                    return source_text[start:i + 1]
        i += 1

    return None  # brackets never balanced (malformed file)


def clean_text(raw):
    """Turn one question's markup-laden text into plain readable words.

    Example in:  'Which is a factor of <math><mi>x</mi>...</math>?'
    Example out: 'Which is a factor of x 2 - x - 6 ?'
    """
    t = re.sub(r"<br\s*/?>", " ", raw, flags=re.IGNORECASE)  # line breaks -> space
    t = re.sub(r"<[^>]+>", " ", t)                           # drop every HTML/MathML tag
    t = html.unescape(t)                                     # &lt; -> < , &amp; -> & , etc.
    t = re.sub(r"\s+", " ", t)                               # squeeze runs of whitespace
    return t.strip()


def extract_test_id(source_text):
    """Grab window.TEST_IDENTIFIER so each row knows which test it came from."""
    m = re.search(r"TEST_IDENTIFIER\s*=\s*['\"]([^'\"]+)['\"]", source_text)
    return m.group(1) if m else ""


def main():
    js_files = sorted(JS_FOLDER.glob("*.js"))
    if not js_files:
        print(f"No .js files found in {JS_FOLDER.resolve()}")
        print("Create that folder, drop your question files in, and rerun.")
        return

    rows = []
    for path in js_files:
        source = path.read_text(encoding="utf-8")
        array_literal = find_question_array(source)
        if array_literal is None:
            print(f"  skipped (no question array): {path.name}")
            continue

        questions = json5.loads(array_literal)   # list of dicts, faithful to the JS
        test_id = extract_test_id(source)

        kept = 0
        for q in questions:
            text = q.get("text")
            if not text:                          # ignore anything without question text
                continue
            rows.append({
                "source_file": path.name,
                "test_id": test_id,
                "qid": str(q.get("id", "")),
                "type": q.get("type", ""),
                "clean_text": clean_text(text),
                "raw_text": text,
            })
            kept += 1
        print(f"  {path.name}: {kept} questions")

    # Write the spreadsheet-friendly CSV
    csv_path = OUTPUT_DIR / "questions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source_file", "test_id", "qid", "type", "clean_text", "raw_text"]
        )
        writer.writeheader()
        writer.writerows(rows)

    # Write the JSON copy (handy for any later scripting)
    json_path = OUTPUT_DIR / "questions.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(rows)} questions written to:")
    print(f"  {csv_path.resolve()}")
    print(f"  {json_path.resolve()}")
    print("\nOpen questions.csv and skim the clean_text column before running step 2.")


if __name__ == "__main__":
    main()
