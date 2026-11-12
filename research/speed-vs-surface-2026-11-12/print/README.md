# Print edition

`export/report.pdf` is built from these files: one topic per A4 page, 10.5 pt body text and
vector charts drawn at their printed size with d3.

```sh
python3 prepare.py                          # print/data.json from data/, followup/ and the paired timing run
python3 build_print.py report-print.html    # self-contained HTML (d3 and data inline)
node render_print.js report-print.html report.pdf   # A4 PDF; fails if a page overflows
```

The fonts are Inter (SIL Open Font License 1.1) converted to TrueType outlines with `otf2ttf.py`
into `fonts/`, so Chromium embeds them as TrueType rather than Type 3. Paths in the scripts point
at the session's scratch directory, as in `scripts/`.
