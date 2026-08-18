"""
generate_images_from_csv.py

Overlay names (from a CSV) onto the "Dear ______" line of an invitation
template, generating one output image per row. Long names shrink to fit.

USAGE:
    python generate_images_from_csv.py

CONFIGURE the CONFIG section below before running.

REQUIREMENTS:
    pip install pillow
"""

from __future__ import annotations

import csv
import os
from PIL import Image, ImageDraw, ImageFont

# ============== CONFIG (edit these) ==============

CSV_FILE = "names.csv"          # CSV file with a column containing names
CSV_HAS_HEADER = True           # True if the first row is a header row
# If CSV_HAS_HEADER is True:  the header name of the column that holds the name, e.g. "name"
# If CSV_HAS_HEADER is False: the 0-based column index that holds the name, e.g. 1
CSV_NAME_COLUMN = "name"

# Column holding the mandal — each mandal gets its own subfolder under OUTPUT_DIR.
# Same rule as above: header name if CSV_HAS_HEADER, else 0-based index.
# Set to None to write every image flat into OUTPUT_DIR.
CSV_MANDAL_COLUMN = "mandal"

TEMPLATE_IMAGE = "template.jpeg" # the base image with blank space for the name
OUTPUT_DIR = "output_images"    # where generated images will be saved

# --- Placement on the "Dear _______" line (measured from template.jpeg, 840x1190) ---
TEXT_START_X = 175        # left edge of the name — clear of "Dear" (ends x=151), inside the rule (starts x=162)
RULE_Y = 198              # y of the printed underline
MAX_TEXT_WIDTH = 600      # usable width; the rule ends at x=785
BASELINE_GAP = 12         # px between the text baseline and the rule (clears descenders like p/y/g)

# Font settings
FONT_PATH = "font/Rasa-Italic-VariableFont_wght.ttf"  # path to a .ttf/.otf font file
FONT_VARIATION = "SemiBold Italic"  # variable-font instance: Light/Regular/Medium/SemiBold/Bold (+ Italic)
FONT_SIZE_MAX = 48        # starting size; short names render at this
FONT_SIZE_MIN = 28        # floor for auto-shrink on long names
TEXT_COLOR = (125, 33, 46)      # RGB — maroon, sampled from the card's own "Dear"

# Output file naming: {name}.png  (spaces replaced with underscores)
OUTPUT_PREFIX = ""
OUTPUT_SUFFIX = ""

# ===================================================


_font_cache = {}


def get_font(font_size: int):
    """Load FONT_PATH at `font_size`, falling back to Pillow's default font if not found.

    Fonts are cached per size — auto-shrink asks for several sizes per run and the
    Rasa variable font is ~286KB to parse each time.
    """
    if font_size in _font_cache:
        return _font_cache[font_size]

    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except OSError:
        print(f"⚠️  Could not load font '{FONT_PATH}'. Falling back to default font "
              f"(size/style won't be customizable). Provide a valid .ttf path for best results.")
        font = ImageFont.load_default()
    else:
        # Variable fonts expose named weights; static fonts raise OSError here.
        try:
            font.set_variation_by_name(FONT_VARIATION)
        except OSError:
            pass

    _font_cache[font_size] = font
    return font


def get_rows_from_csv(csv_file: str, name_column, mandal_column,
                      has_header: bool = True) -> list[tuple[str, str]]:
    """Read (name, mandal) pairs from the CSV.

    With a header row, the column arguments are header names. Without one, they
    are 0-based column indexes. `mandal_column` may be None, in which case every
    row comes back with an empty mandal.
    """
    rows = []
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        if has_header:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            for label, column in (("CSV_NAME_COLUMN", name_column),
                                  ("CSV_MANDAL_COLUMN", mandal_column)):
                if column is not None and column not in fields:
                    raise ValueError(
                        f"Column '{column}' ({label}) not found in CSV. "
                        f"Available columns: {fields}"
                    )
            pairs = (
                ((row.get(name_column) or ""),
                 (row.get(mandal_column) or "") if mandal_column is not None else "")
                for row in reader
            )
        else:
            for label, column in (("CSV_NAME_COLUMN", name_column),
                                  ("CSV_MANDAL_COLUMN", mandal_column)):
                if column is not None and not isinstance(column, int):
                    raise ValueError(
                        f"CSV_HAS_HEADER is False, so {label} must be a 0-based "
                        f"column index (int), not {column!r}."
                    )

            def cell(row, column, line_no, label):
                """One cell by index, with a bounds check naming the offending row."""
                if column is None:
                    return ""
                if column >= len(row):
                    raise ValueError(
                        f"Row {line_no} has only {len(row)} column(s); "
                        f"{label} is {column}. Row: {row}"
                    )
                return row[column]

            def indexed_pairs(reader):
                for line_no, row in enumerate(reader, start=1):
                    if not row:
                        continue
                    yield (cell(row, name_column, line_no, "CSV_NAME_COLUMN"),
                           cell(row, mandal_column, line_no, "CSV_MANDAL_COLUMN"))

            pairs = indexed_pairs(csv.reader(f))

        for name, mandal in pairs:
            name = name.strip()
            if name:  # a blank mandal is allowed through; a blank name is not
                rows.append((name, mandal.strip()))
    return rows


def measure_text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Width of `text` in pixels.

    textbbox() needs Pillow >= 8.0; fall back to textsize() on older versions.
    """
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    return draw.textsize(text, font=font)[0]


def fit_font(draw: ImageDraw.ImageDraw, text: str):
    """Largest font size from FONT_SIZE_MAX down that keeps `text` within MAX_TEXT_WIDTH.

    Long names (first + middle + surname) shrink only as much as they need to;
    short names stay at full size.
    """
    for size in range(FONT_SIZE_MAX, FONT_SIZE_MIN - 1, -2):
        font = get_font(size)
        if measure_text_width(draw, text, font) <= MAX_TEXT_WIDTH:
            return font

    font = get_font(FONT_SIZE_MIN)
    width = measure_text_width(draw, text, font)
    print(f"⚠️  '{text}' is {width}px at the minimum size {FONT_SIZE_MIN}, which overflows "
          f"the {MAX_TEXT_WIDTH}px line. Lower FONT_SIZE_MIN or shorten the name.")
    return font


def draw_name_on_template(template_path: str, name: str, color: tuple) -> Image.Image:
    """Write `name` on the "Dear ______" line, left-aligned and sitting on the rule."""
    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    font = fit_font(draw, name)

    # draw.text() places the top of the line box at y, so baseline = y + ascent.
    # Solving for a baseline BASELINE_GAP above the rule keeps every name on the
    # same baseline no matter which size it shrank to.
    ascent, _ = font.getmetrics()
    y = RULE_Y - BASELINE_GAP - ascent

    draw.text((TEXT_START_X, y), name, font=font, fill=color)
    return img


def safe_filename(name: str) -> str:
    keep = " _-"
    cleaned = "".join(c for c in name if c.isalnum() or c in keep).strip()
    return cleaned.replace(" ", "_")


def mandal_dir(mandal: str, name: str) -> str:
    """Output directory for one guest — OUTPUT_DIR/<mandal>, or OUTPUT_DIR if unset.

    safe_filename() strips path separators and dots, so a stray value like
    "../../etc" cannot escape OUTPUT_DIR.
    """
    folder = safe_filename(mandal)
    if not folder:
        # Only a gap in the data is worth flagging — foldering turned off entirely
        # (CSV_MANDAL_COLUMN = None) is deliberate and shouldn't warn on every row.
        if CSV_MANDAL_COLUMN is not None:
            print(f"⚠️  No mandal for '{name}' — saving to '{OUTPUT_DIR}/' root.")
        return OUTPUT_DIR
    return os.path.join(OUTPUT_DIR, folder)


def main():
    if not os.path.isfile(CSV_FILE):
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")
    if not os.path.isfile(TEMPLATE_IMAGE):
        raise FileNotFoundError(f"Template image not found: {TEMPLATE_IMAGE}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    rows = get_rows_from_csv(CSV_FILE, CSV_NAME_COLUMN, CSV_MANDAL_COLUMN, CSV_HAS_HEADER)
    if not rows:
        print("No names found in CSV. Nothing to generate.")
        return

    print(f"Generating {len(rows)} image(s)...")
    used_paths = set()
    per_mandal = {}

    for row_no, (name, mandal) in enumerate(rows, start=1):
        out_dir = mandal_dir(mandal, name)
        os.makedirs(out_dir, exist_ok=True)

        # A name of only punctuation sanitizes to "", which would write a hidden
        # ".png" — fall back to the row number so the file is findable.
        stem_name = safe_filename(name)
        if not stem_name:
            stem_name = f"guest_{row_no}"
            print(f"⚠️  '{name}' has no filename-safe characters — saving as {stem_name}.png")

        # Two guests with the same name in the same mandal would otherwise
        # overwrite each other, leaving one of them without a card.
        stem = f"{OUTPUT_PREFIX}{stem_name}{OUTPUT_SUFFIX}"
        out_path = os.path.join(out_dir, f"{stem}.png")
        dupe = 1
        while out_path in used_paths:
            dupe += 1
            out_path = os.path.join(out_dir, f"{stem}_{dupe}.png")
        if dupe > 1:
            print(f"  ℹ '{name}' appears {dupe} times in this mandal — saving as {stem}_{dupe}.png")
        used_paths.add(out_path)

        img = draw_name_on_template(TEMPLATE_IMAGE, name, TEXT_COLOR)
        img.save(out_path)
        print(f"  ✔ {out_path}")

        label = os.path.basename(out_dir) if out_dir != OUTPUT_DIR else "(no mandal)"
        per_mandal[label] = per_mandal.get(label, 0) + 1

    breakdown = ", ".join(f"{m} ({n})" for m, n in sorted(per_mandal.items()))
    print(f"\nDone. {len(rows)} image(s) in '{OUTPUT_DIR}/': {breakdown}.")


if __name__ == "__main__":
    main()
