# bulk-image-edit

Bulk-generate personalised invitation cards. Reads a guest list from CSV, writes each
guest's name onto the "Dear \_\_\_\_\_\_" line of an invitation template, and saves one
PNG per guest grouped into a folder per mandal.

## Requirements

- Python 3.7+
- Pillow (`pip install pillow`) — works with Pillow 7 and up

## Usage

```bash
cp names.csv.example names.csv   # then fill in your guest list
python3 script-image.py
```

Output:

```
output_images/
  Mandal A/   Sample_Name.png, Another_Guest.png
  Mandal B/   Third_Person.png
```

## CSV format

```csv
id,name,mandal
1,Sample Name,Mandal A
2,Another Guest,Mandal A
```

Only `name` and `mandal` are read. A row with a blank `name` is skipped; a row with a
blank `mandal` still generates a card, saved to the `output_images/` root with a warning.

Headerless CSVs work too — set `CSV_HAS_HEADER = False` and give `CSV_NAME_COLUMN` /
`CSV_MANDAL_COLUMN` 0-based column indexes instead of names.

## Configuration

All settings live in the CONFIG block at the top of `script-image.py`.

| Setting | Purpose |
|---|---|
| `CSV_FILE`, `CSV_HAS_HEADER` | Input CSV and whether row 1 is a header |
| `CSV_NAME_COLUMN` | Column holding the guest name |
| `CSV_MANDAL_COLUMN` | Column holding the mandal; `None` writes everything flat |
| `TEMPLATE_IMAGE`, `OUTPUT_DIR` | Base card and output folder |
| `TEXT_START_X`, `RULE_Y`, `MAX_TEXT_WIDTH`, `BASELINE_GAP` | Where the name sits |
| `FONT_PATH`, `FONT_VARIATION`, `FONT_SIZE_MAX`, `FONT_SIZE_MIN`, `TEXT_COLOR` | Type |

### Retargeting to a different template

The placement values are measured in pixels against `template.jpeg` (840×1190). For a
different card, find the underline's `y` and its `x` span, then set `RULE_Y` to that `y`,
`TEXT_START_X` just inside the left end, and `MAX_TEXT_WIDTH` to the remaining width.
`BASELINE_GAP` is the space between the text baseline and the rule.

Names are drawn left-aligned from `TEXT_START_X` and shrink from `FONT_SIZE_MAX` down to
`FONT_SIZE_MIN` until they fit `MAX_TEXT_WIDTH`, so a long "first middle surname" still
sits on the line. The baseline is recomputed per name from the chosen size, so every card
lines up regardless of how far its name shrank.

## Known limitations

- **Latin script only.** The bundled Pillow has no `raqm`/HarfBuzz support, so Gujarati
  and Devanagari names render as empty boxes — vowel marks and conjuncts cannot be
  shaped. Install `libraqm` (and a Pillow built against it) before using non-Latin names.
- A single name too long to fit even at `FONT_SIZE_MIN` is still drawn, and warns; it will
  overrun the line.
- Removing a guest from the CSV does not delete their previously generated PNG. Clear
  `output_images/` for a clean run.

## Font

Rasa is bundled under the SIL Open Font License — see [font/NOTICE.md](font/NOTICE.md).
